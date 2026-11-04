---
id: extensions
title: Extensions
group: users
order: 10
path: /extensions
summary: Create and configure staff SIP extensions — Follow Me, voicemail, and device pairing.
---

# Extensions

An extension is the SIP account that belongs to a staff member: a desk phone or browser softphone
connects through it to place and receive calls. Here you can create extensions, manage the SIP secret,
configure call settings (DND, forwarding, recording), and set up Follow Me, voicemail, and devices all in
one place.

## Where

Menu: **Users → Extensions**. Who can see it: the `extensions:view` permission. Adding/editing/deleting/
rotating the secret/importing requires `extensions:edit`; without it, the notice **"You don't have
permission to manage extensions — view only"** is shown.

## Key concepts

- **SIP login/password** — the credentials needed to connect a phone or softphone; the password
  is shown in full only once, right after it is created or rotated — it can't be viewed again afterward.
- **Browser softphone (WebRTC)** — when enabled, the browser softphone connects to this
  extension instead of a physical phone; a device can no longer be paired to this extension via QR.
- **Recording policy** — set **independently** for incoming and outgoing calls: **Always**,
  **Never**, **On demand** (toggled from the phone with `*1`).
- **Call settings** — DND, forward always/when busy, pickup group, outbound call permission,
  outbound CallerID, call waiting — all of these take effect immediately, no restart required.
- **Follow Me** — rules for ringing other numbers in sequence when there's no answer (details below).
- **Connect a phone (QR)** — pair the mobile Linphone app without typing a password, via QR;
  this button is disabled for extensions with WebRTC enabled.
- **CSV import/export** — bulk-create or update extensions from a file; import is previewed as
  a "dry run" before anything is saved, and new passwords are only ever provided in a one-time
  downloadable CSV file.

## Fields

**List** table:

| Column | Shows |
|---|---|
| **Number** | The extension number (with a WebRTC badge) |
| **Name** | Staff member/department name |
| **Status** | Online/offline/disabled (updates live) |
| **Enabled** | Yes/No |
| **Calls** | DND, forwarding, toll-block badges |
| **Updated** | Last changed time |

**New extension** dialog:

| Field | What it does | Example / default |
|---|---|---|
| **Number** | Optional — leave blank to auto-pick the first free one | e.g. `101` |
| **Name** | Staff member/department name | — (required, up to 60 characters) |
| **SIP password** | Suggested automatically; can be changed/regenerated | 8–64 characters, letters + digits, must not contain the extension number |
| **Advanced settings** (expandable) | WebRTC, recording policy, call settings | — |

**Edit** dialog adds: **Enabled**, **Follow Me**, **Voicemail**, **Devices** sections and
**Change SIP password**.

## How to

### Create a new extension
1. Click the **New extension** button.
2. Enter the **Number** or leave it blank (auto-picked), enter the **Name**.
3. Review the SIP password — change it or **regenerate** it if needed.
4. If needed, expand **Advanced settings** to set WebRTC/recording/call settings.
5. Click **Create** — copy the SIP login/password/domain/port from the dialog that
   appears (this information is never shown again).

### Change the SIP password
1. Edit the extension, and in **Change SIP password** choose **Enter my own password**
   or **Generate a new random password**.
2. Enter the password (if entering your own), click **Save** — the new credentials are shown in
   a one-time dialog.

### Change call settings (DND, forwarding)
1. Edit the extension, and in the **Calls** section change the toggles/fields you need
   (DND, forward always/when busy, pickup group, outbound calls, CallerID, call waiting).
2. Click **Save** — the change takes effect immediately.

### Set up Follow Me
1. Edit the extension and enable the toggle in the **Follow Me** section.
2. Add internal/external numbers to the **Numbers** list (reorder by dragging), choose
   **How to ring** (**All at once** or **One by one**).
3. If **One by one**, enter the **Ring time**; with **All at once**, you can also enable
   **Also ring the extension**.
4. Click **Save Follow Me**.

### Enable voicemail
1. Edit the extension and click **Enable** in the **Voicemail** section.
2. Enter a 4–8 digit **PIN** and confirm.

### Connect a phone via QR
1. In the list, click the QR icon on the row you need (disabled for extensions with WebRTC enabled).
2. Scan the QR code with the mobile Linphone app within 15 minutes — the link becomes invalid
   60 seconds after the phone fetches it.
3. If it expires, click **New QR**.

### Bulk import/export via CSV
1. Use **CSV export** to download the current list to a file.
2. Click **CSV import**, choose the file — the system previews the changes (count of
   new/updated/errors) **without saving** first.
3. If there are no errors, click **Apply**; passwords for new extensions are only provided in
   the CSV file downloadable at this point — they can't be retrieved again afterward.

### Delete an extension
1. Click the **Delete** icon on the row, read the warning and confirm.
2. If the extension is used by an [inbound route](/docs/inbound) or elsewhere, deletion is
   rejected and the places it's used in are listed.

## Tips and limits

> [!WARNING]
> A newly created or rotated SIP password is shown **only once** in that dialog — once closed, it
> can't be viewed again, only regenerated.

> [!WARNING]
> A physical device can't be paired to an extension with **browser softphone (WebRTC)**
> enabled — the two don't work together, so the QR pairing button is disabled for such extensions.

> [!TIP]
> When bulk-adding via CSV import, review the **dry run** (unsaved) result first, fix any
> errors, then click **Apply** — the button is disabled while any row has an error.

> [!TIP]
> Call settings (DND, forwarding) can also be changed from the phone using `*`-codes — in that
> case, the new state appears after refreshing the page.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Password must be at least 8 characters" / "Password must not contain the extension number" and similar messages | The SIP password doesn't meet the requirements | Enter a password matching the shown rule, or generate a random one |
| Deletion rejected | The extension is used by an inbound route or elsewhere | Remove it from the listed places first |
| "This setting was changed elsewhere" | Follow Me/extension data was changed from another window | Click **Refresh** and save again |
| QR code expired | More than 15 minutes passed, or the phone didn't use it within 60 seconds | Click **New QR** and scan again |
| Import errors | Data in a CSV row doesn't match the expected format | Fix the file based on the row number and message shown, then re-upload |

## Related sections

- [Phone devices](/docs/devices)
- [My portal](/docs/portal)
- [Inbound routes](/docs/inbound)
