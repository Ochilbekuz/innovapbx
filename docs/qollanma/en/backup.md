---
id: backup
title: Backups
group: system
order: 50
path: /settings/backup
summary: Create manual/automatic backups, store them locally or on S3/SFTP, set an encryption passphrase, restore from a file.
---

# Backups

Back up the system's full state (configuration, call history, sound files, voicemail, call recordings,
certificates) and restore it when needed — all managed from here. Backups can be created automatically on
a schedule or manually, and copied to local disk as well as an S3 or SFTP server.

## Where
Menu: **System → Backups**, three tabs: **Backups**, **Schedule & storage**, **Restore from file**. Who
can see it: everyone can view, but only a user with `*` (full administrator) permission can create,
delete, restore backups and change settings.

## Key concepts

- **Component** — what a backup includes: Configuration, Call history, Sound files,
  Voicemail, Call recordings (usually the largest), Certificates.
- **Backup kind**: Scheduled (automatic), Manual, Pre-restore (a safety copy taken
  automatically before every restore), Uploaded (an `.ibk` file uploaded through the restore-from-file flow).
- **Copies** — each backup can be copied to multiple targets (Local, S3, SFTP); each
  target has its own status: Pending, OK, Failed, Deleted.
- **Backup passphrase** — all backups are encrypted with this passphrase. You can't create a
  new backup until a passphrase is set. **If you lose the passphrase, existing backups can't be restored.**
- **`.ibk` file** — the backup file format uploaded for restoring.
- **Compatibility check (inspect)** — before restoring an uploaded file, the system compares it
  against the current system version and content, and shows compatibility and any warnings.
- **Pre-restore backup** — the current state is saved automatically before any restore —
  if something goes wrong, you can roll back to this copy.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| **Automatic schedule** → Enabled | Turns the scheduled backup on/off | — |
| Frequency | Daily / Weekly | — |
| Day of week | Only when "Weekly" is selected | — |
| Time | When the backup starts | — |
| Which parts | Components included in the scheduled backup | — |
| **Local storage** → How many recent copies to keep | Older local copies beyond this count are deleted | — |
| **S3** → Endpoint/Region/Bucket/Prefix/Access key/Secret key/Path-style | Connection to an S3-compatible store | — |
| **SFTP** → Host/Port/User/Password/Private key/Folder | Connection to an SFTP server | — |
| How many recent copies to keep (S3/SFTP) | Cleans up older copies at that target | — |
| **Backup passphrase** → Current passphrase / New passphrase | Sets/changes the encryption passphrase | At least 12 characters |

## How to

### Create a backup now
1. On the **Backups** tab, click **Back up now**.
2. Select the components you need (at least one must be selected); choosing **Call recordings**
   shows a warning about increased size and time.
3. Click **Start** — a progress banner appears, followed by a success/partial/failure message
   when it finishes.

### Download, fetch locally, or delete a backup
1. If a local copy is ready in the list row, click the **download** icon to save the file to
   your computer.
2. If only a remote (S3/SFTP) copy is ready, click the **fetch locally** icon to copy it
   locally first, then download it.
3. Remove a backup you no longer need with the **delete** (trash) icon — confirm in the
   dialog; this action **cannot be undone**.

### Restore from a backup in the list
1. Click the **restore** icon on the row you need.
2. In the dialog, enter the backup passphrase (if encrypted) and type exactly
   **"TIKLASH"** in the confirmation field.
3. Click **Restore**. If there are active calls right now, the system warns you — choosing
   **Restore anyway** drops them.
4. Once the restore finishes, every user is signed out and returned to the login page.

### Restore from a file
1. On the **Restore from file** tab, choose the `.ibk` file and click **Upload**.
2. Enter the backup passphrase if needed and click **Inspect** — the system shows the file's
   contents (creation date, version, server, components) and whether it is **compatible/incompatible
   with the current system**.
3. If incompatible, the restore cannot proceed. If compatible, click **Continue to restore**
   and follow the same confirmation flow as restoring from the list (type "TIKLASH").

### Set up the automatic schedule and storage targets
1. On the **Schedule & storage** tab, enable **Automatic backup schedule** and set the
   frequency/day/time and components.
2. Under **Local storage**, enter how many recent copies to keep.
3. If needed, enable the **S3** and/or **SFTP** blocks and enter the connection details.
4. Click **Test connection** on each one to confirm it's configured correctly.
5. The first time you connect to SFTP, the server's fingerprint is shown — only click
   **Yes, trust it** once you're sure it's the right server.
6. Click **Save**.

### Set or change the backup passphrase
1. In the **Backup passphrase** section (shown as **Not set** if none exists yet), enter a
   new passphrase (at least 12 characters).
2. If a passphrase is already set, first enter the **Current passphrase** to confirm.
3. Click **Save passphrase**.

## Tips and limits

> [!WARNING]
> If you lose the backup passphrase, existing backups **cannot be restored by any means** —
> keep it somewhere reliable (e.g. a password manager).

> [!WARNING]
> Restoring **completely replaces** the current data and signs out every user. A safety
> backup of the current state is taken automatically beforehand, but it's best to do this during
> low-traffic hours.

> [!TIP]
> **Call recordings** are usually the largest component — if you want to back up configuration
> and settings frequently, you can exclude this component from the automatic schedule.

- A **backup passphrase** must be set before you can create a backup — otherwise a warning
  appears on the page.
- After every successful restore, a link to the "pre-restore backup" is saved in the
  **Restore history** — you can roll back to it again if needed.
- Leaving the secret key/password fields blank for S3/SFTP keeps the previously saved value unchanged.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Could not create backup" | No backup passphrase set | Set one on the **Schedule & storage** tab |
| S3/SFTP "Connection failed" | Wrong details or the network is blocking it | Check the endpoint/keys or host/port/user |
| "Server fingerprint differs from the previous one" | The SFTP server changed, or a possible MITM risk | Confirm only if you're sure the server genuinely changed |
| "Not compatible with the current system" | The backup came from a different system version | Restoring this file isn't recommended; compare versions |
| Restore says "There are active calls" | Calls are in progress right now | Wait for a quiet period, or choose **Restore anyway** |
| Restore failed, error | Server error or a corrupted file | Read the error message; try again from the **pre-restore backup** |

## Related sections

- [Configuration revisions](/docs/revisions)
- [Migration](/docs/migration)
- [Audit log](/docs/audit)
- [Troubleshooting](/docs/muammolar)
