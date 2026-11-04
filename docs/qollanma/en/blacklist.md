---
id: blacklist
title: Blacklist
group: apps
order: 50
path: /blacklist
summary: Block inbound calls by number, including rejecting hidden (anonymous) numbers entirely.
---

# Blacklist

The **blacklist** automatically rejects inbound calls based on the caller's number. For example: add a
persistently annoying telemarketing number to the list, and it will no longer be able to reach the
system at all.

## Where to find it

Menu: **Applications → Blacklist**. Who sees it: users with the `apps` permission can edit; everyone
else can only view.

## Core concepts

- **Number** — the caller number to block; before saving, the system normalizes it to a canonical form
  (digits `0-9` only, 3–15 digits).
- **Reason** — an optional note explaining why the number is blocked (e.g. "spam").
- **Block hidden/anonymous numbers** — a separate toggle; when enabled, all calls without a visible
  caller ID (hidden, "anonymous," "restricted," etc.) are rejected. Technically this is just a regular
  list entry too — a special `anonymous` value is stored instead of a number, and shown separately in the
  table.
- Blocking works in **real time** — Asterisk checks the list directly before routing an inbound call, no
  separate "apply" step is needed.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Number | The caller number to block | `+998901234567`; normalized to 3–15 digits on save |
| Reason | A note explaining why it's blocked | Optional, e.g. `spam` |
| Block hidden/anonymous numbers | Reject calls without a caller ID | Default — disabled |

## How to

### Add a number to the blacklist
1. Click **Add**.
2. Enter the caller number in the **Number** field (e.g. `+998901234567`).
3. Enter a **Reason** if needed.
4. Confirm **Add** — the number is blocked immediately.

### Block hidden/anonymous numbers
1. Turn on the **Block hidden/anonymous numbers** toggle above the table.
2. All calls that don't send a caller ID (hidden, anonymous) are now automatically rejected.
3. Turning the toggle off lets such calls through normally again.

### Remove a number from the list
1. Click the trash icon at the end of the row and confirm.
2. The number is unblocked immediately and can call again.

> [!TIP]
> Use the search field to quickly find an entry by number or reason.

> [!WARNING]
> If a number is already on the list, adding it again causes an error ("This number is already on the
> blacklist") — check the existing entry first.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Invalid number format" error | The entered value didn't normalize to 3–15 digits | Enter the number in a valid format, without letters/symbols |
| "This number is already on the blacklist" | The number was already added | If you need to edit the existing entry, delete it and re-add it |
| The number still gets through | It's arriving in a different format (e.g. with a carrier prefix) | Enter the number in full, international format when adding |
| Hidden numbers still get through | The toggle is off, or the carrier passes the caller ID differently | Check that the toggle is enabled; ask your carrier about caller ID handling |

## Related sections

- [Inbound routes](/docs/inbound)
- [CDR (call history)](/docs/cdr)
