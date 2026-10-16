# Ollama Cloud for Workweave

Ollama Cloud is a separate answer provider (`ollama_cloud`). It calls `https://ollama.com/api/chat` from the backend with Bearer authentication. It uses the same evidence, graph tools, tool receipts, and persisted conversations as the other providers. The default cloud model is `gemma4:31b`; the hosting environment can override `WORKWEAVE_OLLAMA_CLOUD_MODEL` with a currently supported model name.

New workspaces select **Ollama Cloud** by default, with cloud processing enabled. The application tries Ollama Cloud first, then configured Groq, Gemini, and self-hosted Ollama fallbacks. Signup discloses cloud processing and fallback providers. Existing workspaces retain their saved processing preferences; select Ollama Cloud once in Settings to switch. Embedding settings remain unchanged.

Model settings must contain a model identifier, not a URL. Malformed values (for example, pasted URL text after the model name) fall back to `gemma4:31b` for both displayed status and outbound requests, with a configuration warning in Settings. The application does not rewrite your environment file. Syntactically valid names still need to be available on Ollama Cloud.

## Connect on this computer without changing .env

1. Create an API key at [Ollama API keys](https://ollama.com/settings/keys). Keep it out of chat and your repository.
2. With the updated Workweave Docker API running, open a terminal in the project folder and run:

   ```powershell
   python scripts/configure-ollama-cloud.py
   ```

   Paste the key at the hidden prompt. The helper stores it in the existing encrypted backend vault, passes it through stdin, and leaves `.env` unchanged. Use `--compose docker-compose.yml` only if you run the local-database compose stack instead.
3. Open Workweave **Settings â†’ AI answers**, select **Ollama Cloud**, and click **Save preferences**. It is already selected for new workspaces. Choose **Self-hosted Ollama** to exclude cloud answer providers, or **Custom providers** for explicit fallback choices. These three modes are mutually exclusive.
4. Ask a question supported by your uploaded documents. Inspect the saved run's provider. A direct source fact may be answered without any model; use a question requiring synthesis to verify an actual Cloud call. A configured key is not a live connectivity test.

Alternatively, the platform administrator can save the key through the Ollama Cloud row in Settings. Company administrators may change their own processing policy but cannot change credentials shared by every workspace.

The vault key and encrypted credentials are both in the backend data volume. Protect and persist that volume. A saved vault key takes precedence over the hosting environment key. If replacing a key after a rejected authentication attempt using the helper, restart only the API to clear the process's disabled-provider state. Saving through the administrator UI clears it immediately.

## Deploying later

Set `WORKWEAVE_OLLAMA_CLOUD_KEY` as a **backend deployment secret**, never a public frontend variable. The key is sent only to the fixed Ollama HTTPS endpoint. Its value is excluded from provider status, graph data, prompts, and logs.

Document embeddings still use `WORKWEAVE_OLLAMA_URL` and `embeddinggemma:300m` (768 dimensions). Ollama Cloud's model list currently does not include that embedding model. Do **not** change `WORKWEAVE_OLLAMA_URL` to `https://ollama.com`: that is not a replacement embedding service. A public deployment still needs a reachable self-hosted embedding service, or a separately implemented embedding provider with a deliberate reindexing migration. Equal vector dimensions alone do not make two models compatible.

No cloud account, subscription, live API key, or public deployment is created by this change. Runtime pricing and model availability depend on your Ollama account. Adapter tests use simulated external HTTP responses; a live authenticated test requires your key and permitted workspace context.

References checked October 16, 2026: [Ollama Cloud](https://docs.ollama.com/cloud), [tool calling](https://docs.ollama.com/capabilities/tool-calling), [cloud models](https://ollama.com/api/tags), [pricing](https://ollama.com/pricing).
