# Submission disclosure and readiness

**Named tracks: Company Brain; Agent Memory and Coordination; Agents That Act on
Connected Data.** Memory and coordination are supported by persisted outcomes,
checkpoints and internal handoffs. Connected-data actions are supported by graph
investigations that create internal review tasks. Neither claim requires a
completed live Slack-to-ClickUp dispatch or high-throughput autonomous agents.

## Build history

The prior README described a pre-event prototype built **October 10, 2026** and
reliability/interface work on **October 14**. It already described graph storage,
retrieval, versioned evidence, MCP tools, investigations, tasks, and memory.
This document preserves that previously disclosed history; it is not independent
verification of the dates or a replacement for source history.

Observed event-period updates include onboarding/settings improvements, the
Ollama Cloud adapter and validation, production deployment, frontend/backend
proxy integration, Slack/ClickUp event-and-approval integration, graph assignment,
durable delivery/recovery fixes, tests, video preparation, and documentation.
These updates do not establish that
the main FalkorDB implementation was created during the event.

The [rules](https://www.wemakedevs.org/hackathons/falkordb/rules) require main
coding/design work to begin during the event. The
[FAQ](https://www.wemakedevs.org/hackathons/falkordb) also requires the submission
and main FalkorDB implementation to be new event work. The participant should
resolve this existing-work question with the organizers and accurately identify
what was built when. Eligibility confirmation is not claimed.

## AI assistance and authorship

OpenAI Codex assisted with code, tests, troubleshooting, deployment, and
documentation. The participant provided product direction, requested workflows,
company-test scenarios, and acceptance feedback. Assistant-run verification is
not a claim that the participant personally reviewed every implementation detail.

Before submitting, the participant must understand and be able to explain the
graph model, queries, architecture, memory scope, tool permissions, provider
boundaries, known limitations, technical choices, and their own contribution.

## Demo data

The four company packs and Harbor Supply scenario are fictional fixtures. Use
only synthetic or otherwise event-permitted data in the submitted demo. Optional
Google access must not be used to import restricted private content for this event.
Access to a document alone does not establish permission to use it as demo data.

## Deliverables

| Item | State |
| --- | --- |
| Public source repository | Intended repository: `Haleem-code/Workweave`; confirm public visibility and push current local files |
| Setup instructions and graph model | README and linked guides |
| Core Cypher queries | `docs/graph-queries.cypher`, with source references |
| Working-project video | Complete 3:50 MP4 and captions included in `docs/media/`; README and blog link the repository-hosted video. Public links require pushing those files. Slack authentication verified; channel permissions pending; ClickUp setup-only in the recording |
| Live deployment or complete local setup | Frontend/backend live and local setup included; password onboarding and an Ollama Cloud response verified in the live audit; hosted embeddings and complete Google consent remain unverified |
| Named tracks | Company Brain; Agent Memory and Coordination; Agents That Act on Connected Data |
| AI assistance | Disclosed |
| Event-window history | Prior prototype disclosed; eligibility clarification outstanding |

The latest full backend run passed 57 tests with real disposable FalkorDB and
controlled external API responses. The production frontend build and TypeScript
check passed. This is not a claim of a completed live Slack-to-ClickUp dispatch.

Before submitting, push the current source and `docs/media` assets, verify the
public video link, review the code, and resolve the build-history question.
