---
id: revisions
title: Configuration revisions
group: system
order: 25
path: /settings/revisions
summary: A revision history created every time a setting is saved — view diffs and roll back to a previous state.
---

# Configuration revisions

Almost every time a setting is saved in the system (a trunk, route, extension, etc.), a new **revision**
is created — like a "version history." If a change later causes a problem, you can roll back to a
previous state from here.

## Where to find it

Opened via the **revision badge** (current revision number) in the page header, or **System →
Revisions**. Who sees it: only a user with `*` (full administrator) permission.

## Core concepts

- **Revision** — a snapshot of the entire configuration state at one point in time, shown as `r<number>`.
- **Status**: Applied (successfully took effect), Rolled back (reverted later), Applying (currently
  being applied).
- **Diff** — compares the selected revision against the **previous one** or the **current state**,
  showing which lines were added (+) or removed (−).

## How to

### View revision history
1. Select the revision you need from the list on the left side of the page — each one shows the date,
   user, and a short note.
2. On the right, choose **Compare with previous** or **Compare with current** to see the diff (red —
   removed lines, green — added lines).

### Roll back to a previous state
1. Select the revision you need.
2. Click **Roll back to this state**.
3. Read the warning dialog and confirm **Roll back**.
4. The system restores the current configuration to the selected revision's state and applies it as a
   **new revision** (older revisions are not deleted).

## Tips and limits

> [!WARNING]
> Rolling back **replaces** the current configuration — all changes made after the point you're rolling
> back to are lost (but they remain saved as revisions in the history, and you can roll forward to them
> again if needed).

> [!TIP]
> Review the **diff** carefully before confirming a rollback, so you know exactly what you're reverting.

- Every rollback is recorded as a separate entry in the [Audit log](/docs/audit).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Failed to load" | Lost connection to the server | Click **Retry** |
| "No diff found — this may be the first revision" | There's no earlier revision before the selected one | This is normal, don't worry |
| Couldn't roll back | A server error or network issue | Read the error text and try again; contact an administrator if it persists |

## Related sections

- [Audit log](/docs/audit)
- [Dashboard](/docs/dashboard)
