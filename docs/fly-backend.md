# Deploy the backend from the existing GitHub repository

Commit and push `workweave-api/fly.toml`, `workweave-api/Dockerfile`, and
`workweave-api/docker-entrypoint.py` with the current application source first.
No environment file or key belongs in the commit.

In Fly's GitHub launch screen:

| Field | Value |
| --- | --- |
| Repository | Your existing Workweave repository |
| Working directory | `workweave-api` |
| Config path | `fly.toml` (relative to the working directory) |
| Managed Postgres | Off; this backend uses your existing FalkorDB instance |

If GitHub shows another enclosing folder above `workweave-api`, prefix that
folder in the working-directory field. Do not use your Windows absolute path.
Fly supplies the app name and region on creation. Use one API Machine initially;
the application's background-worker and encrypted-vault writes are not designed
for multiple API Machines sharing credentials. The configuration requests a
512 MB shared-CPU Machine and 1 GB volume. Background work keeps the API running;
this configuration does not enable automatic stopping.

Supply these backend secrets privately through Fly's environment/secret setup:

| Name | Value from your own account |
| --- | --- |
| `WORKWEAVE_GRAPH_HOST` | FalkorDB hostname, without protocol or port |
| `WORKWEAVE_GRAPH_PORT` | FalkorDB connection port |
| `WORKWEAVE_GRAPH_USERNAME` | FalkorDB username |
| `WORKWEAVE_GRAPH_PASSWORD` | FalkorDB password |
| `WORKWEAVE_OLLAMA_CLOUD_KEY` | Ollama Cloud API key |
| `WORKWEAVE_ADMIN_PASSWORD` | A strong password for a NEW database's bootstrap administrator |

Do not add duplicate rows for variables already set in `fly.toml`. The cloud
model is `gemma4:31b`; TLS and secure cookies are enabled. Set graph TLS to match
the actual connection settings if your instance differs. Deploying against an
existing graph does not reset an existing administrator password or change any
workspace's saved provider preferences. Local vault credentials are not copied
to Fly: configure cloud keys in Fly separately.

The mounted volume keeps encrypted provider/OAuth credentials across releases.
The container initializes a new mount directory's ownership and starts the
application as user 10001, without reading existing credential files during init.
Keep the volume and its backups; do not delete it when redeploying.

After a successful launch, check `https://YOUR-API-APP.fly.dev/api/v1/health`.
Opening `/` is not a frontend test: this app only serves the backend. Its graph
connection is required during startup. The frontend is now deployed at
https://workweave-web.fly.dev. See [frontend setup](fly-frontend.md) for the exact
origin allowlist, proxy mode, and Google callback. Custom domains must be
explicitly added to the appropriate hostname/origin settings.

Document embeddings also need a reachable Ollama embedding server containing
`embeddinggemma:300m`, configured via `WORKWEAVE_OLLAMA_URL`. The default localhost
address does not provide an embedding server on Fly. Do not expose an
unauthenticated Ollama server publicly. Ollama Cloud chat alone does not supply
this embedding service; semantic search remains degraded until it is configured.
Keep this as a backend connectivity deployment until the frontend and embedding
service are ready.

References: [monorepo paths](https://docs.fly.io/launch/monorepo),
[Fly configuration](https://docs.fly.io/reference/configuration).
