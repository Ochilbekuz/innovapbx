---
id: phonebook
title: Phonebook
group: apps
order: 80
path: /phonebook
summary: A contact list that shows a name/company instead of the raw number on inbound calls.
---

# Phonebook

The **phonebook** is a list of external contacts (customers, partners). When one of these saved
numbers calls, the panel and compatible SIP phones show the contact's name instead of the raw
number.

## Where

Menu: **Applications → Phonebook**. Who can see it: users with the `routing` permission can
edit, others can only view.

## Key concepts

- **Contact** — a name (required), company and note (optional), and one or more
  numbers.
- **Numbers** — each contact can have several numbers, each with an optional label
  (e.g. "Mobile", "Work").
- **CSV import/export** — export the whole phonebook to a file, or add/update many
  contacts at once from a file.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Name | Contact name | Required, up to 128 characters |
| Company | Which organization it belongs to | Optional, up to 128 characters |
| Note | Additional remark | Optional, up to 512 characters |
| Numbers | One or more numbers for the contact | Each can have an optional label (e.g. "Mobile") |

## How to

### Add a new contact
1. Click **New contact**.
2. Enter the name, and a company/note if needed.
3. Click **Add number** and enter the number(s) and an optional label.
4. Click **Add**.

### Edit a contact
1. Click the edit icon on the row, change the fields, and click **Save**.

### Search
1. Enter a name, company, or part of a number in the search field.

### Export via CSV
1. Click **CSV export** — the whole phonebook downloads as a file.

### Import via CSV
1. Click **CSV import** and choose a file.
2. The system first shows a **preview** of the changes (nothing is saved yet) — the
   number of new, updated, and skipped rows, and the error count, are shown.
3. If the result looks right, click **Apply** — the changes are saved.
4. The file must have `name`, `company`, `note`, and `numbers` columns; in the `numbers`
   column, multiple numbers are separated by `;` and a number/label pair by `:` (e.g.
   `998901112233:Mobile;998712223344:Work`).

> [!TIP]
> During import, a row matching an existing number **updates the existing contact**
> instead of creating a new one (matched by number).

> [!WARNING]
> Import is a single all-or-nothing operation: if the file has a serious error, **no row
> is saved** — check and fix the error list from the preview first.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| The caller's name doesn't show on a call | The number isn't in the phonebook, or the format doesn't match | Add the number to the contact in the correct format |
| An import row shows "error" | The `name` column is empty | Fill in the name field on every row |
| Import updated the wrong contact or created a new one | The number's format differs from the stored one (doesn't normalize to match) | Enter the number in the correct, international format |
| Can't delete a contact | — (the phonebook isn't used elsewhere, deletion is unrestricted) | — |

## Related sections

- [Blacklist](/docs/blacklist)
- [CID lookup sources](/docs/cidsources)
- [Call history](/docs/cdr)
