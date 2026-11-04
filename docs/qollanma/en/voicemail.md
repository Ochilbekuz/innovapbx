---
id: voicemail
title: Voicemail
group: apps
order: 20
path: /voicemail
summary: Voicemail for an extension or a shared box — PIN, email/Telegram notification, greeting audio.
---

# Voicemail

A voicemail box lets callers leave a message when a call goes unanswered. For example, route the
"closed" destination of [Business hours](/docs/timegroups) to a voicemail box.

## Where

Menu: **Applications → Voicemail**. Who can see it: the `extensions` permission can edit, others
can only view. The box owner listens to their own messages via [My portal](/docs/portal).

## Key concepts

- **Owner** — tied to a specific extension, **or** a shared/general mailbox that isn't tied
  to any extension and is only used as a routing destination.
- **Box number** — a 2–10 digit identifier; automatic (the extension's number) when linked
  to an extension, or entered manually for a general box.
- **PIN** — the password used to access the box from a phone.
- **Notification (email/Telegram)** — sent when a new message arrives; can attach the
  audio file.
- **Greeting audio** — played to the caller; the default greeting plays if none is chosen.
- **Phone codes**: `*97` to listen to your own box, `*98` to listen to another extension's
  box (standard feature codes, changeable on the [Feature codes](/docs/featurecodes) page).

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Owner | Extension or general box | — |
| Extension | If owner = Extension, chosen from extensions without a box yet | — |
| Box number | If owner = General box, 2–10 digits | — |
| PIN | Required on create, 4–8 digits; blank on edit keeps it unchanged | — |
| Email | Optional notification address | — |
| Notify by email | — | Default: off |
| Notify by Telegram | — | Default: off |
| Telegram chat ID | — | E.g. `123456789` or `@channel_name` |
| Attach audio | — | Default: off |
| Greeting audio | — | Blank = default greeting |

## How to

### Create a box for an extension
1. Click **Create box**, choose **Owner = Extension**, and pick an extension without a
   box yet.
2. Enter a **PIN** (4–8 digits), enable email/Telegram notifications if needed.
3. Click **Create**.

### Create a general box
1. Choose **Owner = General box** and enter a **box number** manually, e.g. `200`.
2. Enter a **PIN** and notification settings.
3. Click **Create** — a general box can be selected as a destination on [Business
   hours](/docs/timegroups), [Inbound routes](/docs/inbound), IVR, and more.

### Enable email/Telegram notifications
1. Open edit, enter an email and enable **Notify by email**, or enter a Telegram chat ID
   and enable **Notify by Telegram**.
2. Optionally enable **Attach audio**.

### Set the greeting
1. First upload the message to the [Audio library](/docs/audio).
2. Then choose it in the **Greeting audio** field when editing the box.

### Listen to or delete messages (via the panel)
1. Open the box row and view the **Messages** list.
2. Click **Mark as heard**, or the trash icon to delete.

### Delete
1. Click the trash icon on the box row.
2. If the box is used elsewhere as a destination (a route/IVR), deletion is blocked —
   remove those links first.

> [!TIP]
> The extension owner can listen via a phone (`*97`) or through the browser via [My
> portal](/docs/portal).

> [!WARNING]
> Leaving the PIN blank on edit keeps the old PIN unchanged — enter a full new value to
> change it.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Extension not shown in the list | It already has a box | Delete the old one or choose a different extension |
| Email/Telegram notification isn't arriving | The channel is disabled or the address/chat ID is wrong | Check the settings and confirm SMTP/Telegram is connected in [Integrations](/docs/integrations) |
| `*97`/`*98` doesn't work | The feature code is disabled or changed | Check the current code on [Feature codes](/docs/featurecodes) |
| Can't delete the box | It's used in a route or IVR | Remove those links first |

## Related sections

- [Audio library](/docs/audio)
- [My portal](/docs/portal)
- [Feature codes](/docs/featurecodes)
- [Business hours](/docs/timegroups)
- [Integrations](/docs/integrations)
