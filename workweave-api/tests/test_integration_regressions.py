"""Failure-path coverage: real FalkorDB storage, synthetic Slack/ClickUp HTTP."""
import asyncio
import json
import os
from types import SimpleNamespace
import httpx
import pytest
from tests.test_assignment_graph import graph_store
from tests.test_integrations_durability import isolated_app
from tests.test_integrations_security import make_slack_headers
from workweave_api.outbox import IntegrationWorker
from workweave_api.store import uid


async def seed_job(store, slack=False):
    await store.put("proposal", {"id": "proposal", "state": "approved"})
    await store.put("outbox", {"id": "job", "state": "approved", "proposal_id": "proposal",
        "idempotency_key": "regression-marker", "title": "Fix billing export", "description": "Export fails",
        "channel": "C_TEST" if slack else "", "thread_ts": "1.1" if slack else "",
        "assignee_person_id": "person_ada", "assignee_clickup_id": "101", "assignee_name": "Ada"})
    await store.put("person", {"id": "person_ada", "name": "Ada"})


@pytest.mark.asyncio
async def test_parallel_workers_do_not_duplicate_clickup_writes(graph_store):
    store = graph_store
    await seed_job(store)
    posts = []
    async def remote(req):
        if req.method == "GET":
            await asyncio.sleep(.02)
            return httpx.Response(200, json={"tasks": []})
        posts.append(json.loads(req.content))
        return httpx.Response(200, json={"id": "CU1", "url": "https://app.clickup.com/t/CU1"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(remote)) as http:
        workers = [IntegrationWorker(store.graph, SimpleNamespace(http=http), None, None) for _ in range(2)]
        await asyncio.gather(*(w.process_outbox("company", store, {"clickup_token": "synthetic", "clickup_list_id": "123"}) for w in workers))
    assert len(posts) == 1
    assert (await store.get("outbox", "job"))["state"] == "done", json.dumps(await store.get("outbox", "job"))
    assert (await store.get("proposal", "proposal"))["state"] == "completed"


@pytest.mark.asyncio
async def test_failed_marker_search_never_creates_a_task(graph_store):
    store = graph_store
    await seed_job(store)
    posts = []
    def remote(req):
        if req.method == "POST":
            posts.append(req)
        return httpx.Response(429, json={"err": "rate limited"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(remote)) as http:
        worker = IntegrationWorker(store.graph, SimpleNamespace(http=http), None, None)
        await worker.process_outbox("company", store, {"clickup_token": "synthetic", "clickup_list_id": "123"})
    assert posts == []
    assert (await store.get("outbox", "job"))["state"] == "approved"


@pytest.mark.asyncio
async def test_ambiguous_clickup_post_is_reconciled_without_resending(graph_store):
    store = graph_store
    await seed_job(store)
    posts, tasks = [], []
    def remote(req):
        if req.method == "GET":
            return httpx.Response(200, json={"tasks": tasks})
        data = json.loads(req.content)
        posts.append(data)
        tasks.append({"id": "CU_COMMITTED", "description": data["description"]})
        raise httpx.ReadTimeout("Reply lost after remote commit", request=req)
    async with httpx.AsyncClient(transport=httpx.MockTransport(remote)) as http:
        worker = IntegrationWorker(store.graph, SimpleNamespace(http=http), None, None)
        creds = {"clickup_token": "synthetic", "clickup_list_id": "123"}
        await worker.process_outbox("company", store, creds)
        item = await store.get("outbox", "job")
        item["retry_at"] = 0
        await store.put("outbox", item)
        await worker.process_outbox("company", store, creds)
    assert len(posts) == 1
    assert (await store.get("outbox", "job"))["state"] == "done", json.dumps(await store.get("outbox", "job"))
    assert (await store.get("external_task", "ext_clickup_CU_COMMITTED"))["assignee_person_id"] == "person_ada"


@pytest.mark.asyncio
async def test_slack_failure_retries_reply_without_recreating_clickup_task(graph_store):
    store = graph_store
    await seed_job(store, slack=True)
    clickup_posts, slack_posts = [], []
    def remote(req):
        if req.url.host == "api.clickup.com":
            if req.method == "GET":
                return httpx.Response(200, json={"tasks": []})
            clickup_posts.append(req)
            return httpx.Response(200, json={"id": "CU1"})
        slack_posts.append(req)
        if len(slack_posts) == 1:
            return httpx.Response(200, json={"ok": False, "error": "ratelimited"})
        return httpx.Response(200, json={"ok": True, "ts": "2.2"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(remote)) as http:
        worker = IntegrationWorker(store.graph, SimpleNamespace(http=http), None, None)
        creds = {"clickup_token": "synthetic", "clickup_list_id": "123", "slack_bot_token": "xoxb-synthetic"}
        await worker.process_outbox("company", store, creds)
        item = await store.get("outbox", "job")
        assert item["state"] == "created", item
        assert (await store.get("proposal", "proposal"))["state"] == "approved"
        item["retry_at"] = 0
        await store.put("outbox", item)
        await worker.process_outbox("company", store, creds)
    assert len(clickup_posts) == 1
    assert len(slack_posts) == 2
    assert (await store.get("outbox", "job"))["state"] == "done", json.dumps(await store.get("outbox", "job"))


@pytest.mark.asyncio
async def test_empty_channel_selection_and_ack_has_no_remote_calls(isolated_app):
    app = isolated_app
    remote_calls = []
    def remote(req):
        remote_calls.append(req.url.path)
        if req.url.path == "/api/auth.test":
            return httpx.Response(200, json={"ok": True, "team_id": "T_TEST"})
        raise AssertionError("Webhook must not fetch Slack user profiles before ACK")
    app.state.router.http = httpx.AsyncClient(transport=httpx.MockTransport(remote))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://local.test") as client:
            signup = await client.post("/api/v1/auth/signup", json={"username": uid("tester"), "password": "synthetic-password-123", "company_name": "Test Company"})
            cid = signup.json()["company_id"]
            configured = await client.put(f"/api/v1/companies/{cid}/integrations/slack", json={"token": "xoxb-test", "signing_secret": "secret-test"})
            route = configured.json()["route_id"]
            body = json.dumps({"type": "event_callback", "team_id": "T_TEST", "event_id": "Ev1", "event": {
                "type": "message", "channel": "C_TEST", "user": "U_TEST", "text": "Fix billing export", "ts": "1.1"}}).encode()
            headers = make_slack_headers("secret-test", body)
            response = await client.post(f"/api/v1/integrations/slack/events/{route}", content=body, headers=headers)
            assert response.json()["ignored"] == "unwatched_channel"
            await client.put(f"/api/v1/companies/{cid}/integrations/slack/channels", json={"channels": ["C_TEST"]})
            response = await client.post(f"/api/v1/integrations/slack/events/{route}", content=body, headers=headers)
            assert response.json()["persisted"] is True
            assert remote_calls == ["/api/auth.test"]

@pytest.mark.asyncio
async def test_full_slack_to_graph_to_approval_to_clickup_and_reply(monkeypatch, tmp_path):
    from workweave_api.config import Settings
    from workweave_api.main import create_app
    from workweave_api.engine import Engine
    from workweave_api.store import company_store
    from tests.test_assignment_graph import seed_roster
    async def idle(*args):
        pass
    monkeypatch.setattr(Engine, "start", idle)
    monkeypatch.setattr(Engine, "stop", idle)
    monkeypatch.setattr(IntegrationWorker, "start", idle)
    monkeypatch.setattr(IntegrationWorker, "stop", idle)
    app = create_app(Settings(_env_file=None, graph_host="", graph_url=os.environ.get("WORKWEAVE_TEST_GRAPH_URL", "redis://127.0.0.1:16380"),
                             ollama_url="http://localhost:1", data_dir=tmp_path, allowed_hosts=["local.test"]))
    writes = []
    team_id = uid("T_E2E")
    def remote(req):
        if req.url.path == "/api/auth.test":
            return httpx.Response(200, json={"ok": True, "team_id": team_id, "team": "Synthetic Company"})
        if req.url.path == "/api/users.info":
            return httpx.Response(200, json={"ok": True, "user": {"name": "Haleem"}})
        if req.url.path == "/api/v2/list/123":
            return httpx.Response(200, json={"id": "123", "name": "Synthetic tasks"})
        if req.url.path == "/api/v2/list/123/task" and req.method == "GET":
            return httpx.Response(200, json={"tasks": []})
        writes.append(req.url.path)
        if req.url.host == "api.clickup.com":
            payload = json.loads(req.content)
            assert payload["assignees"] == [101]
            return httpx.Response(200, json={"id": "E2E_TASK", "url": "https://app.clickup.com/t/E2E_TASK"})
        return httpx.Response(200, json={"ok": True, "ts": "2.1"})
    async def generate(messages, policy):
        return {"text": json.dumps({"is_task": True, "title": "Fix billing export", "description": "The billing export fails.", "terms": "billing export", "due_date_text": ""})}
    await app.state.router.http.aclose()
    app.state.router.http = httpx.AsyncClient(transport=httpx.MockTransport(remote))
    app.state.router.generate = generate
    cid = None
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://local.test") as client:
            signup = await client.post("/api/v1/auth/signup", json={"username": uid("e2e"), "password": "synthetic-password-123", "company_name": "Synthetic Company"})
            cid = signup.json()["company_id"]
            store = company_store(app.state.graph, cid)
            await seed_roster(store)
            base = f"/api/v1/companies/{cid}"
            slack = await client.put(base + "/integrations/slack", json={"token": "xoxb-synthetic", "signing_secret": "synthetic-secret"})
            assert slack.status_code == 200
            assert (await client.put(base + "/integrations/clickup", json={"token": "pk_synthetic", "list_id": "123"})).status_code == 200
            assert (await client.put(base + "/integrations/slack/channels", json={"channels": ["C_E2E"]})).status_code == 200
            payload = json.dumps({"type": "event_callback", "team_id": team_id, "event_id": uid("event"),
                "event": {"type": "message", "channel": "C_E2E", "user": "U_TEST", "text": "Please fix billing export", "ts": "1.0"}}).encode()
            response = await client.post("/api/v1/integrations/slack/events/" + slack.json()["route_id"], content=payload, headers=make_slack_headers("synthetic-secret", payload))
            assert response.json()["persisted"] is True
            await app.state.worker.tick()
            proposals = (await client.get(base + "/proposals")).json()
            assert len(proposals) == 1
            proposal = proposals[0]
            assert proposal["slack_message"] == "Please fix billing export"
            assert proposal["reasoning"]
            assert proposal["candidates"][0]["breakdown"]["completed_outcomes"] == 1
            assert proposal["candidates"][0]["path_ids"][0] == "person_ada"
            assert proposal["candidates"][0]["evidence_chunks"][0]["id"] == "chunk_fin"
            assert writes == []
            approved = await client.post(base + "/proposals/" + proposal["id"] + "/approve", json={})
            assert approved.status_code == 200
            # Approved work stays visible while the worker completes delivery.
            assert (await client.get(base + "/proposals")).json()[0]["state"] == "approved"
            await app.state.worker.tick()
            completed = (await client.get(base + "/proposals?state=completed")).json()
            assert completed[0]["clickup_task_id"] == "E2E_TASK"
            assert writes == ["/api/v2/list/123/task", "/api/chat.postMessage"]
            await app.state.worker.tick()
            assert len(writes) == 2
            await app.state.graph.redis.execute_command("GRAPH.DELETE", store.name)
