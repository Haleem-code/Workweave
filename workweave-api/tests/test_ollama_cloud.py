import json
import time

import httpx
import pytest
from pydantic import ValidationError

from workweave_api.config import Settings
from workweave_api.models import ProviderPolicy
from workweave_api.providers import ProviderError, Router


MESSAGES = [{"role": "user", "content": "Who owns the delivery?"}]
CLOUD_POLICY = {"allowed": ["ollama_cloud"], "cloud_consent": True}


def config(tmp_path, **changes):
    return Settings(_env_file=None, data_dir=tmp_path, ollama_cloud_key="synthetic-test-key", **changes)


@pytest.mark.asyncio
async def test_cloud_auth_tools_and_embeddings_use_separate_destinations(tmp_path):
    seen = []
    def respond(request):
        seen.append(request)
        if request.url.path == "/api/embed":
            assert request.url.host == "embeddings.invalid"
            assert "authorization" not in request.headers
            assert json.loads(request.content)["model"] == "embeddinggemma:300m"
            return httpx.Response(200, json={"embeddings": [[0.1] * 768]})
        assert str(request.url) == "https://ollama.com/api/chat"
        assert request.headers["authorization"] == "Bearer synthetic-test-key"
        body = json.loads(request.content)
        assert body["model"] == "gemma4:31b" and body["stream"] is True
        assert body["think"] is False
        assert body["tools"][0]["function"]["name"] == "find_owner"
        # The model requests a graph tool; preserve typed arguments for the agent.
        return httpx.Response(200, text=json.dumps({"message": {"tool_calls": [{"function": {"name": "find_owner", "arguments": {"entity_id": "DL-301"}}}]}}) + '\n' + json.dumps({"done": True, "prompt_eval_count": 25, "eval_count": 10}) + '\n')
    router = Router(config(tmp_path, ollama_url="http://embeddings.invalid:11434"), httpx.MockTransport(respond))
    try:
        result = await router.generate(MESSAGES, CLOUD_POLICY, [{"name": "find_owner", "parameters": {"type": "object"}}])
        assert result["provider"] == "ollama_cloud"
        assert result["tool_calls"][0]["arguments"] == {"entity_id": "DL-301"}
        assert result["usage"] == {"input_tokens": 25, "output_tokens": 10}
        assert len(await router.embed("Synthetic delivery evidence")) == 768
        assert len(seen) == 2  # No local model discovery before cloud generation.
    finally:
        await router.close()


@pytest.mark.asyncio
async def test_ollama_cloud_tool_results_and_cross_provider_handoff(tmp_path):
    bodies = []
    def respond(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, text='{"message":{"content":"Ada"},"done":true}\n')
    router = Router(config(tmp_path), httpx.MockTransport(respond))
    history = MESSAGES + [
        {"role": "assistant", "native_provider": "ollama_cloud", "native_parts": [{"thinking": "opaque fixture continuation"}], "tool_calls": [{"id": "c1", "function": {"name": "find_owner", "arguments": '{"entity_id":"DL-301"}'}}]},
        {"role": "tool", "tool_call_id": "c1", "name": "find_owner", "content": "Ada owns DL-301; evidence E1"},
    ]
    try:
        await router.call("ollama_cloud", history, [])
        messages = bodies[-1]["messages"]
        assert messages[-1] == {"role": "tool", "tool_name": "find_owner", "content": "Ada owns DL-301; evidence E1"}
        assert messages[-2]["tool_calls"][0]["function"]["arguments"] == {"entity_id": "DL-301"}
        assert messages[-2]["thinking"] == "opaque fixture continuation"
        history[-2]["native_provider"] = "groq"
        await router.call("ollama_cloud", history, [])
        assert bodies[-1]["messages"][-1]["role"] == "user"
        assert "evidence E1" in bodies[-1]["messages"][-1]["content"]
        assert "opaque fixture continuation" not in json.dumps(bodies[-1])
    finally:
        await router.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("policy", [
    {"allowed": ["ollama_cloud"], "cloud_consent": False},
    {"allowed": ["ollama_cloud"], "cloud_consent": True, "local_only": True},
    {"allowed": ["ollama"], "cloud_consent": True, "local_only": False},
])
async def test_cloud_cannot_bypass_workspace_policy(tmp_path, policy):
    def respond(request):
        assert request.url.host != "ollama.com", "Cloud received context without permission"
        return httpx.Response(200, json={"models": []})
    router = Router(config(tmp_path), httpx.MockTransport(respond))
    try:
        with pytest.raises(ProviderError):
            await router.generate(MESSAGES, policy)
    finally:
        await router.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("status,kind", [(401, "authentication"), (429, "rate_limit")])
async def test_cloud_failures_do_not_repeat_requests_immediately(tmp_path, status, kind):
    seen = []
    def respond(request):
        seen.append(request)
        return httpx.Response(status, headers={"Retry-After": "45"})
    router = Router(config(tmp_path), httpx.MockTransport(respond))
    try:
        for _ in range(2):
            with pytest.raises(ProviderError):
                await router.generate(MESSAGES, CLOUD_POLICY)
        assert len(seen) == 1
        if kind == "authentication":
            assert "ollama_cloud" in router.disabled
            router.set_key("ollama_cloud", "replacement-test-key")
            assert "ollama_cloud" not in router.disabled
        else:
            assert router.cooldown["ollama_cloud"] > time.monotonic()
    finally:
        await router.close()


@pytest.mark.asyncio
async def test_cloud_incomplete_stream_is_not_published(tmp_path):
    router = Router(config(tmp_path), httpx.MockTransport(lambda _: httpx.Response(200, text='{"message":{"content":"unfinished answer"}}\n')))
    try:
        with pytest.raises(ProviderError, match="invalid_response"):
            await router.call("ollama_cloud", MESSAGES, [])
    finally:
        await router.close()


@pytest.mark.asyncio
async def test_cloud_key_stays_private_and_survives_restart(tmp_path):
    settings = config(tmp_path)
    assert "synthetic-test-key" not in repr(settings)
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={"models": []}))
    router = Router(settings, transport)
    try:
        router.set_key("ollama_cloud", "vault-test-key")
        assert "vault-test-key" not in (tmp_path / "credentials.enc").read_text()
        status = await router.readiness()
        assert "vault-test-key" not in json.dumps(status)
        assert next(p for p in status if p["id"] == "ollama_cloud")["ready"] is True
    finally:
        await router.close()
    resumed = Router(settings, transport)
    try:
        assert resumed.key("ollama_cloud") == "vault-test-key"
    finally:
        await resumed.close()


def test_new_workspace_cloud_default_and_exclusive_processing_modes():
    assert ProviderPolicy().model_dump() == {
        "allowed": ["ollama_cloud"], "cloud_consent": True, "local_only": False,
    }
    with pytest.raises(ValidationError, match="both cannot be enabled"):
        ProviderPolicy(local_only=True, cloud_consent=True)
    assert ProviderPolicy(allowed=["ollama"], local_only=True, cloud_consent=False).local_only


@pytest.mark.asyncio
@pytest.mark.parametrize("configured,expected,warning", [
    ("gemma4:31b", "gemma4:31b", False),
    ("https://ollama.com/gemma4:31b", "gemma4:31b", True),
    ("", "gemma4:31b", True),
    (" gpt-oss:20b ", "gpt-oss:20b", False),
])
async def test_cloud_model_status_matches_outbound_request(tmp_path, configured, expected, warning):
    bodies = []
    def respond(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": []})
        bodies.append(json.loads(request.content))
        return httpx.Response(200, text='{"message":{"content":"Supported answer"},"done":true}\n')
    router = Router(config(tmp_path, ollama_cloud_model=configured), httpx.MockTransport(respond))
    try:
        status = next(p for p in await router.readiness() if p["id"] == "ollama_cloud")
        assert status["model"] == expected
        assert bool(status["configuration_warning"]) is warning
        assert "googleusercontent.com" not in json.dumps(status)
        await router.generate(MESSAGES, ProviderPolicy().model_dump())
        assert bodies[0]["model"] == expected
    finally:
        await router.close()


@pytest.mark.asyncio
async def test_default_cloud_missing_key_does_not_send_to_another_provider(tmp_path):
    def unexpected(request):
        pytest.fail("No request should be sent when the only permitted provider has no key")
    router = Router(Settings(_env_file=None, data_dir=tmp_path, ollama_cloud_key="", groq_key="synthetic-groq-key"), httpx.MockTransport(unexpected))
    try:
        with pytest.raises(ProviderError, match="No permitted provider"):
            await router.generate(MESSAGES, ProviderPolicy().model_dump())
    finally:
        await router.close()
