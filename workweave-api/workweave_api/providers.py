import asyncio
import json
import os
import time
from pathlib import Path
import httpx
from cryptography.fernet import Fernet
from pydantic import SecretStr
from .config import Settings
from .store import uid

PROVIDER_ORDER = ("groq", "gemini", "ollama_cloud", "ollama")
PROVIDER_LABELS = {"groq": "Groq", "gemini": "Gemini", "ollama_cloud": "Ollama Cloud", "ollama": "Ollama (self-hosted)"}
OLLAMA_CLOUD_CHAT_URL = "https://ollama.com/api/chat"


class ProviderError(RuntimeError):
    def __init__(self, provider: str, kind: str, retry_after: float = 0):
        super().__init__(f"{provider}: {kind}")
        self.provider, self.kind, self.retry_after = provider, kind, retry_after


class Vault:
    """Encrypted local credential file. Host filesystem permissions remain essential."""
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.file = directory / "credentials.enc"
        keyfile = directory / "credentials.key"
        if not keyfile.exists():
            with keyfile.open("xb") as f:
                f.write(Fernet.generate_key())
            os.chmod(keyfile, 0o600)
        self.cipher = Fernet(keyfile.read_bytes())

    def read(self) -> dict:
        return json.loads(self.cipher.decrypt(self.file.read_bytes())) if self.file.exists() else {}

    def set(self, key: str, value):
        data = self.read()
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
        temporary = self.file.with_suffix(".tmp")
        temporary.write_bytes(self.cipher.encrypt(json.dumps(data).encode()))
        os.chmod(temporary, 0o600)
        temporary.replace(self.file)


class Router:
    def __init__(self, config: Settings, transport=None):
        self.config = config
        self.vault = Vault(config.data_dir)
        self.http = httpx.AsyncClient(timeout=httpx.Timeout(90, connect=10), transport=transport)
        self.lock = asyncio.Lock()
        self.cooldown: dict[str, float] = {}
        self.disabled: set[str] = set()
        self.last_request: dict[str, float] = {}

    def key(self, provider: str):
        value = self.vault.read().get(provider) or getattr(self.config, provider + "_key", "")
        return value.get_secret_value() if isinstance(value, SecretStr) else value

    def model(self, provider: str) -> str:
        return self.config.effective_ollama_cloud_model if provider == "ollama_cloud" else getattr(self.config, provider + "_model")

    async def readiness(self):
        local_models = []
        try:
            response = await self.http.get(self.config.ollama_url + "/api/tags", timeout=3)
            response.raise_for_status()
            local_models = [x["name"] for x in response.json().get("models", [])]
        except (httpx.HTTPError, ValueError):
            pass
        return [{"id": p, "label": PROVIDER_LABELS[p], "model": self.model(p),
                 "configuration_warning": "Invalid cloud model setting. Using gemma4:31b." if p == "ollama_cloud" and not self.config.ollama_cloud_model_valid else "",
                 "ready": (getattr(self.config, p + "_model") in local_models) if p == "ollama" else bool(self.key(p)),
                 "disabled": p in self.disabled, "cooldown_seconds": max(0, round(self.cooldown.get(p, 0) - time.monotonic())),
                 "destination": "Configured Ollama service" if p == "ollama" else "Ollama Cloud" if p == "ollama_cloud" else p.title() + " cloud"}
                for p in PROVIDER_ORDER]

    def set_key(self, provider: str, key: str):
        if provider not in ("groq", "gemini", "ollama_cloud"):
            raise ValueError("Unknown cloud provider")
        self.vault.set(provider, key.strip() or None)
        self.disabled.discard(provider)
        self.cooldown.pop(provider, None)

    async def embed(self, text: str) -> list[float]:
        response = await self.http.post(self.config.ollama_url + "/api/embed", json={
            "model": self.config.embedding_model, "input": text, "truncate": False}, timeout=40)
        response.raise_for_status()
        vector = response.json()["embeddings"][0]
        if len(vector) != 768:
            raise ValueError("Embedding model must return 768 dimensions; reindex before changing models")
        return vector

    async def generate(self, messages: list[dict], policy: dict, tools: list[dict] | None = None, notify=None):
        failures = []
        async with self.lock:
            for provider in PROVIDER_ORDER:
                if provider not in policy.get("allowed", []):
                    continue
                if provider != "ollama" and (policy.get("local_only") or not policy.get("cloud_consent")):
                    continue
                if provider in self.disabled or time.monotonic() < self.cooldown.get(provider, 0):
                    continue
                if provider != "ollama" and not self.key(provider):
                    continue
                if provider == "ollama":
                    readiness = await self.readiness()
                    if not next(p["ready"] for p in readiness if p["id"] == "ollama"):
                        failures.append("ollama: local answer model is missing or the service is unavailable")
                        continue
                for attempt in range(2):
                    # Actual rate-limit responses set cooldowns below. Do not impose
                    # a free-tier assumption on every user's paid or free account.
                    interval = 0
                    wait = interval - (time.monotonic() - self.last_request.get(provider, 0))
                    if wait > 0:
                        if notify:
                            await notify("provider.wait", {"provider": provider, "seconds": round(wait)})
                        await asyncio.sleep(wait)
                    self.last_request[provider] = time.monotonic()
                    try:
                        if notify:
                            await notify("provider.selected", {"provider": provider, "attempt": attempt + 1})
                        try:
                            result = await asyncio.wait_for(self.call(provider, messages, tools or []), timeout=60 if provider == 'ollama' else 30)
                        except TimeoutError as exc:
                            raise ProviderError(provider, 'timeout') from exc
                        result["provider"] = provider
                        return result
                    except ProviderError as exc:
                        failures.append(str(exc))
                        if notify:
                            await notify("provider.retry", {"provider": provider, "reason": exc.kind})
                        if exc.kind == "authentication":
                            self.disabled.add(provider)
                            break
                        if exc.kind == "rate_limit":
                            self.cooldown[provider] = time.monotonic() + max(exc.retry_after, 30)
                            break
                        if provider == 'ollama' and exc.kind == 'timeout':
                            # Repeating a slow CPU generation immediately adds
                            # another full minute with little chance of recovery.
                            break
                        if exc.kind not in ("unavailable", "timeout", "invalid_response"):
                            break
                        if attempt == 0:
                            await asyncio.sleep(1)
        raise ProviderError("all providers", "; ".join(failures) or "No permitted provider is ready. Configure a key or download the local model.")

    async def call(self, provider, messages, tools):
        if provider not in PROVIDER_ORDER:
            raise ProviderError(provider, "configuration")
        is_ollama = provider in ("ollama", "ollama_cloud")
        # Only normalized, bounded evidence and user messages reach a provider.
        # Provider-specific call signatures do not survive a provider switch.
        portable = []
        native = None
        for message in messages:
            if message.get("tool_calls"):
                native = message.get("native_provider")
                if native != provider:
                    portable.append({"role": "assistant", "content": "Completed tool requests: " + json.dumps(message["tool_calls"])})
                    continue
            if message["role"] == "tool" and native != provider:
                portable.append({"role": "user", "content": "Already completed tool result for " + message["name"] + ": " + message["content"]})
                continue
            portable.append(message)
        messages = portable
        model = self.model(provider)
        headers = {}
        if provider == "groq" or is_ollama:
            clean = []
            for m in messages:
                item = {k: m[k] for k in ("role", "content", "tool_calls", "tool_call_id", "name") if k in m}
                if is_ollama and "tool_calls" in item:
                    item["tool_calls"] = [{"function": {"name": x["function"]["name"], "arguments": json.loads(x["function"]["arguments"])}} for x in item["tool_calls"]]
                if is_ollama:
                    if m.get("native_provider") == provider:
                        thinking = "".join(p.get("thinking", "") for p in m.get("native_parts", []))
                        if thinking:
                            item["thinking"] = thinking
                    item.pop("tool_call_id", None)
                    if item.get("role") == "tool":
                        item["tool_name"] = item.pop("name", "")
                clean.append(item)
            payload = {"model": model, "messages": clean, "stream": True}
            if tools:
                payload["tools"] = [{"type": "function", "function": t} for t in tools]
            if provider == "groq":
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers["Authorization"] = "Bearer " + self.key(provider)
                payload.update(max_completion_tokens=600, stream_options={"include_usage": True})
            elif provider == "ollama_cloud":
                # Separate, fixed HTTPS destination: the cloud key can never be
                # sent to the self-hosted chat/embedding URL.
                url = OLLAMA_CLOUD_CHAT_URL
                headers["Authorization"] = "Bearer " + self.key(provider)
                payload["options"] = {"num_predict": 600}
                # Gemma supports disabling thinking for these bounded evidence
                # answers. Other models retain their own supported default.
                if model.split(":", 1)[0] == "gemma4":
                    payload["think"] = False
            else:
                url = self.config.ollama_url + "/api/chat"
                payload["options"] = {"num_predict": 600, "num_ctx": 8192}
                payload["think"] = False
        else:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse"
            headers["x-goog-api-key"] = self.key(provider)
            contents = []
            for m in messages:
                if m["role"] == "system":
                    continue
                if m["role"] == "tool":
                    parts = [{"functionResponse": {"name": m["name"], "response": {"result": m["content"]}}}]
                elif m.get("native_provider") == "gemini" and m.get("native_parts"):
                    parts = m["native_parts"]
                elif m.get("tool_calls"):
                    parts = [{"text": "Executed tools: " + json.dumps(m["tool_calls"])}]
                else:
                    parts = [{"text": m.get("content", "") or "Continue"}]
                contents.append({"role": "model" if m["role"] == "assistant" else "user", "parts": parts})
            payload = {"contents": contents, "systemInstruction": {"parts": [{"text": "\n".join(m["content"] for m in messages if m["role"] == "system")}]}, "generationConfig": {"maxOutputTokens": 600}}
            if tools:
                payload["tools"] = [{"functionDeclarations": tools}]
        text_parts, calls, native_parts, usage = [], {}, [], {}
        thinking_parts = []
        finished = False
        try:
            async with self.http.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code >= 400:
                    kind = "authentication" if response.status_code in (401, 403) else "rate_limit" if response.status_code == 429 else "unavailable" if response.status_code >= 500 else "configuration"
                    try:
                        retry = float(response.headers.get("retry-after", "30"))
                    except ValueError:
                        retry = 30
                    raise ProviderError(provider, kind, retry)
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or line.startswith(":") or line == "data: [DONE]":
                        continue
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    elif not is_ollama:
                        continue
                    item = json.loads(line)
                    if item.get("error"):
                        raise ProviderError(provider, "unavailable")
                    if provider == "groq":
                        finished = finished or bool((item.get("choices") or [{}])[0].get("finish_reason"))
                        delta = (item.get("choices") or [{}])[0].get("delta", {})
                        text_parts.append(delta.get("content") or "")
                        usage = item.get("usage") or usage
                        for tc in delta.get("tool_calls", []):
                            entry = calls.setdefault(tc["index"], {"id": "", "name": "", "arguments": ""})
                            entry["id"] += tc.get("id", "")
                            fn = tc.get("function", {})
                            entry["name"] += fn.get("name", "")
                            entry["arguments"] += fn.get("arguments", "")
                    elif is_ollama:
                        msg = item.get("message", {})
                        if msg.get("thinking"):
                            thinking_parts.append(msg["thinking"])
                        text_parts.append(msg.get("content", ""))
                        for tc in msg.get("tool_calls", []):
                            fn = tc["function"]
                            calls[len(calls)] = {"id": uid("call"), "name": fn["name"], "arguments": json.dumps(fn.get("arguments", {}))}
                        if item.get("done"):
                            finished = True
                            usage = {"input_tokens": item.get("prompt_eval_count", 0), "output_tokens": item.get("eval_count", 0)}
                    else:
                        finished = finished or bool((item.get("candidates") or [{}])[0].get("finishReason"))
                        parts = (item.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
                        native_parts.extend(parts)
                        for part in parts:
                            if not part.get("thought"):
                                text_parts.append(part.get("text", ""))
                            if "functionCall" in part:
                                fn = part["functionCall"]
                                calls[len(calls)] = {"id": uid("call"), "name": fn["name"], "arguments": json.dumps(fn.get("args", {}))}
                        usage = item.get("usageMetadata", usage)
        except httpx.TimeoutException as exc:
            raise ProviderError(provider, "timeout") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(provider, "unavailable") from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError(provider, "invalid_response") from exc
        if not finished or (not any(text_parts) and not calls):
            raise ProviderError(provider, "invalid_response")
        try:
            normalized = [{"id": x["id"] or uid("call"), "name": x["name"], "arguments": json.loads(x["arguments"] or "{}")} for x in calls.values()]
        except (ValueError, TypeError) as exc:
            raise ProviderError(provider, "invalid_response") from exc
        # Keep model-native continuation state only inside the current agent
        # loop. It is neither user-facing evidence nor cross-provider context.
        if is_ollama and thinking_parts:
            native_parts = [{"thinking": "".join(thinking_parts)}]
        return {"text": "".join(text_parts), "tool_calls": normalized, "native_parts": native_parts, "usage": usage}

    async def close(self):
        await self.http.aclose()
