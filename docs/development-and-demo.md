# Development checks and recording walkthrough

## Backend tests without real secrets or company data

From the repository root, these PowerShell commands build a test image and use
a disposable database. No project `.env` is loaded into the test container. Use
fresh resource names if these names already belong to another run.

```powershell
docker build -t workweave-test-api ./workweave-api
docker network create workweave-test-network
docker run -d --name workweave-test-db --network workweave-test-network --network-alias test-db -e BROWSER=0 falkordb/falkordb@sha256:e2765e207e5ba4ee90e47ed31eb7491ad6dd3d42241c326e429375c02ad9882f
docker run --rm --user root --entrypoint sh --network workweave-test-network -e WORKWEAVE_TEST_GRAPH_URL=redis://test-db:6379 -e WORKWEAVE_GRAPH_URL=redis://test-db:6379 --mount "type=bind,source=${PWD}/workweave-api/tests,target=/app/tests,readonly" workweave-test-api -c "python -m pip install --quiet pytest pytest-asyncio && python -m pytest tests -q -p no:cacheprovider"
```

After this disposable run, remove only its resources:

```powershell
docker rm -f workweave-test-db
docker network rm workweave-test-network
```

The latest suite passed **40 tests**, covering versions, impact exclusions,
ownership, recovery, tenant/private-history isolation, scoped MCP, provider policy,
model-name fallback, browser origins, and interrupted-example recovery. Provider
unit tests use simulated HTTP. The separate live browser audit verifies an actual
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

## Video: 3 minutes 30 seconds

Use the [timed recording plan](submission-recording-plan.md) and
[narration draft](submission-video-script.md). Show onboarding, confirmed upload,
an answer and citation, the Harbor Supply dependency investigation, exclusions,
handoff, a task outcome, persisted memory, and the real FalkorDB query. Slack and
ClickUp synchronization is a roadmap item; their prepared synthetic data does not
demonstrate a live connection.

Record the running behavior. A walkthrough is not the video deliverable, and a
deterministic graph result must not be presented as a live cloud-model response.
