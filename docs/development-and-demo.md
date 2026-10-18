# Development checks and recording walkthrough

## Backend tests without real secrets or company data

From the repository root, these PowerShell commands build a test image and use
a disposable database. No project `.env` is loaded into the test container. Use
fresh resource names if these names already belong to another run.

```powershell
docker build -t workweave-test-api ./workweave-api
docker network create workweave-test-network
docker run -d --name workweave-test-db --network workweave-test-network --network-alias test-db -e BROWSER=0 falkordb/falkordb@sha256:e2765e207e5ba4ee90e47ed31eb7491ad6dd3d42241c326e429375c02ad9882f
docker run --rm --user root --entrypoint sh --network workweave-test-network -e WORKWEAVE_TEST_GRAPH_URL=redis://test-db:6379 -e WORKWEAVE_GRAPH_URL=redis://test-db:6379 --mount "type=bind,source=${PWD}/workweave-api/tests,target=/app/tests,readonly" workweave-test-api -c "python -m pip install --quiet pytest pytest-asyncio && python -m pytest tests -q -p no:cacheprovider -o asyncio_mode=auto"
```

After this disposable run, remove only its resources:

```powershell
docker rm -f workweave-test-db
docker network rm workweave-test-network
```

The latest complete suite passed **57 tests**, covering versions, impact exclusions,
ownership, recovery, tenant/private-history isolation, scoped MCP, provider policy,
model-name fallback, browser origins, interrupted-example recovery, graph assignment,
atomic job claims, competing workers, uncertain ClickUp writes and Slack reply
retries. External provider/connector tests use controlled HTTP responses. The
separate live browser audit verifies an actual
Ollama Cloud answer; see [audit results](submission-audit.md).

## Frontend build

```bash
docker build -t workweave-web-check ./workweave-web
```

This runs the production build and TypeScript check. A separate isolated browser
test verified onboarding, sign-in, HttpOnly cookies, document imports, citations,
history, mobile layout, and saved task outcomes using fictional company data.
Google consent and hosted embeddings remain separate unverified paths.

## Prepare the demo

Follow the [company-pack guide](testing/README.md) for grounded questions. To show
the actual dependency traversal, use **Home → Try the example**. Preparation runs
as a saved background job in a separate synthetic workspace. Alternatively, create
a password-based test account and run:

```bash
python scripts/run-graph-demo.py --url http://localhost:8080
```

The helper prompts for your login and creates a new synthetic workspace through
the real API. It verifies SO1/SO2 and two saved review tasks. It does not require
a model key, print your password, or send external messages.

Use `--url https://workweave-web.fly.dev` only when intentionally creating this
synthetic workspace in your own hosted account. That is a real write. Google-only
accounts have no local password and cannot use this helper.

## Video: 3 minutes 50 seconds

The [complete video](media/workweave-demo-3m50s.mp4) and
[captions](media/workweave-demo-3m50s.srt) are included in the repository. The
README contains the current chapter timings. The older recording plan/script are
historical preparation notes, not the final video's integration status.

The recording shows onboarding, confirmed upload, answers and citations, the
Harbor Supply dependency investigation, exclusions, handoff, task outcome,
persisted memory, Slack authentication, integration setup and architecture.
Channel permissions remain pending and ClickUp is setup-only in this recording.
The graph example is explicitly deterministic; it is not presented as a live
cloud-model response.
