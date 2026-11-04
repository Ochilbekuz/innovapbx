---
id: announcements
title: Announcements
group: routing
order: 60
path: /announcements
summary: Play a message to the caller, then route to another destination (e.g. "This call is recorded").
---

# Announcements

An **announcement** plays an audio message to the caller, then routes the call to a set next
destination. For example: play "Attention, this call is recorded for quality purposes," then
connect the call to a queue.

## Where

Menu: **Routing → Announcements**. Who can see it: users with the `routing` permission can edit,
others can only view.

## Key concepts

- **Audio file** — the message must first be uploaded as audio to the [Audio
  library](/docs/audio).
- **Next destination** — where the call goes once the message finishes (or is
  skipped).
- **Allow skipping** — if enabled, the caller can press `#` to skip the message without
  listening to the end.
- **Repeat key** — if the set key is pressed, the message plays again from the start.
- **Answer the call before playing** — if enabled, the call is marked "answered" before
  the message starts (important for billing/CDR — otherwise the call still counts as "unanswered"
  while the message plays).

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Name | Announcement name | Up to 128 characters |
| Audio file | The message played to the caller | Required |
| Next destination | Where the call goes after the message | Required — extension, queue, IVR, ring group, business hours condition, conference, another announcement, etc. |
| Allow skipping | Skip the message with `#` | Default: off |
| Repeat key | Replays the message from the start if pressed | A single `0-9*#` character, optional — none repeats it |
| Answer the call before playing | Marks the call as answered before the message | Default: on |

## How to

### Add a new announcement
1. First upload the message audio to the [Audio library](/docs/audio) (a reminder appears
   on the page if none is uploaded).
2. Click **Add announcement**, and choose a name and audio file.
3. Set the **Next destination** (required).
4. Configure skipping, the repeat key, and "answer the call before playing" if needed.
5. Click **Add**.

### Attach an announcement to an inbound route or IVR
1. On the [Inbound routes](/docs/inbound) screen, route a DID to this announcement.
2. Or select it as a destination on an IVR button/business hours condition.

### Delete
1. Click the trash icon at the end of the row.
2. If the announcement is used elsewhere, deletion is blocked and those links are shown —
   remove them first.
3. Calls routed to a deleted announcement now hear a "no answer" tone — clear the links
   before deleting.

> [!TIP]
> Turn on "Answer the call before playing" — otherwise the carrier may count the call as
> "unanswered" while the message plays (especially important for billing).

> [!WARNING]
> Don't select the same announcement as its own "Next destination" — the message could
> loop endlessly.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Adding an announcement is blocked | No audio has been uploaded yet | Upload a file to the [Audio library](/docs/audio) |
| Pressing `#` doesn't skip the message | "Allow skipping" is disabled | Edit the announcement and enable it |
| Can't delete the announcement | It's used in an inbound route, IVR, or another destination | Remove those links first |

## Related sections

- [Audio library](/docs/audio)
- [Inbound routes](/docs/inbound)
- [IVR](/docs/ivr)
