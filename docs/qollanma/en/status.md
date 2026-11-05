---
id: status
title: System status
group: system
order: 70
path: /settings/status
summary: Disk space, trunks, internet/DNS, SIP interface status; clean up disk and reboot.
---

# System status

A page for seeing the server's current "health" at a glance: how full the disk is, whether trunks are
working, whether internet/DNS is available, SIP transports, and the number of registered devices. From
here you can also clean up the disk and reboot the server.

## Where to find it
Menu: **System → System status**. Who sees it: only a user with the `*` (full administrator) permission.

## Core concepts

- **Disk** — total used/free space and the breakdown by category (call recordings, backups, migration
  files, voicemail, logs); some categories are marked as **not manually cleanable**.
- **Trunks** — each trunk's status (working/problem) and the reason, if any.
- **Internet** — whether there's external connectivity, whether DNS is working, latency (ms), and the
  address being checked.
- **SIP interface** — whether the Asterisk service is running, which transports (UDP/TLS) are bound to
  which address, and how many devices are registered.
- **Disk cleanup** — free up space by deleting old call recordings, excess local backup copies, and
  uploaded FreePBX migration files; before deleting, the amount of space that will be freed is shown as a
  **preview**.
- **Reboot** — remotely reboot the server (administrators only; there is no shut-down button); if blocked for a reason
  (`readonly_reason`), the buttons are disabled.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Delete records older than this many days | Threshold for cleaning up call recordings | 180 days |
| Delete all but the last this many backups | Threshold for cleaning up local backup copies | 3 |
| Uploaded FreePBX migration files | If checked — all uploaded packages are deleted | Default: unchecked |
| `reboot` (confirmation) | Type this word to confirm the reboot | — |

## How to

### View the status
1. When the page opens, the disk, trunks, internet, and SIP cards load automatically.
2. If there's a problem (e.g. a trunk connection is down), the relevant card is shown in **red/warning**
   color.

### Clean up the disk
1. Click **Clean up disk** (the button turns red when disk space is running low).
2. Select the items you need: old call recordings (how many days old), excess backup copies (how many
   recent ones to keep), uploaded migration files.
3. After each change, the system automatically shows how much space will be freed (size and file count).
4. Click **Delete** and confirm — this action **cannot be undone**.

### Reboot the server
1. Click **Reboot**.
2. In the dialog, type the word **reboot** to confirm (to prevent accidental clicks; case-insensitive).
3. After confirming, the action runs after a short delay (a few seconds) rather than instantly — a
   message about this is shown.

## Tips and limitations

> [!WARNING]
> Rebooting ends all **active calls**. Remote shut-down was removed on purpose — a powered-off server
> would need physical access to start again.

> [!TIP]
> Before cleaning up the disk, check the amount shown in the **preview** — especially before reducing the
> number of backup copies, make sure enough copies remain to cover your needs.

- If the reboot button is **disabled**, the reason is shown on the page (`readonly_reason`) —
  for example, another system operation (backup/migration) might be running.
- Some disk categories (e.g. logs) are marked as **not manually cleanable** — they can't be deleted from
  this page.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Failed to load" | No connection to the server | Click **Retry** |
| Disk is full (red) | Call recordings/backups are taking up a lot of space | Delete old files with **Clean up disk** |
| Trunk red/problem | No connection to the carrier | Read the reason text, check [SIP & network](/docs/sip) settings |
| Internet "Disconnected" / DNS not working | Server network issue or DNS service is down | Check the server's network settings |
| "Type “reboot”" | Different text entered in the confirmation field | Type the word `reboot` |
| Reboot button is disabled | Blocked by `readonly_reason` | Resolve the shown reason and try again |

## Related sections

- [Backups](/docs/backup)
- [SIP & network](/docs/sip)
- [Network](/docs/network)
- [Troubleshooting](/docs/muammolar)
