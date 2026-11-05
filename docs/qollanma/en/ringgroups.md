---
id: ringgroups
title: Ring groups
group: routing
order: 40
path: /ringgroups
summary: Ring several extensions/external numbers at once or in sequence (e.g. an "Accounting" group).
---

# Ring groups

A **ring group** routes one call to several numbers at once: for example, when a call reaches the "Accounting" group, every staff member's phone in that department rings at the same time. Unlike a queue, there is no waiting/queuing logic here — it's simply "whoever picks up first."

## Where to find it

Menu: **Routing → Ring groups**. Who sees it: users with the `routing` permission can edit; everyone else can only view.

## Core concepts

- **Strategy** — how the call reaches members (see the table below).
- **Member** — can be an extension **or** an external number (such as a mobile phone); you can't combine both in one member.
- **Caller ID prefix** — text added before the inbound number on the agent's phone (e.g. "SALES: "), so the agent knows which group the call came from.
- **No-answer destination** — where the call goes if nobody picks up (or the set duration runs out).

## Fields

The edit drawer mirrors the FreePBX **Ring Groups** module and is split into five sections:
**General**, **Members**, **Ringing & announcements**, **Caller ID**, **Advanced**.

### General

| Field | What it does | Example / default |
|---|---|---|
| Name | Group name | — |
| Number | Optional — for direct dialing | 2–10 characters of `0-9*#` |
| Strategy | The ring order for members | Default — **Ring all** |
| Ring time (seconds) | How long to wait for an answer | 5–300, default 20 |

### Members

| Field | What it does | Example / default |
|---|---|---|
| Members | List of extensions and/or external numbers, in order | — |

### Ringing & announcements

| Field | What it does | Example / default |
|---|---|---|
| Announcement (before ringing) | Played to the caller before connecting to members | Optional, default — none |
| While ringing | Normal ringback, or music on hold (MOH) | Default — normal ringback |
| Music on hold class | Which MOH class plays when "While ringing" = MOH | Only shown when MOH is selected |
| Alert-Info | Tells a supporting IP phone to use a distinctive ringtone (SIP header) | Optional, e.g. `Internal` |
| Skip busy member | Does not ring a member who is already on a call | Default — off |
| Confirm calls | Requires the member to confirm pickup by pressing 1 | Default — off |
| Confirmation announcement | Played to the member before they confirm, when "Confirm calls" is on | Only shown when confirm calls is enabled |

### Caller ID

| Field | What it does | Example / default |
|---|---|---|
| Caller ID prefix | Added before the inbound number on the agent's screen | Optional, e.g. `SALES: ` |

### Advanced

| Field | What it does | Example / default |
|---|---|---|
| Call recording | Recording policy for calls through this group | Default — **don't change** (follows the extension's own setting) |
| If no answer | Destination used once time runs out | Required |

### Strategies

| Strategy | How it works |
|---|---|
| Ring all (`ringall`) | Rings all members at the same time (default) |
| Ring all, primary first (`ringall-prim`) | Same as `ringall`, but member 1 is treated as primary |
| Hunt (`hunt`) | Rings members one by one in list order, each for the ring time |
| Hunt, primary first (`hunt-prim`) | Same as `hunt`, but member 1 is treated as primary |
| Memory hunt (`memoryhunt`) | Rings the first member, then member 1+2, then 1+2+3... — earlier members keep ringing |
| Memory hunt, primary first (`memoryhunt-prim`) | Same as `memoryhunt`, but member 1 is treated as primary |
| First available (`firstavailable`) | Rings only the first member who isn't busy |
| First not on phone (`firstnotonphone`) | Similar to `firstavailable`, chosen by phone state |

> [!NOTE]
> The **"random"** strategy sometimes mentioned alongside Ring Groups in FreePBX actually only applies
> to the Queues module — it isn't a real Asterisk option for Ring Groups, so it was deliberately not
> added here.

## How to

### Create a new group
1. Click **Add group**, choose a name and strategy.
2. Add members via **+ Add extension**; to add an external number, enter it in the dedicated field (format `+998901234567`, 3–15 characters) and add it.
3. Choose the **If no answer** destination (e.g. voicemail).
4. Click **Add**.

### Add an external number
1. Enter the number in the "external" field below the member list, then add it.
2. An incorrectly formatted or already-added number will show an error.

### Change member order
1. Order matters for the `Hunt` or `Memory hunt` strategies — drag a row to the position you want.

### Link a ring group to an inbound route
1. On the [Inbound routes](/docs/inbound) screen, route a DID to this group.
2. Or select it as the destination in an IVR button/business-hours condition.

### Delete
1. Click the trash icon at the end of the row.
2. If the group is used elsewhere, deletion is blocked — remove those links first.

> [!TIP]
> Give each group its own **Caller ID prefix** — an agent who belongs to several groups can tell from the screen which route the call came through.

> [!WARNING]
> Ringing an external number can add extra cost on top of your regular carrier plan — don't set the **Ring time** excessively long.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Can't add an external number | Invalid format, or it's already added | Enter digits only, 3–15 characters, `+` optional |
| In `Memory hunt`, everyone rings at once | The ring time is too short, so the next member joins in too quickly | Increase the ring time |
| Can't delete the group | It's used in an inbound route or another destination | Remove those links first |

## Fields deliberately not ported from FreePBX

- **Ignore CF (forward)/CW (call waiting)/Call pickup** — their semantics overlap with the member's own
  device settings; Innova has no matching feature.
- **Too-late announce** — a separate announcement once the confirm-call window expires — limited extra
  value, since the confirm flow is already covered by "Confirmation announcement".
- **Change external CID / Fixed external CID** — these columns don't even exist in the real FreePBX
  database (legacy/unused), so they were not invented.

## Related sections

- [Inbound routes](/docs/inbound)
- [Extensions](/docs/extensions)
- [Business hours](/docs/timegroups)
