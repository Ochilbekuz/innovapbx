---
id: update
title: Update
group: system
order: 120
path: /settings/update
summary: Check for a new version and update with one click from the panel — live progress, log, and automatic backup.
---

# Update

When a new version of Innova PBX is released, you can install it directly from the panel without needing
terminal access. An **automatic backup** is taken before updating, progress is shown step by step (backup
→ code → install → restart), and any error is reported along with the reason and log.

## Where to find it
Menu: **System → Update**. Who sees it: only a user with the `*` (full administrator) permission.

## Core concepts

- **Update agent** — a service running on the server that performs the actual update. If the agent isn't
  found (typically in development environments), the panel shows this and suggests running
  `sudo innova-update` from the terminal.
- **Current version** — the version number currently installed on the server, and when it was last
  checked.
- **New version and changelog** — if a check finds a new version, its number and the changelog text
  (headings, lists, bold/code formatting supported) are shown.
- **Confirmation dialog** — before starting the update, you must **manually type** the version number to
  confirm — this protects against accidentally clicking the button.
- **Steps** — Backing up → Fetching code → Installing → Restarting; each step is marked on a progress
  stepper.
- **Interruption during restart** — during this step the panel won't respond from the server for a
  while; this is called out explicitly as **normal**, not an error.
- **Log** — technical output during the update refreshes live (every 2 seconds); scrolling up manually
  stops auto-scroll, and **Jump to end** brings it back.
- **Result** — on success, "Updated" is shown along with a button to refresh the page; on failure, the
  error reason, the backup filename (if any), and a button to view the log are shown.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Current version | The version currently installed | — |
| Last checked | When it was last checked | Not checked yet |
| New version | The new version number found | — |
| Type the version number (confirmation) | Must match exactly to start the update | — |

## How to

### Check for an update
1. Click **Check**.
2. If a new version is found, its number and changelog appear; if not, "You're on the latest version" is
   shown.

### Start an update
1. While a new version is shown, click **Update**.
2. Read the warnings in the dialog: an automatic backup will be taken, the process takes 5–15 minutes, and
   calls may be interrupted for ~1 minute.
3. Type the shown version number into the field **exactly**.
4. Click **Start** — the process begins immediately, with live steps and log.

### Monitor progress
1. Watch the current step above (Backup/Code/Install/Restart).
2. If the panel doesn't respond for a while during the restart step, wait — this is expected.
3. Scroll the log up/down as needed; click **Jump to end** to return to the bottom.

### View the result
1. On success, click **Refresh page** — the panel reloads on the new version.
2. On failure, read the error reason, and click **View log** if needed to see the full text.

## Tips and limitations

> [!WARNING]
> Do not **manually shut down** or reboot the server during the update — this can interrupt the process
> and leave the system in a half-updated state (an "Interrupted" error).

> [!TIP]
> Schedule updates for a time when call traffic is low — calls may be interrupted for about 1 minute
> during the process.

- If the server doesn't have the update agent installed, you can't update from this page — use
  `sudo innova-update` from the terminal instead.
- The version confirmation field must match exactly — the button stays disabled otherwise.
- If the backup fails, the code hasn't been changed yet — the system keeps running as before.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Panel-based updates are not set up" | The server has no update agent | Use `sudo innova-update` from the terminal |
| "Source not configured" | No Git repository or upstream found | Check the reason with `innova-update --check` in the terminal |
| "Failed to fetch" (fetch_failed) | Network or permission error | Check your internet connection and try again |
| "There are unsaved changes in the code" | Manual changes exist on the host | Contact your administrator |
| "Backup failed" | Not enough disk space, or another reason | Check disk space and try again — the code hasn't changed yet |
| "Installation error" | The step after backup failed | Contact your administrator — a manual restore from backup may be needed |
| "Process interrupted" | The server restarted before the previous update finished | Check the status and try again |
| "Version number doesn't match" | An incorrect number was typed in the confirmation field | Type the shown version number exactly |
| "The page was out of date" | The state changed elsewhere (409) | The state was refreshed automatically — check again |

## Related sections

- [Backups](/docs/backup)
- [System status](/docs/status)
- [Audit log](/docs/audit)
