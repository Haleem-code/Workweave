# Workweave — step-by-step demo recording and submission plan

Checked against the official event overview and rules on October 17, 2026:

- https://www.wemakedevs.org/hackathons/falkordb
- https://www.wemakedevs.org/hackathons/falkordb/rules

The principal artifact is a recording of the running app with narration. Motion graphics are brief explanatory overlays. This is not a template presentation or a replacement UI animation.

## Capture order — 3 minutes 30 seconds

These times are editorial targets. No video duration limit was found on the public pages checked. Check the signed-in submission form for any additional field constraints.

| Target | Actual screen recording | Explanation |
| --- | --- | --- |
| 0:00–0:12 | Open the live app and introduce the problem | Knowledge is scattered; Workweave connects evidence to responsibilities and next steps. |
| 0:12–0:32 | Create a synthetic demo workspace through onboarding | Show work area, starting focus, and workspace name. Guidance adapts; an entire industry application is not generated. |
| 0:32–1:00 | Select one fictional company document, preview, confirm, and open the saved source | Explain that uploaded files become versioned evidence. Show the completed import rather than replacing it with a title card. |
| 1:00–1:35 | Ask a useful company question, show the answer, then open its citation | Demonstrate an actual response. Include the missing-founder answer briefly. An answer alone is not proof of relationship reasoning. |
| 1:35–2:25 | Launch the separate synthetic Harbor Supply example from Home; show the real investigation | Follow the delayed shipment to affected orders; show reasons other assessed orders are excluded, then the responsible team, saved handoff, and internal review tasks. Label any accelerated preparation. |
| 2:25–2:50 | Update a review task and reopen its remembered outcome after refresh | Show actual persistence. For the memory track, also verify recall of the updated outcome; history alone is insufficient evidence of coordination. |
| 2:50–3:20 | Open FalkorDB Browser on the demo company's graph; execute a reviewed query, inspect returned data | Explain nodes, relationships, the path behind the result, and where source evidence is stored. Hide connection credentials and unrelated company data. |
| 3:20–3:30 | Return to the app, then show links and a small architecture overlay | Show repository, live app, tracks, and AI disclosure. A small roadmap note may say Slack/ClickUp connections are planned; do not depict them as connected. |

Use one consistent fictional company for onboarding and document Q&A. Harbor Supply uses a different structured-data example: announce that transition rather than pretending a narrative PDF created those operational dependencies.

## Footage and narration

Capture the complete working journey before polishing the edit. If a feature fails, repair and recapture it, or remove the unsupported claim. Do not fill gaps with invented screens.

Your own voice is suitable. Read the narration in short sections with a pause between them. Record one test sentence and listen before doing the full take. The existing narration draft is in `submission-video-script.md`; adapt it to the real footage, not the reverse.

Keep actions in order. A cut may remove dead time, but label accelerated model/database waits. Keep enough of the original wait to make the sequence understandable. Do not imply measured speed from an edited clip.

## Motion graphics direction

- Use Workweave's existing cream/green palette and typography.
- Keep the app readable and visible for most of the video.
- Add short chapter labels: Set up, Add knowledge, Ask, Investigate, Act, Remember, Inside FalkorDB.
- Highlight one relevant region at a time: upload confirmation, citation, dependency path, owner, task status.
- Use a brief diagram to explain supplier → purchase order → customer commitment, following the actual recorded graph direction when presenting Cypher.
- Use captions; avoid dense paragraphs and oversized effects covering the answer.
- Native Adobe timeline tools support assembly of uploaded media and audio. Specific custom motion effects, caption styling, zoom animation, and export options must be verified rather than promised from the available connector alone.
- No template choice is needed to record the product walkthrough. Optional Express template work is separate from the required demo.

## Scope before submission

Prioritize one complete verified workflow, legible evidence, and an easy way for a reviewer to reproduce it. Defer the mascot, additional connectors, broad redesign, and any unverified automation.

The original captured video predates the Connections interface. Read-only Slack
and ClickUp adapters have since been added; see [connection setup](workplace-connections.md).
The participant has asked to defer video changes until connecting their fictional
workspace. Capture the actual selected-source preview and confirmed import before
claiming a successful connection. Do not present these snapshots as automatic sync.

A mascot can show agent status later, but it does not implement memory. Persistent scoped state, evidence, outcome updates, and cross-session recall are the memory features to prove.

Company Brain is the primary declared track. Agents That Act on Connected Data is a plausible additional entry when the working traversal/action flow is demonstrated. Memory and Coordination should be declared only with an accurate explanation of the existing bounded coordinator and a verified memory/handoff demonstration. Do not claim distributed execution or concurrency guarantees from the current implementation.

## Submission package

The official rules require public code, setup and graph-model documentation, dependent Cypher/algorithms, a working-project video, live deployment or full local setup, and declared track(s). AI coding assistance must be disclosed. A pitch deck and a blog are not listed as mandatory deliverables. The event lists a separate best-blog-post prize.

Recommended packaging:

1. GitHub: public source, README, architecture, graph model, real queries, fictional company packs, setup, known limitations, AI disclosure, and accurate build history.
2. Video host: upload the completed demo with a publicly accessible or appropriately unlisted viewing link; verify access when signed out. Put its link near the top of the README. Do not mark it recorded until it exists.
3. Optional article: publish a focused technical project explanation on DEV.to or your preferred platform, linking to the video, repository, and live app. This does not replace the official submission.
4. Official event panel: submit all required links and name each entered track. Check actual form fields and limits; the authenticated form has not been inspected here.
5. Test all reviewer links signed out and make sure synthetic company fixtures are downloadable.

Avoid spending remaining time duplicating the full technical documentation into a deck and multiple publishing platforms. Finish the official submission before optional promotional work.

Deadline: October 18, 2026, 11:59 PM IST, equivalent to 7:29 PM WAT in Lagos. Aim to submit several hours early. The existing pre-event implementation disclosure needs organizer clarification; retain it and do not claim eligibility is confirmed.

## Current status

Narration and capture planning exist. The final screen recording, voice track, edited video, video hosting link, article, and official submission have not been completed by this plan. See the [audit report](submission-audit.md) for verified app behavior and remaining limits. Capture the verified flow again for the actual video.
