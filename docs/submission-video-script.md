# Workweave submission video — narration and scene plan

Narration draft for a 3 minute 30 second recording, 16:9, readable at 1080p. Follow the exact scene timing in the [capture plan](submission-recording-plan.md). The draft section times below are guidance for narration only; onboarding and upload actions are included in the capture plan. The duration is the participant's chosen edit target, not a published hackathon requirement.

Use real recorded application behavior. Motion graphics explain the architecture; label them as diagrams. Label synthetic company data and any accelerated waiting. Record the completed workflow before finalizing narration. If a scene does not work in production, fix it or remove its claim.

## 0:00–0:12 — The problem

Visual: short animated diagram connecting a document, a purchase order, a customer order, and a team. Transition into the actual workspace.

Narration:

“A late shipment can put customer promises at risk. Workweave connects company knowledge to its evidence, the responsible team, and the next step.”

## 0:12–0:32 — Set up the company

Visual: real onboarding, selecting logistics, company answers, and a fictional workspace name.

Narration:

“First, tell Workweave what your company does and where you want to begin. These choices personalize its guidance. Here, I’m setting up a fictional logistics company so you can try the same workflow with the included test documents.”

## 0:32–1:00 — Add knowledge

Visual: select a company document, review its preview, confirm the import, and open the saved document. Label any shortened wait.

Narration:

“Upload a company profile, procedure, or supported spreadsheet. Review the preview before importing it. The accepted content becomes versioned evidence in FalkorDB. Workweave can suggest people and responsibilities from explicitly stated information; a person reviews those suggestions before relying on them.”

## 1:00–1:35 — Ask and verify

Visual: real uploaded company documents, a grounded question, and an opened source citation. Use one company consistently within this section.

Narration:

“Ask what the company does, then open the source behind the answer. You can check the actual document passage. Now ask who founded the company. These documents do not say, so Workweave explains what is missing rather than treating the Managing Director as the founder. Conversations remain available through History when you return.”

## 1:35–2:05 — The graph changes the result

Visual: clearly announce switching to the synthetic Harbor Supply operational example. Show the actual saved investigation, affected orders, and dependency evidence. Use a separate animated diagram only to clarify the recorded path.

Narration:

“Switch to Harbor Supply, the separate fictional operations example. This is a deterministic graph workflow. A supplier shipment moves to a later date. The investigation follows recorded dependencies, then checks deadlines and unallocated stock. Two orders need review. Two more are excluded, with date and stock evidence. Orders outside these dependency paths are not assessed.”

## 2:05–2:25 — From investigation to accountable work

Visual: actual responsible team, saved internal review tasks, and evidence. Show the real persisted workflow trace if the UI exposes it. Do not invent an agent handoff screen.

Narration:

“The investigation finds the responsible team and saves a handoff to the response coordinator. That coordinator creates two internal review tasks with evidence. Open the trace to inspect the findings, the handoff, and the recorded actions.”

## 2:25–2:50 — Memory that changes over time

Visual: update an actual task's status. Refresh or start a new session and reopen the investigation. For a memory-track submission, also record actual recall of the updated outcome, rather than history alone.

Narration:

“Mark a review task complete. Its remembered outcome now reflects that update. Refresh and reopen the saved memory: the investigation and what happened afterward are still here. This gives the next person context without asking them to reconstruct the whole conversation.”

## 2:50–3:20 — Why FalkorDB matters

Visual: concise architecture diagram, followed by the actual bounded Cypher traversal. Highlight the dependency path. Explain rather than show unreadable code at full-page scale.

Narration:

“Here is the same data in FalkorDB Browser. These nodes represent records and evidence; their relationships connect orders, supply, and ownership. The query follows the recorded dependency path. Reviewed tools run parameterized Cypher. FalkorDB also stores investigations, tasks, and memory. Each company has its own graph, with membership checks before access.”

## 3:20–3:30 — Close

Visual: live app address, repository, declared tracks, and brief AI-assistance disclosure. Keep links legible.

Narration:

“Understand the change. Explain the impact. Remember the outcome. Try Workweave and the included fictional company packs. AI assistance is disclosed.”

On-screen roadmap note: “Slack and ClickUp live sync: planned.” Their synthetic messages and tasks are prepared separately; this recording does not claim a live connection.

## Edit direction

- Match Workweave's cream background, dark green accents, and existing typography.
- Prefer clean cuts, subtle zooms, and short highlights around the relevant evidence.
- Keep the running product visible for most of the video.
- Add readable captions and keep background music below narration, if used.
- Keep future Slack/ClickUp synchronization out of the demonstrated feature claims.
- Do not describe the deterministic Harbor Supply example as a live model-generated investigation.
- Use the narrator's own voice if available; synthetic narration is an alternative, with any required disclosure.
- Confirm the submission's build-history eligibility separately; a polished video does not resolve it.
