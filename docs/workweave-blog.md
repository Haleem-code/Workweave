---
title: "Workweave: connecting company knowledge to accountable work with FalkorDB"
description: "A company brain with source-backed answers, graph investigations, persistent memory, and reviewed Slack-to-ClickUp actions."
tags: falkordb, ai, hackathon, webdev
published: false
---

# A late shipment is a fact. Knowing which promises it affects is the useful part.

A delivery procedure explains what should happen when an order is delayed. A spreadsheet holds the customer commitments. A team guide says who is responsible. A conversation may explain what changed.

The company already has much of the information. Its employees still have to reconstruct the connections before they can decide what to do.

I built **Workweave** around that problem: company knowledge should help people understand a change, review the next step, and remember the outcome.

**[Try the live app](https://workweave-web.fly.dev) · [Explore the source](https://github.com/Haleem-code/Workweave) · [Watch the complete 3:50 demo](https://raw.githubusercontent.com/Haleem-code/Workweave/main/docs/media/workweave-demo-3m50s.mp4)**

[![Watch the Workweave demo](https://raw.githubusercontent.com/Haleem-code/Workweave/main/docs/images/demo-poster.jpg)](https://raw.githubusercontent.com/Haleem-code/Workweave/main/docs/media/workweave-demo-3m50s.mp4)

The video is a walkthrough of the running application, with synthetic narration and captions. Its Slack account authentication is real. Channel permissions remain pending in the recording, and ClickUp is shown at setup. The article distinguishes those live results from automated tests throughout.

## Start with a company, not a database schema

Workweave begins with a short onboarding flow: what kind of company this is, what the team needs help with, and what to call the workspace. A logistics company can start with delivery procedures and responsibilities. A software company can start with projects and operating guides.

These choices personalize the guidance. They do not invent a company's organization or turn the interface into an entirely different product.

Next, the user uploads a supported document or spreadsheet. Workweave shows the parsed content and proposed mappings before asking for confirmation. Accepted information becomes versioned evidence in FalkorDB.

This review step matters. A document can contain a person's name without defining their responsibility. A column can look like an identifier without establishing a dependency. The application needs a clear boundary between a suggestion and accepted company knowledge.

## The question that made the graph necessary

The operational example uses **Harbor Supply**, a fictional distributor. A supplier shipment that was expected on October 16 moves to October 23.

The useful question is: **which customer commitments now need attention, and why?**

Workweave follows recorded dependencies from customer orders to the affected purchase order. It then checks required dates, quantities, available stock, and current evidence.

The result deliberately contains different outcomes:

| Order | Result |
| --- | --- |
| Acme cartons | Needs review: the commitment precedes the delayed arrival and stock is insufficient |
| Beacon cartons | Needs review: its commitment also precedes the delayed arrival |
| Later cartons | Excluded: its required date is later |
| Tape with stock | Excluded: unallocated stock covers the order |
| Unrelated tools | Outside the traversed dependency paths; not assessed |

That last distinction matters. An order outside the query's scope is not a proven safe order. Likewise, a connected order is not automatically an affected order. Connectivity gives us candidates; the business checks establish the finding.

## What FalkorDB actually does

FalkorDB is the primary store for company knowledge and workflow state. It holds source versions, evidence chunks, accepted records, people, conversations, investigations, tasks, and remembered outcomes.

The operational relationships include:

```text
Customer order ──DEPENDS_ON──▶ Purchase order ──DEPENDS_ON──▶ Supplier
      │
      ├──OWNED_BY──▶ Responsible team
      └──SUPPORTED_BY──▶ Source version
```

Here is the core shape of the bounded traversal:

```cypher
MATCH path=(o:Entity {entity_type:'SalesOrder',active:true})
  -[:DEPENDS_ON*1..4]->(target:Entity {id:$id,active:true})
WHERE all(n IN nodes(path) WHERE n.active=true)
RETURN DISTINCT o.payload AS order_json,
  [n IN nodes(path) | n.id] AS path_ids
```

The complete implementation also joins the purchase-order and product records needed for the date and stock checks. The returned node IDs expose the actual route through the graph. They are not an explanation assembled from invented connections.

The model does not write arbitrary Cypher. Reviewed tools use fixed, parameterized queries, with validated arguments and company/user/run boundaries. A private MCP catalogue exposes retrieval, impact tracing, ownership, procedures, memory, and eligible internal task creation.

Removing FalkorDB removes these paths, evidence retrieval, persisted jobs, and memory. It is not an optional visualization layer over a separate business database.

## An answer should carry its evidence

For company questions, Workweave retrieves current evidence before answering. Retrieval combines exact and full-text matching, optional semantic search, and graph context. Revoked, inactive, incomplete, or superseded evidence is filtered.

The interface lets the user open the source behind a claim. In the KoraBridge example, the documents explain the company and identify responsibilities. They do not necessarily identify the founder. Workweave should say that the fact is missing rather than infer that the Managing Director must be the founder.

Citations make an answer reviewable. They do not make every model-generated statement infallible. Keeping the source visible gives the person using the system a practical way to challenge the answer.

## Memory means preserving what happened

A useful company assistant must carry more than a transcript into the next session.

Workweave stores accepted facts and relationships as semantic context, investigations and outcomes as episodic context, and approved versioned procedures as procedural context. Conversation history, task state, and investigation checkpoints persist in the company graph.

In the Harbor Supply workflow, the investigator saves findings and a handoff to the response coordinator. The coordinator creates internal review tasks. Completing a task updates its remembered outcome. Refreshing the application does not erase the investigation or the work already recorded.

These are bounded application roles and persisted handoffs. I am not claiming a distributed fleet of autonomous agents or benchmarked high-concurrency coordination.

## Bringing Slack requests into reviewed work

Documents are useful context, but new work often begins in a message. Workweave therefore also implements a Slack-to-ClickUp pipeline:

```text
Selected Slack channel
        ↓
Verify signed event → Persist in company graph → Acknowledge
        ↓
Background triage + graph-supported candidate selection
        ↓
Task Inbox: administrator reviews or edits the proposal
        ↓
Approved outbox job → ClickUp task → Slack confirmation
        ↓
Recorded task outcome becomes future context
```

An administrator connects the Slack app, configures its public HTTPS event callback, and selects the channels to watch. No selected channels means no message intake. Credentials are stored separately from company knowledge in an encrypted backend vault.

When an eligible signed message arrives, the application persists it before acknowledgement. Slow author lookup and AI triage happen afterward. Slack retries are deduplicated using a company-scoped event identifier.

The assignment graph has its own concrete relationships:

```text
Person ──HAS_ROLE──▶ Role ──RESPONSIBLE_FOR──▶ Responsibility
   ▲
   └──ASSIGNED_TO── ExternalTask
```

FalkorDB finds eligible, confirmed, ClickUp-mapped people whose roles or responsibilities match, and joins their past assigned tasks. Python scores the bounded graph results using responsibility overlap, similar on-time completions, overdue/reassigned work, and current workload. The UI can show real path IDs, factors, and current attached evidence.

This score is a transparent heuristic. It is not a learned employee-performance ranking, and a human still chooses whether to approve the proposal.

## A task should not be created twice because a response was lost

External writes introduced a more difficult engineering question than showing a connected badge.

Suppose ClickUp creates a task, but the network connection drops before Workweave saves the response. Retrying the same POST could create a second task.

Workweave uses deterministic outbox IDs, graph-side leases, unique worker ownership, and an external marker. Before creation, it searches for that marker. A search error does not count as “task absent.” A persisted `create_started` flag prevents blind resending after an uncertain write.

If the existing task is found, the worker reconciles its ID and restores the graph assignment. If the outcome remains uncertain, it pauses for review. Slack confirmation is tracked separately: a failed reply does not erase the created ClickUp task or silently mark the whole job successful.

There is no distributed transaction spanning Slack, ClickUp and FalkorDB. The practical goal is recoverable state and conservative handling of uncertainty, not an exactly-once promise the external APIs do not provide.

## Architecture in plain language

The browser is a **Next.js/React** workspace. It uses a same-origin proxy to reach **FastAPI**. Authentication and membership checks select the appropriate company graph before retrieval or tool execution.

The backend connects to **FalkorDB**, an optional self-hosted Ollama embedding service, and the configured answer providers. Ollama Cloud is the default chat provider; permitted and configured fallbacks can be used if needed. Embeddings and chat are separate services.

Slack events enter through a signature-checked receiver. Background workers persist proposals and delivery state in FalkorDB. External writes wait for administrator approval. The encrypted credential vault lives on a backend volume, outside the company knowledge graph.

The frontend and API run as separate Fly apps from one repository. The [architecture guide](https://github.com/Haleem-code/Workweave/blob/main/docs/architecture.md) contains component, ingestion, integration and recovery diagrams, plus links to the implementing modules.

## Test the idea across different companies

I prepared four fictional company packs so reviewers can test more than a single rehearsed question:

- **KoraBridge Logistics:** delivery exceptions, operations ownership and project context.
- **Sunvale Energy Systems:** installation projects and blocked sites.
- **Cedargrain Foods:** quality release authority and deliberately unconfirmed dates.
- **Meridian Harbor Software:** project ownership, planned releases and shipping status.

Each pack includes a PDF profile, Markdown procedure, and text report. A separate guide contains 24 questions and an answer key. Reviewers should upload the company documents, not the answer key, and use a separate workspace for each company.

The packs include repeated names and intentionally absent facts. Those choices exercise tenant isolation and the ability to admit uncertainty. They do not establish that every company workflow can be inferred from arbitrary files.

[Open the company-pack guide](https://github.com/Haleem-code/Workweave/tree/main/docs/testing)

## What was verified—and what remains

The latest complete backend run passed **57 tests** inside Linux against disposable real FalkorDB. External Slack and ClickUp responses were controlled in these tests. Coverage includes real assignment paths, current-source filtering, atomic claims, competing workers, approval gating, lost responses, reply retries, tenant boundaries, private MCP, and interrupted-work recovery. The frontend production build and TypeScript check passed.

The recording demonstrates the running application, source inspection, operational investigation, persisted outcomes, Slack account authentication, and integration setup. It does **not** demonstrate a completed live Slack-to-ClickUp dispatch: channel discovery still needed Slack permissions, and ClickUp was not connected in that recording.

Current boundaries also include reviewed manual onboarding, bounded worker scans, token-based connector installation, no scanned-PDF OCR, and separate provisioning for hosted embeddings. Public multi-customer OAuth and broader connector coverage are future work.

## Why I chose Company Brain

The central product is a shared understanding of how a company works: its evidence, people, dependencies, procedures, and decisions. Memory and reviewed actions make that understanding useful over time. **Company Brain is the named submission track.**

OpenAI Codex assisted with implementation, fixes, verification, deployment, documentation, and video preparation. I directed the product goals, company scenarios, integration work and acceptance feedback. The narration is synthetic. Before submission, I must be able to explain the code, graph model, queries and engineering decisions myself.

Earlier project documentation described pre-event prototype work. That history is preserved in the repository's [submission disclosure](https://github.com/Haleem-code/Workweave/blob/main/docs/submission-disclosure.md); this article does not claim that the whole implementation began during the event or that organizers have confirmed eligibility.

The ambition is practical: when someone asks what changed, what it affects, and who should act, the answer should carry a source, a connection, a reviewable next step, and a memory of what happened afterward.

**[Try Workweave](https://workweave-web.fly.dev) · [Watch the demo](https://raw.githubusercontent.com/Haleem-code/Workweave/main/docs/media/workweave-demo-3m50s.mp4) · [Read the README](https://github.com/Haleem-code/Workweave) · [Captions](https://raw.githubusercontent.com/Haleem-code/Workweave/main/docs/media/workweave-demo-3m50s.srt)**
