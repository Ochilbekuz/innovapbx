---
id: audit
title: Audit log
group: system
order: 20
path: /settings/audit
summary: A trail of every write action and login in the system — who changed what, and when.
---

# Audit log

A complete record of who did what in the system (who created, changed, or deleted something, logged in
or failed to log in, restored a backup, and so on). For example, if a trunk setting changed unexpectedly,
you can see exactly which user changed it, when, and both the old and new values.

## Where to find it

Menu: **System → Audit log**. Who sees it: only a user with `*` (full administrator) permission.

## Core concepts

- **Action type**: Created, Changed, Deleted, Logged in, Login failed, Restored, Restarted, Temporarily
  changed, Listen/join.
- **Object** — what the action applied to (e.g. `trunk`, `extension`, `user`).
- If detailed change information is available for an action, an eye icon appears on the row — click it
  to see the old/new values. Passwords and other secret values are masked with `***` in the log.
- The "Who" column shows **system** (without a user) for actions the system performed on its own.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Start / End | Date range | Default — last 30 days |
| Action | Filter by action type | Default — All |
| Object type | Free-text filter (optional) | `trunk`, `extension` |
| Search | Free search by login or object name (optional) | — |

## How to

### Find changes using filters
1. Set the **Start**/**End** date.
2. Choose an **Action** type if needed (e.g. only "Deleted").
3. Enter text such as `trunk` or `extension` into **Object type** to see only that kind of entry.
4. Enter a login or object name into **Search** for a quick match.

### View change details
1. Click the eye icon at the end of a row (only shown on entries that have details).
2. The opened dialog shows the **old** (red) and **new** (green) value for each changed field.

## Tips and limits

> [!TIP]
> If something suspicious happens (e.g. an unexpected configuration change), filter by **Action:
> Changed** and the relevant **Object type** to quickly identify the responsible user and the time.

- The log is read-only — you can't delete or edit anything from here.
- Password and other secret fields are always shown as `***` — the real value is never displayed.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "No entries match this filter" | The date range or filter is too narrow | Widen the filters or re-check them |
| The eye icon doesn't appear | No change details were saved for this entry (e.g. a login action) | This is normal — not every action type has details |

## Related sections

- [Configuration revisions](/docs/revisions)
- [Users & roles](/docs/rollar)
- [Security](/docs/security)
