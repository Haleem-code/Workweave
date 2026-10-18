import asyncio
import hashlib
import json
import logging
import time
from . import clickup_client
from . import slack_client
from .credentials import get_company_credentials
from . import store as store_module
from .store import Store, now, uid
from .triage import triage_slack_message
from .models import effective_provider_policy

logger = logging.getLogger("workweave.integrations")


class IntegrationWorker:
    def __init__(self, graph, router, control: Store, config):
        self.graph = graph
        self.router = router
        self.control = control
        self.config = config
        self.running = False
        self.task = None
        self.notify_event = asyncio.Event()
        self.last_outcome_sync = {}

    async def start(self):
        self.running = True
        self.task = asyncio.create_task(self.loop())

    async def stop(self):
        self.running = False
        self.notify_event.set()
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    def trigger(self):
        self.notify_event.set()

    async def loop(self):
        while self.running:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Error in integration worker tick: %s", exc)

            try:
                await asyncio.wait_for(self.notify_event.wait(), timeout=15)
                self.notify_event.clear()
            except TimeoutError:
                pass

    async def tick(self):
        companies = await self.control.list("company")
        for company in companies:
            cid = company["id"]
            store = store_module.company_store(self.graph, cid)
            creds = get_company_credentials(self.router.vault, self.config, cid)
            if not creds.get("slack_bot_token") and not creds.get("clickup_token"):
                continue
            policy = effective_provider_policy(company)

            # Process event inbox
            await self.process_inbox(cid, store, creds, policy)

            # Process outbox
            await self.process_outbox(cid, store, creds)

            # Periodic outcome sync (every 10 minutes)
            last_sync = self.last_outcome_sync.get(cid, 0)
            if now() - last_sync >= 600:
                self.last_outcome_sync[cid] = now()
                try:
                    await self.sync_outcomes(cid, store, creds)
                except Exception as exc:
                    logger.warning("Outcome sync error for %s: %s", cid, exc)

    async def process_inbox(self, company_id: str, store: Store, creds: dict, policy: dict):
        events = await store.list("slack_event", 5000)
        for ev in events:
            state = ev.get("state")
            if state in ("ignored", "processed", "dead"):
                continue

            # Attempt to claim
            owner = uid("worker")
            attempts = await store.claim("slack_event", ev["id"], ["received"], "triaging", 300, owner)
            if not attempts:
                continue
            ev = await store.get("slack_event", ev["id"])

            try:
                text = ev.get("text", "")
                if creds.get("slack_bot_token") and ev.get("user"):
                    try:
                        user = await slack_client.user_info(self.router.http, creds["slack_bot_token"], ev["user"])
                        ev["author_name"] = user.get("name") or ev["user"]
                    except Exception:
                        pass
                author = ev.get("author_name") or ev.get("user", "User")
                channel = ev.get("channel", "")
                thread_ts = ev.get("thread_ts") or ev.get("ts", "")

                result = await triage_slack_message(
                    store, self.router, policy, text, author, channel, thread_ts
                )

                if not result["is_task"]:
                    ev["state"] = "ignored"
                    ev["ignore_reason"] = result.get("reason", "Not an actionable task")
                    await self._save_job(store, "slack_event", ev, owner)
                    continue

                # Create task proposal
                event_id = ev.get("event_id") or ev["id"]
                proposal_id = f"tp_{hashlib.sha256((company_id + ':' + event_id).encode()).hexdigest()[:20]}"
                
                chosen = result.get("chosen_candidate") or {}
                proposal = {
                    "id": proposal_id,
                    "event_id": ev["id"],
                    "channel": channel,
                    "thread_ts": thread_ts,
                    "slack_user": ev.get("user", ""),
                    "author_name": author,
                    "message_text": text,
                    "title": result["title"],
                    "description": result["description"],
                    "due_date_text": result.get("due_date_text", ""),
                    "recommended_person_id": chosen.get("person_id"),
                    "recommended_person_name": chosen.get("name"),
                    "recommended_role": chosen.get("role", ""),
                    "recommended_clickup_id": chosen.get("clickup_id"),
                    "reason": result.get("reason", ""),
                    "candidates": result.get("candidates", []),
                    "path_ids": chosen.get("path_ids", []),
                    "evidence_ids": chosen.get("evidence_ids", []),
                    "past_task_ids": chosen.get("past_task_ids", []),
                    "state": "pending",
                    "created_at": now(),
                }
                await store.create_once("proposal", proposal)

                # Link graph edges
                try:
                    await store.link(proposal_id, "PROPOSED", ev["id"])
                    if chosen.get("person_id"):
                        await store.link(proposal_id, "RECOMMENDS", chosen["person_id"])
                    for chunk_id in chosen.get("evidence_ids", []):
                        try:
                            await store.link(proposal_id, "SUPPORTED_BY", chunk_id)
                        except Exception:
                            pass
                except Exception as exc:
                    logger.warning("Graph link error on proposal %s: %s", proposal_id, exc)

                ev["state"] = "processed"
                ev["proposal_id"] = proposal_id
                await self._save_job(store, "slack_event", ev, owner)

            except Exception as exc:
                logger.exception("Error triaging event %s: %s", ev["id"], exc)
                ev = await store.get("slack_event", ev["id"]) or ev
                if (ev.get("attempts") or 1) >= 5:
                    ev["state"] = "dead"
                    ev["error"] = str(exc)[:300]
                else:
                    ev["state"] = "received"
                await store.put_owned("slack_event", ev, owner)

    async def _save_job(self, store, kind, item, owner):
        if not await store.put_owned(kind, item, owner):
            raise RuntimeError("Job lease expired or ownership changed")

    async def _record_external_task(self, store, item):
        task_id = "ext_clickup_" + item["clickup_task_id"]
        # Reconciliation must restore graph memory too, without resetting outcomes.
        if not await store.get("external_task", task_id):
            await store.create_once("external_task", {
                "id": task_id, "clickup_id": item["clickup_task_id"],
                "list_id": item.get("clickup_list_id"),
                "title": item["title"], "description": item.get("description", ""),
                "status": "open", "outcome": "in_progress",
                "clickup_assignee_id": item.get("assignee_clickup_id"),
                "assignee_person_id": item.get("assignee_person_id"), "created_at": now(),
            })
        if item.get("assignee_person_id"):
            await store.link(task_id, "ASSIGNED_TO", item["assignee_person_id"])

    async def process_outbox(self, company_id: str, store: Store, creds: dict):
        outbox_items = await store.list("outbox", 5000)
        for snapshot in outbox_items:
            oid = snapshot["id"]
            state = snapshot.get("state")
            if state in ("done", "failed"):
                continue
            if snapshot.get("retry_at", 0) > now():
                continue
            owner = uid("worker")
            if state in ("approved", "creating"):
                attempts = await store.claim("outbox", oid, ["approved"], "creating", 120, owner)
                if not attempts:
                    continue
                item = await store.get("outbox", oid)
                try:
                    token = creds.get("clickup_token")
                    list_id = item.get("clickup_list_id") or creds.get("clickup_list_id")
                    if not token or not list_id:
                        raise RuntimeError("ClickUp token or list ID not configured")
                    item["clickup_list_id"] = list_id
                    if not item.get("clickup_task_id"):
                        existing = await clickup_client.find_by_marker(
                            self.router.http, token, list_id, item["idempotency_key"])
                        if existing:
                            item["clickup_task_id"] = str(existing["id"])
                            item["clickup_task_url"] = existing.get("url") or f"https://app.clickup.com/t/{existing['id']}"
                        elif item.get("create_started"):
                            # A timed-out POST may already have committed remotely.
                            # Never blindly resend a non-idempotent external write.
                            item["state"] = "failed"
                            item["error"] = "ClickUp creation outcome is uncertain. Check the destination list; retry will reconcile only. No duplicate task was sent."
                            await self._save_job(store, "outbox", item, owner)
                            continue
                        else:
                            item["create_started"] = True
                            await self._save_job(store, "outbox", item, owner)
                            marker = item["idempotency_key"]
                            description = (item.get("description", "") +
                                f"\n\n---\nRequested via Slack by {item.get('author_name') or 'a team member'}.\n⟦workweave:{marker}⟧")
                            task = await clickup_client.create_task(
                                self.router.http, token, list_id, name=item["title"],
                                description=description,
                                assignees=[item["assignee_clickup_id"]] if item.get("assignee_clickup_id") else [],
                                due_date_ms=item.get("due_date_ms"))
                            item["clickup_task_id"] = str(task["id"])
                            item["clickup_task_url"] = task.get("url") or f"https://app.clickup.com/t/{task['id']}"
                    item["state"] = "created"
                    item["error"] = None
                    await self._save_job(store, "outbox", item, owner)
                except Exception:
                    # Public state never contains HTTP credentials or response bodies.
                    item["state"] = "failed" if attempts >= 4 else "approved"
                    item["error"] = "ClickUp delivery could not be confirmed. The worker will reconcile before any further action."
                    item["retry_at"] = now() + min(300, 15 * attempts)
                    await store.put_owned("outbox", item, owner)
                    continue

            item = await store.get("outbox", oid)
            if not item or item.get("state") not in ("created", "replying"):
                continue
            owner = uid("worker")
            attempts = await store.claim("outbox", oid, ["created"], "replying", 120, owner)
            if not attempts:
                continue
            item = await store.get("outbox", oid)
            try:
                await self._record_external_task(store, item)
                token = creds.get("slack_bot_token")
                channel, thread_ts = item.get("channel"), item.get("thread_ts")
                # Imported/demo proposals may have no Slack delivery target.
                if channel and thread_ts:
                    if not token:
                        raise RuntimeError("Slack connection required for thread confirmation")
                    if not item.get("slack_reply_ts") and item.get("reply_started"):
                        replies = await slack_client.conversations_replies(self.router.http, token, channel, thread_ts)
                        for msg in replies:
                            metadata = msg.get("metadata") or {}
                            if metadata.get("event_payload", {}).get("key") == item["idempotency_key"]:
                                item["slack_reply_ts"] = msg.get("ts")
                                break
                        if not item.get("slack_reply_ts"):
                            raise RuntimeError("Previous Slack delivery is uncertain; check the thread before resending")
                    if not item.get("slack_reply_ts"):
                        item["reply_started"] = True
                        await self._save_job(store, "outbox", item, owner)
                        marker = item["idempotency_key"]
                        result = await slack_client.post_thread_reply(
                            self.router.http, token, channel, thread_ts,
                            f"✅ Task created in ClickUp and assigned to *{item.get('assignee_name') or 'team member'}*:\n<{item['clickup_task_url']}|{item['title']}>",
                            metadata={"event_type": "workweave_task_assigned", "event_payload": {"key": marker, "task_id": item["clickup_task_id"]}})
                        item["slack_reply_ts"] = result["ts"]
                # Persist delivery receipt before updating the proposal. A restart
                # can repeat the local update without sending another message.
                item["state"] = "replying"
                item["error"] = None
                await self._save_job(store, "outbox", item, owner)
                if item.get("proposal_id"):
                    prop = await store.get("proposal", item["proposal_id"])
                    if prop:
                        prop.update(state="completed", clickup_task_id=item["clickup_task_id"],
                                    clickup_task_url=item["clickup_task_url"])
                        await store.put("proposal", prop)
                item["state"] = "done"
                await self._save_job(store, "outbox", item, owner)
            except Exception as exc:
                if isinstance(exc, slack_client.SlackDeliveryRejected):
                    item["reply_started"] = False
                item["state"] = "failed" if attempts >= 8 else "created"
                item["error"] = "ClickUp task exists; Slack confirmation is pending or uncertain. Retry checks the thread without recreating the task."
                item["retry_at"] = now() + min(300, 15 * attempts)
                await store.put_owned("outbox", item, owner)

    async def sync_outcomes(self, company_id: str, store: Store, creds: dict):
        clickup_token = creds.get("clickup_token")
        clickup_list_id = creds.get("clickup_list_id")
        if not clickup_token or not clickup_list_id:
            return

        tasks = await store.list("external_task", 500)
        open_tasks = [t for t in tasks if t.get("status") not in ("closed", "done", "complete")]
        if not open_tasks:
            return

        try:
            recent_updates = await clickup_client.list_tasks_updated(
                self.router.http, clickup_token, clickup_list_id
            )
            update_map = {str(t["id"]): t for t in recent_updates}

            for t in open_tasks:
                cid = t.get("clickup_id")
                remote = update_map.get(cid)
                if not remote:
                    continue

                new_status = remote.get("status", {}).get("status", "").lower()
                date_done = remote.get("date_done")
                due_date = remote.get("due_date")

                t["status"] = new_status
                if new_status in ("complete", "closed", "done"):
                    if due_date and date_done:
                        if int(date_done) <= int(due_date):
                            t["outcome"] = "completed_on_time"
                        else:
                            t["outcome"] = "completed_late"
                    else:
                        t["outcome"] = "completed"

                # Check if reassigned
                assignees = [str(a.get("id")) for a in remote.get("assignees", [])]
                if t.get("clickup_assignee_id") and assignees:
                    if str(t["clickup_assignee_id"]) not in assignees:
                        t["reassigned"] = True
                        t["outcome"] = "reassigned"

                t["updated_at"] = now()
                await store.put("external_task", t)

        except Exception as exc:
            logger.warning("Error during outcome sync: %s", exc)
