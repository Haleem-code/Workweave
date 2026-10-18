import hashlib
import hmac
import time
import httpx
import pytest
from copy import deepcopy
from workweave_api import main as main_module
from workweave_api.config import Settings
from workweave_api.main import create_app
from workweave_api.store import uid
from workweave_api.slack_client import verify_signature


def make_slack_headers(signing_secret: str, raw_body: bytes, timestamp: float | None = None):
    ts = str(int(timestamp if timestamp is not None else time.time()))
    basestring = f"v0:{ts}:".encode("utf-8") + raw_body
    sig = "v0=" + hmac.new(signing_secret.encode("utf-8"), basestring, hashlib.sha256).hexdigest()
    return {
        "x-slack-request-timestamp": ts,
        "x-slack-signature": sig,
        "Content-Type": "application/json",
    }


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
async def test_signature_verification_logic():
    secret = "test_signing_secret_12345"
    body = b'{"type":"event_callback","event":{"text":"hello"}}'
    now_ts = time.time()

    headers = make_slack_headers(secret, body, now_ts)
    assert verify_signature(body, headers["x-slack-request-timestamp"], headers["x-slack-signature"], secret)

    # Tampered body fails
    assert not verify_signature(body + b"tampered", headers["x-slack-request-timestamp"], headers["x-slack-signature"], secret)

    # Stale timestamp (> 5 min) fails
    stale_headers = make_slack_headers(secret, body, now_ts - 305)
    assert not verify_signature(body, stale_headers["x-slack-request-timestamp"], stale_headers["x-slack-signature"], secret)

    # Wrong secret fails
    assert not verify_signature(body, headers["x-slack-request-timestamp"], headers["x-slack-signature"], "wrong_secret")


@pytest.mark.asyncio
async def test_webhook_routing_and_tenant_isolation(isolated_app):
    app = isolated_app

    def slack_mock(request):
        if request.url.path == "/api/auth.test":
            auth_header = request.headers.get("authorization", "")
            if "token_a" in auth_header:
                return httpx.Response(200, json={"ok": True, "team_id": "T_AAA", "team": "Team A", "app_id": "A_AAA"})
            return httpx.Response(200, json={"ok": True, "team_id": "T_AAA", "team": "Team B", "app_id": "A_BBB"})
        return httpx.Response(200, json={"ok": True})

    app.state.router.http = httpx.AsyncClient(transport=httpx.MockTransport(slack_mock))

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://local.test") as client_a, \
                   httpx.AsyncClient(transport=transport, base_url="http://local.test") as client_b, \
                   httpx.AsyncClient(transport=transport, base_url="http://local.test") as client:
            # 1. Signup Company A with client_a and Company B with client_b
            res_a = await client_a.post("/api/v1/auth/signup", json={"username": uid("usrA"), "password": "password-123456", "company_name": "Company A"})
            comp_a = res_a.json()["company_id"]

            res_b = await client_b.post("/api/v1/auth/signup", json={"username": uid("usrB"), "password": "password-123456", "company_name": "Company B"})
            comp_b = res_b.json()["company_id"]

            # Configure Slack for Company A
            cfg_a = await client_a.put(f"/api/v1/companies/{comp_a}/integrations/slack", json={"token": "xoxb-token_a", "signing_secret": "secret_aaa", "app_id": "A_AAA"})
            assert cfg_a.status_code == 200
            route_a = cfg_a.json()["route_id"]

            # Configure Slack for Company B
            cfg_b = await client_b.put(f"/api/v1/companies/{comp_b}/integrations/slack", json={"token": "xoxb-token_b", "signing_secret": "secret_bbb", "app_id": "A_BBB"})
            assert cfg_b.status_code == 200
            route_b = cfg_b.json()["route_id"]

            # Status endpoint NEVER reveals secrets
            status_a = await client_a.get(f"/api/v1/companies/{comp_a}/integrations/status")
            assert "secret_aaa" not in status_a.text
            assert "xoxb-token_a" not in status_a.text
            assert status_a.json()["slack"]["configured"] is True

            # Webhook on Route A signed with Company B's secret fails with 401
            body = b'{"type":"url_verification","challenge":"chal123"}'
            bad_headers = make_slack_headers("secret_bbb", body)
            res = await client.post(f"/api/v1/integrations/slack/events/{route_a}", content=body, headers=bad_headers)
            assert res.status_code == 401

            # Webhook on Route A signed with Company A's secret succeeds
            good_headers = make_slack_headers("secret_aaa", body)
            res = await client.post(f"/api/v1/integrations/slack/events/{route_a}", content=body, headers=good_headers)
            assert res.status_code == 200
            assert res.json()["challenge"] == "chal123"

            # Team mismatch rejection
            event_body = b'{"type":"event_callback","team_id":"T_OTHER","event":{"type":"message","channel":"C1","text":"do task"}}'
            hdrs = make_slack_headers("secret_aaa", event_body)
            res = await client.post(f"/api/v1/integrations/slack/events/{route_a}", content=event_body, headers=hdrs)
            assert res.status_code == 403

            # Exclusive channel claims
            claim_res = await client_a.put(f"/api/v1/companies/{comp_a}/integrations/slack/channels", json={"channels": ["C_SHARED_01"]})
            assert claim_res.status_code == 200

            # Company B attempting to claim Company A's channel gets 409 Conflict
            conflict_res = await client_b.put(f"/api/v1/companies/{comp_b}/integrations/slack/channels", json={"channels": ["C_SHARED_01"]})
            assert conflict_res.status_code == 409
