import hashlib
import json
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, SecretStr
from . import clickup_client
from . import slack_client
from .credentials import (
    clear_company_credentials,
    get_company_credentials,
    get_company_status,
    set_company_clickup,
    set_company_slack,
)
from . import store as store_module
from .store import Store, now, uid
from .assignment import sync_assignment_graph
from .understanding import current_chunks


class SlackConfigInput(BaseModel):
    token: SecretStr = Field(min_length=5, max_length=500)
    signing_secret: SecretStr = Field(min_length=5, max_length=500)
    app_id: str = Field(default="", max_length=100)


class SlackChannelsInput(BaseModel):
    channels: list[str] = Field(max_length=50)


class ClickUpConfigInput(BaseModel):
    token: SecretStr = Field(min_length=5, max_length=500)
    list_id: str = Field(min_length=1, max_length=80)


class ProposalActionInput(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    assignee_person_id: str | None = Field(default=None, max_length=100)
    assignee_clickup_id: str | None = Field(default=None, max_length=100)
    due_date_ms: int | None = Field(default=None)


class RosterMemberInput(BaseModel):
    id: str | None = Field(default=None, max_length=100)
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(default="", max_length=160)
    responsibility: str = Field(default="", max_length=3000)
    clickup_id: str = Field(default="", max_length=80)
    slack_id: str = Field(default="", max_length=80)
    evidence_ids: list[str] = Field(default_factory=list, max_length=30)


def register_integrations(app, config, router, control: Store, workspace, administrator, worker):
    api = APIRouter()

    # --- 1. Slack Events Webhook Endpoint (Unauthenticated, Verified by Signature) ---
    @app.post("/api/v1/integrations/slack/events/{route_id}")
    async def slack_webhook(route_id: str, request: Request):
        route = await control.get("integration_route", route_id)
        if not route or not route.get("active", True):
            raise HTTPException(404, "Unknown integration route")

        company_id = route["company_id"]
        creds = get_company_credentials(router.vault, config, company_id)
        signing_secret = creds.get("slack_signing_secret")
        if not signing_secret:
            raise HTTPException(404, "Slack is not configured for this workspace")

        raw_body = await request.body()
        timestamp = request.headers.get("x-slack-request-timestamp", "")
        signature = request.headers.get("x-slack-signature", "")

        if not slack_client.verify_signature(raw_body, timestamp, signature, signing_secret):
            raise HTTPException(401, "Invalid Slack signature")

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception:
            raise HTTPException(400, "Invalid JSON payload")

        # URL verification handshake
        if payload.get("type") == "url_verification":
            return {"challenge": payload.get("challenge")}

        if payload.get("type") == "event_callback":
            # Security verification: team_id must match configured team
            team_id = payload.get("team_id")
            if route.get("team_id") and team_id != route["team_id"]:
                raise HTTPException(403, "Slack team mismatch")

            api_app_id = payload.get("api_app_id")
            if route.get("app_id") and api_app_id and api_app_id != route["app_id"]:
                raise HTTPException(403, "Slack app mismatch")

            event = payload.get("event", {})
            event_type = event.get("type")
            if event_type == "message":
                # Ignore bot messages and edits
                if event.get("bot_id") or event.get("subtype") in ("bot_message", "message_changed", "message_deleted"):
                    return {"ok": True, "ignored": "bot_or_subtype"}

                channel = event.get("channel")
                watched_channels = route.get("channels", [])
                if channel not in watched_channels:
                    return {"ok": True, "ignored": "unwatched_channel"}

                event_id = payload.get("event_id") or f"{channel}:{event.get('ts')}"
                store = store_module.company_store(control.graph, company_id)

                # Persist event BEFORE returning 200 to Slack
                record_id = f"se_{hashlib.sha256((company_id + ':' + event_id).encode()).hexdigest()[:20]}"
                ev_data = {
                    "id": record_id,
                    "event_id": event_id,
                    "company_id": company_id,
                    "channel": channel,
                    "user": event.get("user", ""),
                    "text": event.get("text", ""),
                    "ts": event.get("ts", ""),
                    "thread_ts": event.get("thread_ts") or event.get("ts", ""),
                    "state": "received",
                    "created_at": now(),
                }

                # Network enrichment belongs in the worker, after durable acceptance.
                ev_data["author_name"] = event.get("user", "User")

                created = await store.create_once("slack_event", ev_data)
                if created:
                    worker.trigger()

                return {"ok": True, "persisted": created}

        return {"ok": True}

    # --- 2. Company Integration Management Endpoints (Admin Required) ---

    @app.get("/api/v1/companies/{company_id}/integrations/status")
    async def get_status(company_id: str, access=Depends(workspace)):
        administrator(access)
        status = get_company_status(router.vault, config, company_id)
        route_records = await control.list("integration_route", 500)
        route = next((r for r in route_records if r.get("company_id") == company_id and r.get("active")), None)
        if route:
            status["slack"]["request_url"] = f"{config.public_base_url.rstrip('/')}/api/v1/integrations/slack/events/{route['id']}"
            status["slack"]["channels"] = route.get("channels", [])
            status["slack"]["team_name"] = route.get("team_name", "")
            status["slack"]["team_id"] = route.get("team_id", "")
        else:
            status["slack"]["request_url"] = ""
            status["slack"]["channels"] = []

        return status

    @app.put("/api/v1/companies/{company_id}/integrations/slack")
    async def configure_slack(company_id: str, body: SlackConfigInput, access=Depends(workspace)):
        administrator(access)
        token = body.token.get_secret_value().strip()
        secret = body.signing_secret.get_secret_value().strip()

        # Validate with Slack auth.test
        auth_info = await slack_client.auth_test(router.http, token)
        team_id = auth_info.get("team_id", "")
        team_name = auth_info.get("team", "")
        app_id = body.app_id.strip() or auth_info.get("app_id", "")

        set_company_slack(router.vault, company_id, token, secret, app_id=app_id)

        # Retrieve or create integration route
        route_records = await control.list("integration_route", 500)
        route = next((r for r in route_records if r.get("company_id") == company_id and r.get("active")), None)
        if not route:
            route_id = f"r_{secrets.token_hex(16)}"
            route = {
                "id": route_id,
                "company_id": company_id,
                "team_id": team_id,
                "team_name": team_name,
                "app_id": app_id,
                "channels": [],
                "active": True,
                "created_at": now(),
            }
        else:
            route["team_id"] = team_id
            route["team_name"] = team_name
            route["app_id"] = app_id
            route["updated_at"] = now()

        await control.put("integration_route", route)
        request_url = f"{config.public_base_url.rstrip('/')}/api/v1/integrations/slack/events/{route['id']}"
        return {
            "route_id": route["id"],
            "request_url": request_url,
            "team_id": team_id,
            "team_name": team_name,
        }

    @app.get("/api/v1/companies/{company_id}/integrations/slack/channels")
    async def get_slack_channels(company_id: str, access=Depends(workspace)):
        administrator(access)
        creds = get_company_credentials(router.vault, config, company_id)
        token = creds.get("slack_bot_token")
        if not token:
            raise HTTPException(400, "Slack is not configured")

        channels = await slack_client.conversations_list(router.http, token)
        route_records = await control.list("integration_route", 500)
        route = next((r for r in route_records if r.get("company_id") == company_id and r.get("active")), None)
        watched = set(route.get("channels", []) if route else [])

        for c in channels:
            c["watched"] = c["id"] in watched
        return channels

    @app.put("/api/v1/companies/{company_id}/integrations/slack/channels")
    async def set_slack_channels(company_id: str, body: SlackChannelsInput, access=Depends(workspace)):
        administrator(access)
        route_records = await control.list("integration_route", 500)
        route = next((r for r in route_records if r.get("company_id") == company_id and r.get("active")), None)
        if not route:
            raise HTTPException(400, "Configure Slack credentials first")

        team_id = route.get("team_id", "default")
        # Exclusive channel claims across companies
        for ch in body.channels:
            claim_id = f"slack_claim:{team_id}:{ch}"
            await control.create_once("connection", {"id": claim_id, "company_id": company_id, "channel": ch})
            existing_claim = await control.get("connection", claim_id)
            if existing_claim and existing_claim.get("company_id") != company_id:
                raise HTTPException(409, f"Channel {ch} is already connected to another workspace")

        route["channels"] = body.channels
        route["updated_at"] = now()
        await control.put("integration_route", route)
        return {"channels": route["channels"]}

    @app.put("/api/v1/companies/{company_id}/integrations/clickup")
    async def configure_clickup(company_id: str, body: ClickUpConfigInput, access=Depends(workspace)):
        administrator(access)
        token = body.token.get_secret_value().strip()
        list_id = body.list_id.strip()

        list_info = await clickup_client.get_list(router.http, token, list_id)
        set_company_clickup(router.vault, company_id, token, list_id)
        return {
            "list_id": list_id,
            "list_name": list_info.get("name", "Default List"),
        }

    @app.delete("/api/v1/companies/{company_id}/integrations/{provider}")
    async def remove_integration(company_id: str, provider: str, access=Depends(workspace)):
        administrator(access)
        if provider not in ("slack", "clickup"):
            raise HTTPException(400, "Unknown provider")
        clear_company_credentials(router.vault, company_id, provider=provider)
        if provider == "slack":
            route_records = await control.list("integration_route", 500)
            for r in route_records:
                if r.get("company_id") == company_id:
                    r["active"] = False
                    await control.put("integration_route", r)
        return {"disconnected": True}

    @app.get("/api/v1/companies/{company_id}/clickup/members")
    async def get_clickup_members(company_id: str, access=Depends(workspace)):
        administrator(access)
        creds = get_company_credentials(router.vault, config, company_id)
        token = creds.get("clickup_token")
        list_id = creds.get("clickup_list_id")
        if not token or not list_id:
            return []
        try:
            return await clickup_client.list_members(router.http, token, list_id)
        except Exception as exc:
            raise HTTPException(502, f"Could not fetch ClickUp members: {exc}")

    # --- 3. Team Roster (People + Identities + Roles + Responsibilities) ---

    @app.get("/api/v1/companies/{company_id}/roster")
    async def get_roster(company_id: str, access=Depends(workspace)):
        store = access[0]
        people = await store.list("person")
        return [
            {
                "id": p["id"],
                "name": p["name"],
                "role": p.get("role", ""),
                "responsibility": p.get("responsibility", ""),
                "clickup_id": p.get("clickup_id", ""),
                "slack_id": p.get("slack_id", ""),
                "evidence_ids": p.get("evidence_ids", []),
                "confirmed": p.get("confirmed", True),
            }
            for p in people
        ]

    @app.put("/api/v1/companies/{company_id}/roster")
    async def save_roster_member(company_id: str, body: RosterMemberInput, access=Depends(workspace)):
        administrator(access)
        store = access[0]
        person_id = body.id or uid("person")
        valid_ids = {c["id"] for c in await current_chunks(store)}
        if not set(body.evidence_ids) <= valid_ids:
            raise HTTPException(409, "The source changed. Review current documents before saving this role.")
        if not body.name.strip():
            raise HTTPException(422, "Enter a person name")

        record = {
            "id": person_id,
            "name": body.name.strip(),
            "role": body.role.strip(),
            "responsibility": body.responsibility.strip(),
            "clickup_id": body.clickup_id.strip(),
            "slack_id": body.slack_id.strip(),
            "evidence_ids": body.evidence_ids,
            "confirmed": True,
            "updated_at": now(),
        }
        await store.put("person", record)

        # Update node in graph with indexed attributes
        await control.graph.query(
            store.name,
            "MERGE (p:Record:Person {id:$id}) SET p.name=$name, p.role=$role, p.responsibility=$resp",
            {"id": person_id, "name": record["name"], "role": record["role"], "resp": record["responsibility"]}
        )

        # Maintain graph links
        for eid in body.evidence_ids:
            try:
                await store.link(person_id, "SUPPORTED_BY", eid)
            except Exception:
                pass
        await sync_assignment_graph(store)
        return record

    # --- 4. Task Inbox & Proposals (Human Approval Gate) ---

    @app.get("/api/v1/companies/{company_id}/proposals")
    async def list_proposals(company_id: str, state: str = "pending", access=Depends(workspace)):
        store = access[0]
        items = await store.list("proposal", 200)
        if state != "all":
            states = ("pending", "approving", "approved") if state == "pending" else (state,)
            items = [p for p in items if p.get("state") in states]
        items.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        for p in items:
            # Keep existing saved proposals compatible with the inbox contract.
            p["slack_message"] = p.get("message_text", "")
            p["reasoning"] = p.get("reason", "")
            if p.get("outbox_id"):
                ob = await store.get("outbox", p["outbox_id"])
                if ob:
                    p["outbox_state"] = ob.get("state")
                    p["outbox_error"] = ob.get("error")
                    if ob.get("clickup_task_url") and not p.get("clickup_task_url"):
                        p["clickup_task_url"] = ob.get("clickup_task_url")
                    if ob.get("clickup_task_id") and not p.get("clickup_task_id"):
                        p["clickup_task_id"] = ob.get("clickup_task_id")
        return items

    @app.post("/api/v1/companies/{company_id}/proposals/{proposal_id}/approve")
    async def approve_proposal(
        company_id: str,
        proposal_id: str,
        body: ProposalActionInput,
        access=Depends(workspace)
    ):
        administrator(access)
        store = access[0]
        prop = await store.get("proposal", proposal_id)
        if not prop:
            raise HTTPException(404, "Proposal not found")

        # Check existing outbox to guarantee idempotency
        outbox_id = f"out_{hashlib.sha256((company_id + ':' + proposal_id).encode()).hexdigest()[:20]}"
        existing_outbox = await store.get("outbox", outbox_id)
        if existing_outbox:
            return {
                "outbox_id": outbox_id,
                "status": existing_outbox["state"],
                "clickup_task_url": existing_outbox.get("clickup_task_url"),
            }
        if prop.get("state") not in ("pending", "approving"):
            raise HTTPException(409, "Only pending proposals can be approved")

        title = (body.title or prop.get("title") or "Task").strip()
        description = (body.description or prop.get("description") or "").strip()
        assignee_person_id = body.assignee_person_id or prop.get("recommended_person_id")
        assignee_clickup_id = body.assignee_clickup_id or prop.get("recommended_clickup_id")

        # Resolve assignee name
        assignee_name = prop.get("recommended_person_name", "")
        if assignee_person_id:
            person = await store.get("person", assignee_person_id)
            if person:
                assignee_name = person.get("name", assignee_name)
                if not assignee_clickup_id:
                    assignee_clickup_id = person.get("clickup_id")

        idempotency_key = f"ww-{hashlib.sha256((company_id + ':' + proposal_id).encode()).hexdigest()[:20]}"
        outbox_entry = {
            "id": outbox_id,
            "proposal_id": proposal_id,
            "idempotency_key": idempotency_key,
            "title": title,
            "description": description,
            "channel": prop.get("channel"),
            "thread_ts": prop.get("thread_ts"),
            "author_name": prop.get("author_name"),
            "assignee_person_id": assignee_person_id,
            "assignee_clickup_id": assignee_clickup_id,
            "assignee_name": assignee_name,
            "due_date_ms": body.due_date_ms,
            "state": "approved",
            "attempts": 0,
            "created_at": now(),
        }

        if not await store.claim("proposal", proposal_id, ["pending"], "approving", 30, uid("approval")):
            raise HTTPException(409, "This proposal is already being reviewed. Refresh its status.")
        await store.create_once("outbox", outbox_entry)
        prop["state"] = "approved"
        prop["outbox_id"] = outbox_id
        await store.put("proposal", prop)

        worker.trigger()
        return {
            "outbox_id": outbox_id,
            "status": "approved",
            "idempotency_key": idempotency_key,
        }

    @app.post("/api/v1/companies/{company_id}/proposals/{proposal_id}/reject")
    async def reject_proposal(company_id: str, proposal_id: str, access=Depends(workspace)):
        administrator(access)
        store = access[0]
        prop = await store.get("proposal", proposal_id)
        if not prop:
            raise HTTPException(404, "Proposal not found")
        outbox_id = f"out_{hashlib.sha256((company_id + ':' + proposal_id).encode()).hexdigest()[:20]}"
        if prop.get("state") != "pending" or await store.get("outbox", outbox_id):
            raise HTTPException(409, "An approved or completed proposal cannot be dismissed")
        if not await store.claim("proposal", proposal_id, ["pending"], "rejected", 30, uid("review")):
            raise HTTPException(409, "This proposal is already being reviewed")
        prop["state"] = "rejected"
        prop["updated_at"] = now()
        await store.put("proposal", prop)
        return {"rejected": True}

    @app.post("/api/v1/companies/{company_id}/outbox/{outbox_id}/retry")
    async def retry_outbox(company_id: str, outbox_id: str, access=Depends(workspace)):
        administrator(access)
        store = access[0]
        item = await store.get("outbox", outbox_id)
        if not item:
            raise HTTPException(404, "Outbox item not found")
        if item.get("state") != "failed":
            raise HTTPException(400, f"Cannot retry outbox in state {item.get('state')}")
        item["state"] = "created" if item.get("clickup_task_id") else "approved"
        item["attempts"] = 0
        item["lease_until"] = 0
        item["retry_at"] = 0
        item["error"] = None
        await store.put("outbox", item)
        worker.trigger()
        return {"retrying": True}
