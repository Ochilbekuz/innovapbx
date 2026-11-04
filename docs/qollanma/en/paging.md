---
id: paging
title: Paging / Intercom
group: apps
order: 70
path: /paging
summary: Broadcast a voice announcement to multiple extensions at once (paging group) and direct intercom calls.
---

# Paging / Intercom

A **paging group** lets you broadcast a voice announcement to several extensions (rooms) at once by
dialing a single number. For example, you could create an "All-staff announcement" group linked to every
department's phones, and announce "Lunch break has started" to the whole office by dialing one number.

## Where to find it

Menu: **Applications → Paging / Intercom**. Who sees it: users with the `routing` permission can edit;
everyone else can only view (shown with a **"You don't have permission to manage paging groups"** warning)
— even though the screen appears under "Applications" in the menu.

## Core concepts

- **Number** — dialing this number connects to all members at once (a voice announcement is played).
- **Two-way** — when enabled, members can answer and talk back; when disabled, it's a one-way
  announcement (members hear it but can't respond).
- **Skip if busy** — when enabled, a busy member doesn't receive the announcement.
- **Beep** — a short tone played before the announcement starts.
- **Intercom** (`*80<extension>`) — unlike a paging group, this feature code connects directly to one
  specific extension with auto-answer (default `*80`, changeable in [Feature codes](/docs/featurecodes)).

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Name | Group name | Up to 128 characters |
| Number | The number dialed to connect to the group | 1–10 characters of `0-9*#` |
| Two-way | Can members answer and talk | Default — disabled (one-way) |
| Skip if busy | A busy member doesn't receive the announcement | Default — enabled |
| Beep | A short tone before the announcement | Default — enabled |
| Members | The extensions that receive the announcement | Selected from the extension list |

## How to

### Create a new paging group
1. Click **New group**, enter a name and number.
2. Select the members (extensions) you need.
3. Change the **Two-way**, **Skip if busy**, and **Beep** settings if needed.
4. Click **Add**.

### Edit a group
1. Click the edit button on the row, change the fields you need, and click **Save**.

### Call a group
1. Dial the group's number from any extension — all members are connected at once.

### Connect directly to one extension via intercom
1. Dial `*80<extension>` (e.g. `*80205`) — the other side's device auto-answers (if the device supports
   intercom).

### Delete
1. Click the trash icon at the end of the row and confirm — the group is permanently deleted.

> [!WARNING]
> If more than one device is registered on the same extension in a paging group (e.g. a desk phone +
> softphone), currently **only the first registered device** will ring — because Asterisk's `Page()`
> application checks each destination's "device state" beforehand and doesn't support a one-number,
> multi-device setup (identified in 1.0.15, not yet fixed). Keep this in mind when adding staff with
> multiple devices to a paging group.

> [!TIP]
> For listen-only announcements (e.g. workshop speakers), turn off **Two-way** — otherwise every member's
> microphone opens and noise may mix in.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Only one phone rings for a multi-device staff member | Paging groups currently only reach the first device (a known limitation) | Register the employee's primary device first |
| A busy member still gets the announcement | **Skip if busy** is disabled | Enable this setting in the group |
| Intercom doesn't work | The other device doesn't support auto-answer, or the code was changed | Check the device settings and the current code in [Feature codes](/docs/featurecodes) |
| Can't delete the group | It's used elsewhere (a route, IVR) | Remove those links first |

## Related sections

- [Feature codes](/docs/featurecodes)
- [Extensions](/docs/extensions)
- [Ring groups](/docs/ringgroups)
