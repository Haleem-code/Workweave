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

The latest suite passed **39 tests**, covering versions, impact exclusions,
ownership, recovery, tenant/private-history isolation, scoped MCP, provider policy,
model-name fallback, and browser origins. Provider tests use simulated HTTP; they
do not prove that a live cloud key or quota works.

## Frontend build

```bash
docker build -t workweave-web-check ./workweave-web
```

This runs the production build and TypeScript check. A separate isolated browser
test verified sign-in, HttpOnly cookies, saved preferences, a synthetic multipart
document import, and hostile-origin rejection. Public smoke checks verified
routing, negative authentication, Google callback configuration, and mobile layout;
they did not create production companies/users or complete Google consent.

## Prepare the demo

Follow the [company-pack guide](testing/README.md) for grounded questions. To show
the actual dependency traversal, first create a password-based test account, then:

```bash
python scripts/run-graph-demo.py --url http://localhost:8080
```

The helper prompts for your login and creates a new synthetic workspace through
the real API. It verifies SO1/SO2 and two saved review tasks. It does not require
a model key, print your password, or send external messages.

Use `--url https://workweave-web.fly.dev` only when intentionally creating this
synthetic workspace in your own hosted account. That is a real write. Google-only
accounts have no local password and cannot use this helper.

## Suggested video: about three minutes

| Time | Show | Explain |
| --- | --- | --- |
| 0:00–0:20 | A company workspace and its three documents | Workweave connects company knowledge and its sources. |
| 0:20–0:55 | Answer, opened citation, then missing fact | Grounded answers should distinguish known facts from unknowns. |
| 0:55–1:45 | Harbor Supply investigation and dependency path | SO1/SO2 need review; explain why SO3–SO5 are excluded. |
| 1:45–2:15 | Current owner, review task, completed status | This is an internal action with recorded evidence, not a customer message. |
| 2:15–2:40 | Refresh, History, and past decisions | Conversations, investigations, and actual outcomes persist. |
| 2:40–3:00 | Architecture and source query | Explain FalkorDB's central role; disclose AI assistance and existing work. |

Record the running behavior. A walkthrough is not the video deliverable, and a
deterministic graph result must not be presented as a live cloud-model response.
