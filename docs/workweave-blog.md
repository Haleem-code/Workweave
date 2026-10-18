---
title: "Workweave: an AI company brain that turns information into useful work"
description: "How Workweave uses FalkorDB to connect company documents, remember outcomes, and turn Slack requests into reviewed ClickUp tasks."
tags: falkordb, ai, hackathon, webdev
published: false
---

## What if your company information could help your team decide what to do next?

Most companies already have useful information. Some is in documents, some is in spreadsheets, and some is in Slack messages. The hard part is connecting it.

Someone asks a question. A manager looks for the right document. Another person checks who owns the work. Someone else creates a task. Later, the team has to remember why that task was created and what happened to it.

I built **Workweave** to bring these steps together.

Workweave helps teams ask questions about their company, check the source behind an answer, find the people responsible, and keep a record of the next step and its outcome. It uses **FalkorDB** to store the information and the connections between it.

It is designed for company knowledge across industries. Logistics is one example in the demo. The repository also includes fictional energy, food production, and software companies.

**[Try Workweave](https://workweave-web.fly.dev) · [Source code](https://github.com/Haleem-code/Workweave) · [Watch the 3:50 demo](https://youtu.be/3Rfimah_TUQ)**

[![Watch the Workweave demo](https://raw.githubusercontent.com/Haleem-code/Workweave/main/docs/images/demo-poster.jpg)](https://youtu.be/3Rfimah_TUQ)

<!-- DEV Community: this tag embeds the video when you publish the article. -->
{% embed https://www.youtube.com/watch?v=3Rfimah_TUQ %}

## First, tell Workweave about your company

A new user chooses the company's work area, what they want help with, and a workspace name. These choices help the app show useful starting guidance.

The user can then upload a company profile, a procedure, a report, or a supported spreadsheet. Workweave shows a preview before saving the information as company knowledge.

People and responsibilities found in documents are suggestions. An administrator reviews them before relying on them. A person mentioned in a document does not automatically get an account or permission to use the app.

For example, a company guide might say that Ada handles billing issues. The administrator can confirm that role and connect Ada to her ClickUp user account in **Team Roster**.

## How a company question gets answered

A user might ask:

> Who handles billing issues, and what is our approval process?

Workweave looks through the company's current information, finds relevant evidence, and uses that evidence to prepare an answer. The user can open a source button to check the original passage.

If the documents do not contain the answer, the app should say so. For example, knowing the Managing Director's name does not tell us who founded the company.

Documents can change. Workweave keeps source versions and filters out old or withdrawn evidence when preparing current answers.

## How Slack connects to Workweave

An administrator connects a Slack app using its bot token and Signing Secret. These are entered privately in **Connections**, not added to GitHub.

Workweave gives the administrator a public HTTPS address for Slack events. They add it to Slack's Event Subscriptions, give the app the required permissions, invite the bot, and choose which channels Workweave should watch.

Only selected channels are used. Selecting no channels means no messages are monitored.

When Slack sends a message, Workweave checks that it came from the configured app/workspace and has a valid signature. It saves the accepted event in the company's FalkorDB graph before acknowledging it. Reading the author's name and asking the AI to review the message happen afterward.

This keeps slower AI work out of the first response to Slack. It also gives the app a saved event to continue processing after an interruption.

## How the AI decides whether a message needs a task

Imagine someone posts this in a selected company channel:

> Please fix the billing export. The invoice totals are wrong.

The AI checks whether the message asks for work. A greeting or a thank-you message should not become a task.

For a work request, the AI prepares a draft title, description, useful matching words, and any deadline mentioned in the message. It does not get permission to create an external task at this stage.

If AI extraction is unavailable, the app can leave the request for manual review instead of pretending that the AI completed the decision.

## How Workweave finds someone who can do the work

The AI does not choose from a list of random names. Workweave first asks FalkorDB for suitable people based on the company's confirmed information.

The graph stores connections such as:

```text
Person → Role → Responsibility
Past task → Assigned person
Person → Supporting document
```

For the billing example, a confirmed person responsible for billing exports is a better match than someone whose role is warehouse dispatch.

The app considers:

- How well the person's role and responsibilities match the request.
- Similar tasks recorded as completed on time.
- Relevant tasks recorded as late or reassigned.
- How much open work is already recorded for that person.

People must be active, confirmed, and mapped to a ClickUp user before they can be automatic assignment candidates. Attached document evidence must still be current.

FalkorDB finds the connected records and returns real graph paths. Application code calculates a clear fit score from those results. When available, the AI can review the top three candidates and choose only from those supplied people. It cannot invent a new employee.

This is a practical matching rule, not a promise that the AI always knows the best person. The administrator can inspect the reasons and change the choice.

## How the ClickUp task gets created

ClickUp is connected separately using a personal API token and a destination **List ID**. The List ID tells Workweave where approved tasks should go.

The proposed task first appears in **Task Inbox**. The administrator can review:

1. The original Slack request.
2. The proposed task title and description.
3. The suggested person and other candidates.
4. The matching factors, recorded paths, and available document evidence.

The administrator can edit the draft or change the assignee. Only after they choose **Approve & Create in ClickUp** does the worker send the task to ClickUp.

Once creation is confirmed, Workweave saves the task ID and tries to post a confirmation in the Slack thread with a link to the task.

```text
Slack request
    ↓
AI prepares a draft
    ↓
FalkorDB finds suitable people and their supporting connections
    ↓
Administrator reviews and approves
    ↓
Worker creates the ClickUp task
    ↓
Task ID, confirmation and later outcome are saved
```

The app does not create ClickUp tasks or send confirmation replies just because an AI model said to do so. Human approval is the gate.

## What happens if a connection fails?

A network problem should not create the same task twice.

Each approved job has a stable ID and a marker that can be found in ClickUp. Before creating a task, the worker checks whether that task already exists.

If ClickUp may have accepted the task but its reply was lost, Workweave searches for the existing task. It does not blindly send another create request. If the result is still unclear, it pauses for review.

Slack confirmation is tracked separately. A failed Slack reply does not erase the ClickUp task or falsely mark the entire job complete.

These checks make recovery safer. They do not mean three separate services share one perfect, exactly-once transaction.

### The difficult case: the task exists, but its response never arrives

A timeout does not always mean an action failed. ClickUp could create a task, then the connection could fail before Workweave receives its ID. Retrying the same request could create a second task.

The worker records that creation has started before sending the request. Each job also has a stable marker in its task description. On retry, the worker searches for that marker and saves the existing task ID if it finds one. If a previous creation attempt has an uncertain outcome, it does not blindly send another create request. An unsuccessful search request is not treated as proof that the task is absent.

The regression test recreates this failure deliberately: the simulated ClickUp endpoint stores the task, then raises a read timeout. On the next worker attempt, the search returns that task. The test checks that there was **only one create request**, the saved job finished, and the task retained its person assignment.

This test uses real FalkorDB storage and simulated external HTTP responses. It checks recovery logic; it is not evidence of a completed live ClickUp integration.

[Read the lost-response and competing-worker tests](https://github.com/Haleem-code/Workweave/blob/main/workweave-api/tests/test_integration_regressions.py).

## What the app remembers

Workweave keeps conversations, investigations, internal tasks, approved procedures, and recorded outcomes in the company's graph. A user can return later and see what was found and what happened next.

The ClickUp worker also periodically checks task updates. Those recorded outcomes can help with later assignment suggestions. This is the app reading saved context, not training a new AI model on every message.

Company workspaces have separate knowledge graphs. Access checks also control which company and private conversation a user can read.

## Why the demo includes a delivery delay

The delivery example makes the relationships easy to see. A supplier shipment changes date. Workweave follows the connected purchase order to customer commitments, then checks deadlines and stock.

Two orders need attention. Two other connected orders are excluded for clear reasons. An unrelated order is outside the investigation's paths.

This is one implemented operational workflow. Company document questions and role-based task routing are broader features. Deeper checks for other industries need the right structured data and supported relationships; choosing an industry during onboarding does not create all those rules automatically.

### The Cypher behind the result

This is the dependency query used by the investigation tool. The application resolves the requested record against current source evidence before binding its ID to `$id`.

```cypher
MATCH path=(o:Entity {entity_type:'SalesOrder',active:true})
  -[:DEPENDS_ON*1..4]->(target:Entity {id:$id,active:true})
WHERE all(n IN nodes(path) WHERE n.active=true)
MATCH (o)-[:DEPENDS_ON]->(po:Entity {entity_type:'PurchaseOrder',active:true})
OPTIONAL MATCH (o)-[:DEPENDS_ON]->(product:Entity {entity_type:'Product',active:true})
RETURN DISTINCT o.payload AS order_json, po.payload AS po_json,
  product.payload AS product_json,
  [n IN nodes(path) | n.id] AS path_ids
ORDER BY o.required_date
```

In plain English, it finds active sales orders that depend on the changed record through one to four recorded connections. It also returns the purchase-order data, any linked product data, and the IDs along each path. Those IDs let the interface show how a commitment is connected to the change.

The query finds candidates. Python then checks current source versions, required dates, delivery dates, quantities, and unallocated stock. A connected order is not automatically an affected order. The four-hop limit also means this is a bounded investigation, not a claim to inspect every possible dependency at any depth.

[Inspect the query and business checks in `trace_impact`](https://github.com/Haleem-code/Workweave/blob/main/workweave-api/workweave_api/tools.py).

### From a changed date to a remembered outcome

**Before the investigation:** the supplier's arrival date has moved to October 23. That date alone does not tell a team which customers need attention.

**After following the graph:** Workweave identifies two commitments needing review and creates two internal tasks for Customer Success. The Acme order needs 10 units by October 19, but only 2 unallocated units are available. Beacon needs 8 units by October 20, with none available. Other checked orders are excluded when their dates or stock cover them; an unrelated order is outside the investigated paths.

![Workweave investigation showing the changed supplier date, two affected commitments, Customer Success ownership, and two open internal review tasks.](https://raw.githubusercontent.com/Haleem-code/Workweave/main/docs/images/blog-impact-review.png)

**After someone acts:** the demo marks the Beacon review task done. The memory page then shows Beacon as done and Acme as open, alongside the original findings, source buttons, and current procedure. The next session can return to that recorded outcome.

![Workweave memory showing the saved supplier-delay findings, Beacon review marked done, Acme review still open, source links, and the approved procedure.](https://raw.githubusercontent.com/Haleem-code/Workweave/main/docs/images/blog-saved-outcome.png)

These are screenshots from the synthetic Harbor Supply demo. Its investigation is deterministic and uses the implemented graph tools. Marking a review task done records the user's update; it does not prove that a delivery arrived or a customer was contacted. These internal tasks are separate from the ClickUp workflow described earlier.

## A simple view of the architecture

![Workweave architecture: company documents, FalkorDB memory, and the Slack-to-reviewed-ClickUp workflow.](https://raw.githubusercontent.com/Haleem-code/Workweave/main/docs/images/workweave-architecture.png)

- **Next.js and React:** the interface people use.
- **FastAPI:** sign-in, access checks, imports, questions and integration endpoints.
- **FalkorDB:** company facts, relationships, conversations, tasks, job state and memory.
- **Configured AI providers:** extract proposed work and help write source-grounded answers.
- **Background workers:** process requests and deliver approved external actions.
- **Encrypted backend vault:** stores credentials separately from company knowledge.

[See the architecture diagrams and source-file map](https://github.com/Haleem-code/Workweave/blob/main/docs/architecture.md).

## What has actually been tested?

The complete backend suite passed **57 tests** in Linux using a real disposable FalkorDB database. Tests used controlled Slack and ClickUp responses to check the full request, assignment, approval, creation and confirmation flow. They also tested competing workers, lost responses, stale sources, permissions and recovery. The frontend production build and TypeScript check passed.

In the public video, Slack authentication succeeded for KoraBridge, but channel permissions were still pending. ClickUp is shown at setup. The recording therefore does not claim a completed live Slack-to-ClickUp dispatch.

The repository includes four fictional company packs and a separate reviewer question guide. Reviewers should upload the company documents, not the answer key, and use a separate workspace for each company.

[Try the company packs](https://github.com/Haleem-code/Workweave/tree/main/docs/testing).

## What I learned

Finding a connected record is only the first step. In the delivery example, the graph finds candidate orders, but dates and stock determine whether they actually need attention. Returning the path makes that decision easier to inspect.

I also learned that a timeout is not proof of failure. Saving a job before processing it, recording external task IDs, and checking uncertain results are part of making an action reliable. A successful answer on screen is only one part of the workflow.

Finally, connecting an account is different from having permission to read its data. Slack authentication worked in the recording, but channel discovery still needed additional scopes. The demo labels that setup as pending instead of presenting authentication as a completed integration.

## Tracks and build disclosure

The named tracks are **Company Brain**, **Agent Memory and Coordination**, and **Agents That Act on Connected Data**. Company knowledge and source-backed answers support the first. Saved outcomes, checkpoints and the investigator-to-coordinator handoff support the second. Graph investigations that identify affected commitments, resolve owners and create internal review tasks support the third. The connected-data action claim does not depend on a completed live Slack-to-ClickUp dispatch. High-concurrency autonomous-agent operation has not been benchmarked.

OpenAI Codex and GitHub Copilot assisted with development. Codex also assisted with testing, deployment, documentation, and demo video preparation. I directed the product, developed the company scenarios, and reviewed the results. The video uses synthetic narration. I reviewed and tested the implementation and can explain its architecture, graph model, and technical decisions.

Earlier documentation described pre-event prototype work. That history is preserved in the [submission disclosure](https://github.com/Haleem-code/Workweave/blob/main/docs/submission-disclosure.md); this article does not claim that the entire implementation began during the event or that eligibility has been confirmed.

**[Open Workweave](https://workweave-web.fly.dev) · [Watch the demo](https://youtu.be/3Rfimah_TUQ) · [View the code](https://github.com/Haleem-code/Workweave)**
