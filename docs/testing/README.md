# Try Workweave with four fictional companies

These are the prepared company fixtures, not real customer records. All people,
companies, figures, addresses, and events are invented. The snapshots are dated
October 15, 2026. Each company has one searchable PDF profile, one Markdown
procedure, and one plain-text report: **12 upload files in total**.

## Pick one company

| Workspace name | Upload folder | What it tests | First question |
| --- | --- | --- | --- |
| KoraBridge Logistics | [01_korabridge_logistics](../01_korabridge_logistics/) | Delivery delays, stock coverage, dispatch responsibility | Who owns Project Atlas and what are its budget and target date? |
| Sunvale Energy Systems | [02_sunvale_energy](../02_sunvale_energy/) | Solar-project dependencies, budgets, change approvals | Who owns Project Lumen and which site is blocked? |
| Cedargrain Foods | [03_cedargrain_foods](../03_cedargrain_foods/) | Quality holds, release authority, inventory allocation | Who can release CGF-LOT-410, and is a release date confirmed? |
| Meridian Harbor Software | [04_meridian_harbor_software](../04_meridian_harbor_software/) | Release status, revenue, support escalation | Who owns Atlas, when is it planned, and has it shipped? |

## Run the document test

1. Download or clone this repository. Open the relevant folder under `docs`.
2. Open Workweave and create a workspace using that company's name. Choose its
   industry and starting focus. These answers tailor setup guidance.
3. Upload **only that company's three files**, individually. Preview and confirm
   each import. Finish reviewing the company details.
4. Review **People & roles**. Accept or correct the source-backed suggestions.
   A name in a document does not create a login account.
5. Ask the company's questions from [TEST_QUESTIONS.md](TEST_QUESTIONS.md).
   Open the source citations, then compare with
   [EXPECTED_ANSWERS.md](EXPECTED_ANSWERS.md) outside the app.
6. Create another workspace to try another company. Reopen conversation History
   after refreshing or signing back in to check persistence.

Do not upload the answer key, question list, test guide, or a ZIP archive. The
answer key would teach the app the expected answers and invalidate the test.
Use separate workspaces; combining all four packs changes the isolation test.

## What a good answer looks like

An answer should get the facts, dates, and units right; cite an actual uploaded
source; stay inside the current company; and distinguish a planned action from
one that has happened. Unknown facts should remain unknown. The pack includes:

- Two different employees named Ada Bello.
- Two different projects named Atlas, in different companies.
- A proposed freight purchase that has not been approved.
- An unreleased software project and a lot with no confirmed release date.
- Questions whose answers are deliberately absent, such as a bank account number.

There are **24 questions**. An optional rubric gives one point each for factual
accuracy, a relevant source citation, and correct scope/uncertainty: up to 72
points. This is a reviewer rubric, **not a claimed application score**. Arithmetic
and reasoning answers still require checking; a citation is not proof that a
model's calculation is correct.

## Documents and graph-workflow tests are different

The narrative packs test grounded company questions, supported roles, and
workspace boundaries. Mentioning a purchase order in a paragraph does not
automatically create a typed operational dependency graph.

To test the operational traversal, use the separate **Harbor Supply** scenario:

Open **Home → Try the example** to prepare it in a new workspace. The background
job saves its progress and can recover after interruption. The command-line
alternative is:

```bash
python scripts/run-graph-demo.py --url http://localhost:8080
```

Create an email/username account first. The script prompts for that account's
password without displaying it, creates a fresh synthetic workspace, imports
the supplied tables, and changes a delivery date. It verifies SO1/SO2 as affected
and two saved review tasks. SO3/SO4 have explicit date/stock exclusions; SO5 is
outside the assessed dependency paths. It signs its own API session out afterward; the
workspace stays available in the browser. A Google-only account has no password
for this helper; use a separate password-based test account.

Then inspect **Home**, open an investigation, follow the dependency path and
citations, complete a review task, and inspect **Company → Past decisions**.
This graph scenario runs without a chat-model key and is labelled accordingly.
It does not send customer messages or create tasks in another product.
