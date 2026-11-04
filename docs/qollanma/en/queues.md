---
id: queues
title: Queues
group: routing
order: 30
path: /queues
summary: Distribute calls among agents — strategy, members, hold music, SLA, live status.
---

# Queues

A **queue** distributes calls among several agents (extensions). For example, a "Sales queue" — when a customer calls, whichever agent is free rings; if everyone is busy, the call waits in line and hears hold music.

## Where to find it

Menu: **Routing → Queues**. Who sees it: users with the `routing` permission can edit; everyone else can only view. Agents manage their own queue status (log in/log out/pause) on the [My portal](/docs/portal) page.

## Core concepts

- **Strategy** — how calls are distributed among agents (see the table below).
- **Member** — an extension linked to the queue, with a **penalty** — a lower score rings first (used for priority in equal strategies).
- **Dynamic member** — an agent who logs in/out themselves (usually via [My portal](/docs/portal), joining/leaving the queue); members added by an admin through the panel are considered static.
- **Status** — each member shows a "Logged in / Paused / Logged out" indicator; if there is a pause reason, it appears on hover.
- **Hold music (MOH)** — the music played to the caller while waiting for an agent to answer; if none is chosen, the default music is used.
- **SLA threshold** — the number of seconds within which a call is considered "answered well" (for reporting purposes only, does not extend the wait).
- **Live status** — the "Live status" column in the table shows how many are currently waiting and how many members are online (updates in real time).

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Name | Queue name | Up to 60 characters |
| Number | Optional — for direct dialing | 2–10 characters of `0-9*#` |
| Strategy | Distribution method | Default — **Ring all (memory round-robin)** |
| Members | List of extensions linked to the queue, each with a penalty | At least 1 member required |
| On wait time expiry | Destination used when nobody answers | Required |
| Hold music | MOH class | Empty — default |
| Ring time per agent (s) | How long each member rings | 5–120, default 15 |
| Wait before retry (s) | Wait time after a failed ring | default 5, minimum 1 |
| Wrap-up time (s) | How long an agent stays "busy" after a call | default 0 |
| Max wait time (s) | The longest a caller can wait in queue before moving to the "On wait time expiry" destination | default 300 |
| SLA threshold (s) | The "good answer" threshold for reporting | default 20 |
| Announce frequency (s) | How often the position in queue is announced | default 60 (10–300) |
| Max callers in queue | How many people can wait in the queue at once | Empty — unlimited |
| Announce position in queue | "You are caller number 3" message | Enabled by default |
| Join queue even with no agents | If disabled — calls are rejected when no member is available | Disabled by default |
| Record calls | Record calls that go through the queue | Enabled by default |

### Strategies

| Strategy | How it works |
|---|---|
| Ring all (`ringall`) | Rings all free members at the same time |
| Least recently used (`leastrecent`) | Rings the member who has gone the longest without taking a call |
| Fewest calls (`fewestcalls`) | Rings the member with the fewest answered calls |
| Random (`random`) | Rings a randomly chosen member |
| Round robin (memory) (`rrmemory`) | Rotates through the list, resuming from where it last stopped (default) |
| Linear (`linear`) | Always in list order, starting from the first |
| Weighted random (`wrandom`) | Weighted random choice based on penalty |

## How to

### Create a new queue
1. Click **Add queue**, choose a name and strategy.
2. Add extensions from the **Members** list (at least one required); adjust the penalty if needed.
3. Choose the **On wait time expiry** destination (required) — e.g. voicemail or a night agent.
4. Click **Add**.

### Change member order
1. Open the queue for editing, and drag a row to a new position in the members list (order matters for `linear`/`rrmemory` strategies).

### Remove a member
1. Click **Remove** on the member's row, then **Save**.

### Open advanced settings
1. Click **Advanced settings** at the bottom of the form — agent ring time, time between retries, SLA, announce frequency, and the queue limit are here.

### Change the hold music
1. In the **Hold music** field, choose a ready-made MOH class (must first be created in the [Audio library](/docs/audio)), or leave it as the default.

### Link a queue to an inbound route
1. On the [Inbound routes](/docs/inbound) screen, route a DID to this queue.

### Delete
1. Click the trash icon at the end of the row.
2. If the queue is used elsewhere (inbound route, IVR button, etc.), deletion is blocked — remove those links first.

> [!TIP]
> The live status column and the "Now: N waiting, M online" line in the form header update in real time — you can monitor queue load from here.

> [!WARNING]
> If "Join queue even with no agents" is disabled and no member is free/logged in, the call is rejected — it won't even go to the "On wait time expiry" destination. Always make sure there is a fallback destination (e.g. voicemail).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Calls don't reach any agent | The agent hasn't "logged in" to the queue, or is on pause | The agent needs to log in / clear the pause via [My portal](/docs/portal) |
| The queue always rejects as "busy" | "Max callers in queue" has been reached | Raise the limit or leave it empty |
| Calls are rejected immediately | No members are available and "Join queue even with no agents" is disabled | Add a member or enable this setting |
| Can't delete the queue | It's used in an inbound route or another destination | Remove those links first |

## Related sections

- [My portal](/docs/portal)
- [Inbound routes](/docs/inbound)
- [Audio library](/docs/audio)
- [Quality scoring](/docs/quality)
- [Live monitor](/docs/live)
