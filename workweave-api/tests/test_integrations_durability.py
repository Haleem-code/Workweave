import hashlib
import json
import time
import httpx
import pytest
from copy import deepcopy
from workweave_api import main as main_module
from workweave_api.config import Settings
from workweave_api.main import create_app
from workweave_api.store import uid
from tests.test_integrations_security import make_slack_headers


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
async def test_event_persistence_before_ack_and_deduplication(isolated_app):
    app = isolated_app

    def slack_mock(request):
        if request.url.path == "/api/auth.test":
            return httpx.Response(200, json={"ok": True, "team_id": "T123", "team": "Test Team", "app_id": "A123"})
        if request.url.path == "/api/users.info":
            return httpx.Response(200, json={"ok": True, "user": {"name": "ada", "profile": {"real_name": "Ada Bello"}}})
        return httpx.Response(200, json={"ok": True})

    app.state.router.http = httpx.AsyncClient(transport=httpx.MockTransport(slack_mock))

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://local.test") as client:
            res = await client.post("/api/v1/auth/signup", json={"username": uid("usr"), "password": "password-123456", "company_name": "Test Co"})
            cid = res.json()["company_id"]

            cfg = await client.put(f"/api/v1/companies/{cid}/integrations/slack", json={"token": "xoxb-test", "signing_secret": "sec123", "app_id": "A123"})
            route_id = cfg.json()["route_id"]

            await client.put(f"/api/v1/companies/{cid}/integrations/slack/channels", json={"channels": ["C_OPS"]})

            event_payload = {
                "type": "event_callback",
                "team_id": "T123",
                "api_app_id": "A123",
                "event_id": "Ev_TEST_001",
                "event": {
                    "type": "message",
                    "channel": "C_OPS",
                    "user": "U123",
                    "text": "Please fix invoice export for Acme by Friday",
                    "ts": "1700000000.001",
                }
            }
            body = json.dumps(event_payload).encode()
            headers = make_slack_headers("sec123", body)

            # 1. Post event: persisted=True returned
            res1 = await client.post(f"/api/v1/integrations/slack/events/{route_id}", content=body, headers=headers)
            assert res1.status_code == 200
            assert res1.json()["persisted"] is True

            # 2. Duplicate event delivery: duplicate rejected/deduped gracefully (persisted=False)
            res2 = await client.post(f"/api/v1/integrations/slack/events/{route_id}", content=body, headers=headers)
            assert res2.status_code == 200
            assert res2.json()["persisted"] is False

            # Verify store has only 1 slack_event
            store = main_module.company_store(app.state.graph, cid)
            events = await store.list("slack_event")
            assert len(events) == 1
            assert events[0]["state"] == "received"
            assert events[0]["author_name"] == "U123"  # No Slack HTTP calls before ACK.

            # 3. Simulate worker triaging the event
            await app.state.worker.tick()
            events_after = await store.list("slack_event")
            assert events_after[0]["author_name"] == "Ada Bello"
            assert events_after[0]["state"] == "processed"

            proposals = await store.list("proposal")
            assert len(proposals) == 1
            assert "invoice" in proposals[0]["title"].lower() or "invoice" in proposals[0]["description"].lower()
            assert proposals[0]["state"] == "pending"


@pytest.mark.asyncio
async def test_lease_expiry_and_worker_reclaim(isolated_app):
    app = isolated_app
    async with app.router.lifespan_context(app):
        store = main_module.company_store(app.state.graph, "comp_test")
        ev_id = "se_crash_test"
        await store.put("slack_event", {
            "id": ev_id,
            "state": "triaging",
            "lease_until": time.time() - 10,  # Expired lease from crashed worker
            "attempts": 1,
            "text": "Can someone update customer records?",
            "channel": "C1",
            "ts": "1.0",
        })

        # Claim should succeed because lease expired
        claimed_attempts = await store.claim("slack_event", ev_id, ["received"], "triaging", 60, "new_worker")
        assert claimed_attempts == 2

        updated = await store.get("slack_event", ev_id)
        assert updated["state"] == "triaging"
        assert updated["attempts"] == 2
        assert updated["lease_owner"] == "new_worker"
