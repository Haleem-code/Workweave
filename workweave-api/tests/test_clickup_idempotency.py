import json
import time
import httpx
import pytest
from copy import deepcopy
from workweave_api import main as main_module
from workweave_api.config import Settings
from workweave_api.main import create_app
from workweave_api.store import uid


@pytest.fixture
def isolated_app(monkeypatch, tmp_path):
    records = {}
    class MemoryGraph:
        def __init__(self, *args): pass
        async def schema(self, *args): pass
        async def close(self): pass
        async def query(self, graph, query, params=None):
            return []
    class MemoryStore:
        def __init__(self, graph, name):
            self.graph, self.name = graph, name
        async def put(self, kind, value, props=None):
            records[(self.name, kind, value["id"])] = deepcopy(value)
            return value
        async def get(self, kind, ident):
            return deepcopy(records.get((self.name, kind, ident)))
        async def list(self, kind, limit=500):
            return [deepcopy(v) for (name, k, _), v in records.items() if name == self.name and k == kind][:limit]
        async def create_once(self, kind, value, props=None):
            key = (self.name, kind, value["id"])
            if key in records:
                return False
            records[key] = deepcopy(value)
            return True
        async def claim(self, kind, ident, from_states, to_state, lease_seconds, owner):
            key = (self.name, kind, ident)
            item = records.get(key)
            if not item:
                return None
            if item.get("state") in from_states or (item.get("state") == to_state and item.get("lease_until", 0) < time.time()):
                item["state"] = to_state
                item["lease_until"] = time.time() + lease_seconds
                item["lease_owner"] = owner
                item["attempts"] = item.get("attempts", 0) + 1
                return item["attempts"]
            return None
        async def put_owned(self, kind, value, owner):
            key = (self.name, kind, value["id"])
            current = records.get(key)
            if not current or current.get("lease_owner") != owner or current.get("lease_until", 0) <= time.time():
                return False
            records[key] = deepcopy(value)
            return True
        async def link(self, a, rel, b):
            pass

    async def idle(*args): pass
    from workweave_api import store as store_module
    from workweave_api.outbox import IntegrationWorker
    monkeypatch.setattr(main_module, "Graph", MemoryGraph)
    monkeypatch.setattr(main_module, "Store", MemoryStore)
    monkeypatch.setattr(main_module, "company_store", lambda graph, ident: MemoryStore(graph, "ww_" + ident))
    monkeypatch.setattr(store_module, "company_store", lambda graph, ident: MemoryStore(graph, "ww_" + ident))
    monkeypatch.setattr(main_module.Engine, "start", idle)
    monkeypatch.setattr(main_module.Engine, "stop", idle)
    monkeypatch.setattr(IntegrationWorker, "start", idle)
    monkeypatch.setattr(IntegrationWorker, "stop", idle)
    return create_app(Settings(_env_file=None, graph_url="redis://unused:6379", ollama_url="http://localhost:1", data_dir=tmp_path, allowed_hosts=["local.test"]))


@pytest.mark.asyncio
async def test_no_write_before_approval_and_idempotent_reconcile(isolated_app):
    app = isolated_app

    clickup_posts = []
    slack_posts = []
    created_tasks = []

    def mock_transport(request):
        path = request.url.path
        # ClickUp List check
        if request.method == "GET" and path == "/api/v2/list/999888":
            return httpx.Response(200, json={"id": "999888", "name": "Sprint Tasks"})
        # ClickUp find_by_marker (task search)
        if request.method == "GET" and path == "/api/v2/list/999888/task":
            return httpx.Response(200, json={"tasks": created_tasks})
        # ClickUp Task Create
        if request.method == "POST" and path == "/api/v2/list/999888/task":
            data = json.loads(request.read().decode())
            clickup_posts.append(data)
            task_id = f"CU_{len(clickup_posts)}"
            task_record = {
                "id": task_id,
                "name": data["name"],
                "description": data["description"],
                "url": f"https://app.clickup.com/t/{task_id}",
            }
            created_tasks.append(task_record)
            return httpx.Response(200, json=task_record)
        # Slack postMessage
        if request.method == "POST" and "/api/chat.postMessage" in str(request.url):
            data = json.loads(request.read().decode())
            slack_posts.append(data)
            return httpx.Response(200, json={"ok": True, "ts": "1700000050.001"})
        # Slack conversations.replies
        if request.method == "GET" and "/api/conversations.replies" in str(request.url):
            return httpx.Response(200, json={"ok": True, "messages": []})
        return httpx.Response(200, json={"ok": True})

    app.state.router.http = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://local.test") as client:
            res = await client.post("/api/v1/auth/signup", json={"username": uid("usr"), "password": "password-123456", "company_name": "Idemp Co"})
            cid = res.json()["company_id"]
            from workweave_api.credentials import set_company_slack
            set_company_slack(app.state.router.vault, cid, "xoxb-synthetic", "synthetic-secret")

            # Configure ClickUp
            await client.put(f"/api/v1/companies/{cid}/integrations/clickup", json={"token": "pk_test", "list_id": "999888"})

            # Seed a pending proposal
            store = main_module.company_store(app.state.graph, cid)
            prop = {
                "id": "tp_12345",
                "title": "Fix delivery packaging bug",
                "description": "Packaging tape is out of stock",
                "channel": "C_DISPATCH",
                "thread_ts": "1700000001.002",
                "author_name": "Yusuf",
                "recommended_person_id": "person_ada",
                "recommended_person_name": "Ada Bello",
                "recommended_clickup_id": "112233",
                "state": "pending",
                "created_at": time.time(),
            }
            await store.put("proposal", prop)

            # 1. Verification: No external writes before approval
            await app.state.worker.tick()
            assert len(clickup_posts) == 0
            assert len(slack_posts) == 0

            # 2. Human approval
            approve_res = await client.post(f"/api/v1/companies/{cid}/proposals/tp_12345/approve", json={})
            assert approve_res.status_code == 200
            assert approve_res.json()["status"] == "approved"
            outbox_id = approve_res.json()["outbox_id"]

            # Double approve should be strictly idempotent (no duplicate outbox created)
            approve_again = await client.post(f"/api/v1/companies/{cid}/proposals/tp_12345/approve", json={})
            assert approve_again.status_code == 200
            assert approve_again.json()["outbox_id"] == outbox_id

            # 3. Worker tick 1: Creates ClickUp task and Slack reply
            await app.state.worker.tick()
            assert len(clickup_posts) == 1
            assert len(slack_posts) == 1
            assert clickup_posts[0]["name"] == "Fix delivery packaging bug"
            assert "⟦workweave:" in clickup_posts[0]["description"]

            outbox_entry = await store.get("outbox", outbox_id)
            assert outbox_entry["state"] == "done"
            assert outbox_entry["clickup_task_id"] == "CU_1"

            # 4. Crash simulation: Suppose worker crashed right after ClickUp POST,
            # and outbox item was left in state 'creating' with attempts=1
            outbox_entry["state"] = "creating"
            outbox_entry["lease_until"] = 0
            outbox_entry["attempts"] = 2
            outbox_entry.pop("clickup_task_id", None)
            await store.put("outbox", outbox_entry)

            # Run worker tick again: reconcile MUST find the existing task via marker and NOT call POST again!
            await app.state.worker.tick()
            assert len(clickup_posts) == 1  # EXACTLY ONE POST! No duplicate task!
            
            reclaimed = await store.get("outbox", outbox_id)
            assert reclaimed["state"] == "done"
            assert reclaimed["clickup_task_id"] == "CU_1"
