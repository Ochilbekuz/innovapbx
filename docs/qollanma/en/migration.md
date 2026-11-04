---
id: migration
title: Migration
group: system
order: 60
path: /settings/migration
summary: Migrate your configuration from a FreePBX server to Innova PBX using a 5-step wizard.
---

# Migration

A 5-step wizard lets you migrate extensions, trunks, queues, IVRs, routes, and similar settings from a
FreePBX server to Innova PBX without re-entering everything by hand: **Source → Analyze → Review →
Apply → Result**.

## Where to find it

Menu: **System → Migration**. Who sees it: anyone can view, but only a user with `*` (full
administrator) permission can start and apply an import.

## Core concepts

- **Export script** — a read-only script (`innova-fpbx-export.sh`) run as **root** on the FreePBX
  server; it doesn't change anything there and produces an `fpbx-export-*.tar.gz` bundle.
- **Source type**: upload the bundle file manually, or fetch it automatically over SSH — both lead to
  the same analysis step.
- **Analysis** — reads the uploaded bundle and builds a **plan** for the objects to migrate (extensions,
  trunks, queues, IVRs, routes, etc.); nothing changes in Innova at this stage.
- **Plan item and action**: each object is marked as **Create**, **Skip**, **Conflict** (an object with
  the same name/number already exists in Innova), or **Unsupported** (Innova doesn't support it).
- **Resolving conflicts** — a conflicting item's action can be changed to **Skip**, or (if the object
  wasn't manually created) to **Replace**.
- **Weak secrets** — extensions with SIP passwords shorter than 12 characters; by default these migrate
  unchanged (so phones don't need reprovisioning), but you can choose to replace them with new random
  passwords.
- **Apply** — actually writes the plan to Innova; an automatic backup of the current state is taken
  beforehand.
- **Result** — counts of created/skipped/warnings, a CSV report, and (if the import fails or needs to be
  undone) a link to restore the pre-import backup.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Bundle file | Must be `fpbx-export-*.tar.gz`/`.tgz` | — |
| **SSH** → Host/Port/User | Connection to the source server | Default port: 22 |
| Password / Private key | At least one of these is required | — |
| Replace weak secrets | When enabled, weak SIP passwords are regenerated | Default — disabled |
| Confirmation phrase | Must be typed exactly to start applying | `MIGRATE` |

## How to

### Step 1 — Source
1. On the **Upload bundle** tab, first click **Download script**, then run
   `bash innova-fpbx-export.sh` as `root` on the FreePBX server — this produces the bundle file.
2. Select the resulting `.tar.gz`/`.tgz` file and click **Upload and continue to analysis**.
3. Alternatively, on the **Fetch over SSH** tab, enter the host/port/user and a password or private key,
   click **Test connection**, then **Fetch and continue to analysis**. On first connection the server's
   fingerprint is shown — confirm it's correct before continuing.

### Step 2 — Analyze
1. Click **Start analysis** — progress is shown; nothing changes in Innova yet, only the plan is built.

### Step 3 — Review
1. The **By type** cards show the total count and number of conflicts for each object type.
2. Filter the plan table by type/action, find the items you need, and change conflicting rows' action to
   **Skip**/**Replace**/**Create** (an object created manually can't be replaced — only skipped).
3. In the **Weak secrets** section, enable **Replace weak secrets with new random passwords** if needed.
4. Click **Continue to apply**.

### Step 4 — Apply
1. If a backup password hasn't been set, the page warns you — go to [Backups](/docs/backup) settings and
   set one first.
2. Type **"MIGRATE"** exactly into the confirmation field.
3. Click **Apply** — progress is shown as the process runs.
4. If the plan is stale (something changed in Innova in the meantime), the system offers **Re-analyze**
   — refresh the plan and re-confirm the review.

### Step 5 — Result
1. Review the counts of created/skipped/warning items.
2. Save the full details with **Download report (CSV)**.
3. If the result failed, or the import made an unintended change, you can roll back using the **Cancel —
   restore pre-import backup** link.
4. Use **Start new import** to run the wizard again from the beginning.

### View/delete previous import history
1. See prior imports in the **Migration history** table at the bottom of the page.
2. Delete a bundle file you no longer need with the trash icon — this only deletes the **file** from
   disk; the import result (plan, report) is kept.

## Tips and limits

> [!WARNING]
> The bundle also contains **SIP passwords** — the file is deleted from the server after the import
> finishes, but it must be transferred over a trusted channel while uploading.

> [!TIP]
> Nothing in Innova changes during the **Analysis** and **Review** steps — review the plan as much as
> you need, resolve conflicts carefully, and only then move on to **Apply**.

- Only one backup/migration job can run at a time — **Apply** is blocked while another is in progress;
  wait for it to finish.
- You can't reach the **Apply** step until a backup password is set (an automatic backup is required
  before importing).
- A conflict with an object created manually (in Innova itself) can only be **skipped**, not
  **replaced**.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Select a .tar.gz or .tgz file" | A file in a different format was uploaded | Select the bundle produced by the FreePBX export script |
| SSH "Connection failed" | Host/port/user/password is incorrect | Check the details and try again |
| "State changed in Innova before the job could start" | Another change was made after the analysis | Click **Re-analyze** |
| "Another backup/migration job is currently running" | A parallel job is in progress | Wait for the previous job to finish and try again |
| An action failed on a plan item | A server error, or the object's state changed | Re-analyze to refresh the plan |
| Result "Failed" | An error occurred during the import | Read the error text; use **Cancel** to restore the pre-import state |

## Related sections

- [Backups](/docs/backup)
- [Configuration revisions](/docs/revisions)
- [Audit log](/docs/audit)
- [Troubleshooting](/docs/muammolar)
