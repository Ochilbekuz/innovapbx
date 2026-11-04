---
id: quality
title: Quality scoring
group: reports
order: 30
path: /quality
summary: Score operators' calls against an evaluation checklist; view summaries and statistics.
---

# Quality scoring

Monitor how operators talk to customers: score each call against a ready **evaluation
checklist**, then view the average score by extension. For example, answer questions like
"Followed the greeting standard?" and "Resolved the issue?" — the call gets a percentage score.

## Where

Menu: **Reports → Quality scoring**. Everyone can view, but only `reports:edit` permission can
create/edit checklists and create/edit/delete evaluations — without it, a notice reads "You
don't have permission to manage quality control — view only."

## Key concepts

- **Checklist** — a template with one or more criteria; each criterion has a type (**Yes
  / No** or **Rating 1–5**), its own **weight**, and if marked **Critical**, failing just that
  one criterion zeroes the overall score.
- **Evaluation** — the answers filled in for one call against one checklist, plus a
  score percentage (0–100%) and an optional comment.
- **Score color**: ≥80% green, 50–79% yellow, <50% red.
- One call can be evaluated multiple times, even with different checklists.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| **Checklist** → Name | — | — |
| Active | Selected by default for new evaluations | — |
| Criterion text | — | e.g. "Followed the greeting standard" |
| Type | Yes/No or Rating 1–5 | — |
| Weight | The criterion's share of the overall score | — |
| Critical | If checked, failing it zeroes the whole score | Default: off |
| **Evaluation** → Checklist | Which checklist is used | — |
| Comment | Optional free text | — |

## How to

### Create a new checklist
1. On the **Checklists** tab, click **New checklist**; enter a name and set **Active**.
2. Use **Add criterion** to add each question: text, type (Yes/No or Rating 1–5), weight,
   and the **Critical** flag if needed.
3. Click **Add**.

### Evaluate a call
1. On the [Call history](/docs/cdr) page, click **Evaluate** on the row (or open an
   existing evaluation via **Edit** on this page's Evaluations tab).
2. In the panel that opens, choose a **Checklist** and answer each criterion (Yes/No or a
   1–5 score) — the save button stays inactive until all criteria are answered.
3. Optionally write a **Comment**, then click **Save evaluation** — the score percentage
   is calculated automatically.

### Edit or delete a checklist/evaluation
1. Click the pencil icon to edit, or the trash icon to delete, on the row you need.
2. Confirm again in the delete dialog — this action can't be undone.

### View the summary
1. Open the **Summary** tab to see the total evaluation count and average score, with a
   breakdown by extension below.

## Tips and limits

> [!TIP]
> Only use the **Critical** flag for cases where "breaking this rule should void the
> whole score" — e.g. threatening a customer — otherwise average scores drop artificially.

> [!WARNING]
> Deleting an evaluation or checklist can't be undone.

- A checklist stays available in the history for past evaluations even if deactivated —
  it just isn't selectable for new ones.
- A checklist must have at least one criterion, with every criterion's text filled in —
  otherwise it won't save.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| No "New checklist" button | You lack `reports:edit` permission | Ask an admin for the permission ([Users and roles](/docs/rollar)) |
| Can't save the evaluation | Not every criterion was answered | Answer Yes/No or 1–5 for every criterion |
| "This checklist has no criteria" | The checklist was created empty | Edit the checklist and add at least one criterion |
| Average score much lower than expected | The Critical flag is overused | Keep the Critical flag only on truly necessary criteria |

## Related sections

- [Call history](/docs/cdr)
- [Analytics](/docs/analytics)
- [Users and roles](/docs/rollar)
