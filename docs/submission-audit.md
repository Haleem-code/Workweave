# Latest verification — October 18, 2026

- **57 backend tests passed** in a Linux container with disposable real FalkorDB and controlled external API responses. Real graph assignment, concurrent claims, duplicate prevention, approval gating, ambiguous external responses, and reply retries are covered.
- The frontend production build and TypeScript check passed.
- The complete **3:50, 1920×1080, 30 fps** [video](media/workweave-demo-3m50s.mp4) decoded successfully from start to finish. [Captions](media/workweave-demo-3m50s.srt) and [media verification](media/video-verification.json) are included.
- Slack authentication succeeded for the synthetic KoraBridge workspace. Channel discovery returned `missing_scope`; no watched-channel intake or live external dispatch was verified. ClickUp is shown at setup-only.
- The public Slack callback URL and the distinction between account authentication and live-event readiness were corrected.
- Hosted embeddings, complete Google consent, production-scale concurrency, and the outstanding build-history eligibility question are separate from these results.

The earlier audit below is retained as a historical record. Its test count and connector/video status are superseded by this update and the current README.

---

# Submission audit — October 17, 2026

**Later update:** this report describes the core audit before workplace adapters
were added. Connections now provides selected read-only Slack/ClickUp snapshots;
see [the current connection guide](workplace-connections.md). Real-account tests
and the video update are pending the participant connecting synthetic content.

This audit exercises a defined demo journey. It does not assign a judging score,
guarantee eligibility, or certify every possible company workflow.

## Changes verified

- Added **Home → Try the example**, which creates a separate fictional Harbor
  Supply workspace. Preparation is a persisted background job instead of one long
  HTTP request. An interrupted preparation can resume; repeated setup does not
  create duplicate review tasks or replace an existing company's profile.
- Batched operational dependency reconstruction to reduce remote database calls.
- Added evidence-backed explanations for the two assessed orders excluded from
  the impact result. Orders outside the traversed paths are explicitly unassessed.
- Exposed the saved investigator-to-coordinator handoff and a direct route to
  remembered outcomes. Active runs refresh more frequently than idle pages.
- Fixed duplicate recent-conversation cards when switching workspaces.

## Automated checks

The isolated backend suite passed **40 tests** against real disposable FalkorDB.
This includes source versions, impact and stock exclusions, task recovery,
interrupted-example recovery, company/private-history boundaries, scoped tools,
provider policies, malformed model names, and hostile origins.

The frontend production build and TypeScript check passed. The isolated browser
journey passed from onboarding to task outcomes with no captured browser runtime
errors. Its model endpoint was deliberately unavailable, so its source-check and
deterministic graph results are not evidence of cloud-model behavior.

## Live verification

Frontend: https://workweave-web.fly.dev

Backend health: https://workweave.fly.dev/api/v1/health

The audit created its own synthetic accounts and company workspaces through the
ordinary user interface. Existing customer workspaces were not inspected. Project
`.env` files and secrets were not read or edited during this audit.

The deployed browser journey verified:

- Password signup and the onboarding forms.
- Preview and confirmation of the three KoraBridge Markdown, PDF, and text files.
  Import confirmation took approximately **19.2, 6.4, and 13.4 seconds** respectively.
- The cloud-first default policy, an answer with an opened current-source citation,
  and an honest missing-founder response.
- A real Ollama Cloud response to “What information is missing?” This returned a
  generic insufficient-evidence answer, rather than a detailed missing-information
  analysis. The three questions completed in **9.9, 9.3, and 9.1 seconds** in this run.
- Conversation history after reload, sign-out/sign-in without repeated onboarding,
  and a 390-pixel mobile Ask layout without horizontal overflow.
- The example launched through Home, producing two affected commitments, two
  internal tasks, dependency paths, and a persisted coordinator handoff. Preparation
  and investigation took approximately **60.6 seconds** on the hosted database.
- Visible date/stock exclusion evidence, a single recent-conversations card,
  task-status changes, and the updated outcome fetched from persistent memory.
  No browser runtime errors were captured during the completed live journey.

Times are observations from one synthetic run, not performance guarantees. The
first browser attempt selected a disabled upload input before workspace creation
had settled. The test was corrected to wait for an enabled input and verify the
upload response; the retry completed the imports.

## Remaining submission work and limits

- Record and host the actual **3:30 demo video**, then link it in the README.
- Push the reviewed source and documentation to the public repository and verify
  reviewer access. Deployment alone does not publish current source to GitHub.
- Slack and ClickUp live connections are **not implemented**. Prepared synthetic
  messages/tasks in those services may be mentioned as future integration data;
  do not present them as synchronized with Workweave.
- A complete Google OAuth consent roundtrip and hosted embedding service were not
  verified. The demonstrated path uses password login and available source/graph
  retrieval. Not all 24 questions across the four company packs were evaluated.
- Company Brain remains the declared track. The handoff is a bounded internal
  workflow; it does not establish distributed-agent execution or production-scale
  concurrency guarantees.
- Retain the existing build-history and AI-assistance disclosures. Organizer
  clarification of pre-event implementation eligibility remains outstanding.

Follow the [recording plan](submission-recording-plan.md) and
[narration draft](submission-video-script.md) for the next step.
