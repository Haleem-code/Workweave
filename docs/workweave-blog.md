---
title: "Workweave: a company brain that explains the next step"
description: "Connecting company evidence, operational dependencies, and remembered outcomes with FalkorDB."
tags: falkordb, ai, hackathon, webdev
published: false
---

# A late shipment is a fact. Knowing which promises it affects is the useful part.

A company can have a delivery procedure in a PDF, customer commitments in a
spreadsheet, and the explanation for a change in a workplace conversation.
Finding each item helps. Connecting them is what makes a useful next step possible.

That is the problem behind **Workweave**, a company knowledge and operations
assistant built around FalkorDB.

[Try Workweave](https://workweave-web.fly.dev) ·
[Source code](https://github.com/Haleem-code/Workweave) ·
[Fictional company packs](https://github.com/Haleem-code/Workweave/tree/main/docs/testing)

The primary Graph Hacks track is **Company Brain**. The product also includes a
bounded investigation-and-coordination workflow and persistent outcomes. Those
features are demonstrated within their actual scope rather than presented as a
general autonomous workforce.

## Start with something a company already understands

Workweave begins with a short onboarding flow: what the company does, where the
team wants help, and what to call its workspace. These choices personalize the
guidance. They do not magically generate a complete logistics or finance product.

A user adds a company profile, procedure, report, or supported spreadsheet. They
review the preview and confirm the import. Then they can ask a question and open
the source behind the answer.

One useful test is deliberately simple: ask who founded a company whose documents
name a Managing Director but never identify a founder. The correct result is an
explanation that the fact is missing. A plausible name would make the product
less trustworthy.

## The graph has to change the result

The separate **Harbor Supply** example makes FalkorDB's role visible. It uses
fictional structured records and an explicitly labelled deterministic workflow.

A supplier shipment moves to a later delivery date. The investigation traverses
recorded dependencies from customer orders to the changed purchase order. It then
checks required dates, quantities, source versions, and unallocated stock.

| Outcome | Why |
| --- | --- |
| Acme and Beacon carton orders need review | Supply arrives after their required dates and stock cannot cover them |
| The later carton order is excluded | Its required date falls after the revised delivery date |
| The tape order is excluded | Its unallocated stock covers the required quantity |
| An unrelated tools order is unassessed | It lies outside the recorded paths traversed by this investigation |

That final distinction matters. An investigation should explain its limits as
carefully as it explains a finding. A connection alone is not proof of impact,
and an absent path is not proof of safety.

The candidate traversal is small enough to review:

```cypher
MATCH path=(o:Entity {entity_type:'SalesOrder',active:true})
  -[:DEPENDS_ON*1..4]->(target:Entity {id:$id,active:true})
WHERE all(n IN nodes(path) WHERE n.active=true)
RETURN [n IN nodes(path) | n.id] AS path_ids
```

The full tool also obtains the purchase-order and product records needed for
the application checks. The model chooses approved tools; it does not invent
arbitrary Cypher. The repository includes the actual query catalogue.

## Keep the evidence attached to the work

The investigator resolves the responsible team and saves a handoff to the response
coordinator. That coordinator creates internal review tasks from recorded findings.
The UI exposes the findings, dependency paths, exclusion evidence, and handoff.

Completing a task updates its remembered outcome. Refreshing and reopening the
memory shows what was investigated and what happened afterward. This is a bounded
workflow with persisted state, not a claim of distributed-agent execution or
production-scale concurrency.

FalkorDB is central to this behavior. It stores company knowledge, versions,
dependencies, conversations, investigations, tasks, and memory. Each company has
its own graph; membership checks select that graph before a tool runs. Private
history also checks its author. Removing FalkorDB stops the workflow.

## Bring workplace tools into the same review flow

Uploading files is a useful starting point, but work also happens in Slack and
ClickUp. Workweave now includes a **Connections** interface and selected-source
adapters for those official APIs.

Reviewers do not need credentials to try the journey. **Try Slack demo data** and
**Try ClickUp demo data** create explicitly labelled fictional content, then use
the real preview, confirmation, and FalkorDB ingestion path. No external account
is connected in this mode. The video distinguishes these demo fixtures from live
API access rather than showing a fabricated successful connection.

![Selected workplace sources and separate demo-data options](https://raw.githubusercontent.com/Haleem-code/Workweave/main/docs/images/connections.png)

For the participant's own synthetic demo workspace, an administrator supplies a
Slack bot token and public channel ID, or a ClickUp personal token and list ID.
The adapter reads a limited snapshot, shows a preview, and requires confirmation
before adding it to company knowledge. Tokens remain encrypted on the backend.

The current limit is 15 top-level Slack text messages or 15 ClickUp tasks per
snapshot. These imports add source evidence; they do not automatically infer all
operational dependencies or update external tasks. Scheduled sync and public
OAuth onboarding are future work. Real-account verification is pending the
participant connecting the fictional workspace; a UI alone is not proof of sync.

Basic API access is available with free plans, subject to the services' limits.
The [connection guide](https://github.com/Haleem-code/Workweave/blob/main/docs/workplace-connections.md)
explains permissions, setup, and the current boundaries.

## Built to be tried, not just described

The repository includes four fictional company packs: logistics, energy, food
production, and software. Each has three documents, with separate reviewer
questions and expected answers. The answer key stays outside the app so it cannot
teach the system its own test answers.

The core audited browser journey covers onboarding, confirmed imports, citations,
history, the operational investigation, task updates, and persisted outcomes.
The pre-connector backend suite passed 40 isolated tests. New connector tests use
controlled API responses; neither those tests nor one working demo establish
production-scale reliability or perfect model accuracy.

The stack is Next.js and React, FastAPI, FalkorDB, and a configured answer provider
with Ollama Cloud as the default. Hosted semantic embeddings and a complete Google
OAuth consent journey remain separate unverified paths.

## What I want Workweave to earn

The goal is a company assistant whose next step can be checked: which source,
which relationship, which owner, and which recorded outcome. Automatic ingestion
can make that smoother over time. The evidence and the boundaries still need to
remain visible.

**Disclosure:** OpenAI Codex assisted with implementation, tests, troubleshooting,
deployment, and documentation. The participant directed the product and scenarios
and remains responsible for understanding the code and technical decisions.
The demo uses synthetic narration. Existing pre-event prototype history is
preserved in the repository's submission disclosure; organizer clarification of
eligibility is outstanding. This article does not claim that the entire existing
implementation originated during the event.

**Before publishing:** add the publicly viewable demo-video link. Real-account
connector verification remains separate from the demonstrated synthetic fixtures. This article
is a draft; it has not been posted to DEV.to or submitted to the event.
