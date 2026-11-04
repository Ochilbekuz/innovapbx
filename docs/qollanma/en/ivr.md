---
id: ivr
title: IVR
group: routing
order: 20
path: /ivr
summary: A voice menu — callers press a key to choose an option ("Press 1 for sales, 2 for accounting").
---

# IVR

**IVR** (voice menu) offers callers a spoken list of options: "Press 1 for Sales, 2 for Accounting." Each key leads to its own destination (extension, queue, another IVR, etc.).

## Where to find it

Menu: **Routing → IVR**. Who sees it: users with the `routing` permission can edit; everyone else can only view.

## Core concepts

- **Greeting audio** — the message played when the IVR is reached (must first be uploaded in the [Audio library](/docs/audio)).
- **Key map** — a separate destination for each key (`0-9`, `*`, `#`). An empty key is unassigned.
- **Direct dial** — when enabled, lets a caller skip the menu by dialing another extension's full number without listening to the prompt.
- **Timeout / invalid key** — if nothing is pressed within the set time, or an unassigned key is pressed, the matching audio (optional) is played and the call moves to a separate destination.
- **Loop check** — if an IVR connects back to itself, directly or through another IVR, the system raises an error and shows which path created the loop.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Name | The IVR menu's name | Up to 128 characters |
| Number | Optional — for direct dialing | 2–10 characters of `0-9*#` |
| Greeting audio | The message played when the menu opens | Required |
| Audio for invalid key | An optional message | Empty — moves to the error destination immediately on an invalid key |
| Wait time (seconds) | How long to wait if no key is pressed | 1–60, default 7 |
| Repeat count | How many times the greeting replays when the time runs out | 0–5, default 2 |
| Direct dial | Allows dialing another extension's full number to skip the menu | Disabled by default |
| Key map | A destination for each key | At least 1 key must be assigned |
| On timeout | Destination used if nothing is pressed | Required |
| On invalid key | Destination used for an unassigned key | Required |

Destination choices include: an extension, ring group, queue, another IVR, business-hours condition, conference, stop/busy tone, announcement, or misc destination.

## How to

### Add a new IVR
1. First upload the greeting audio in the [Audio library](/docs/audio).
2. Click **Add IVR**, choose a name and the greeting audio.
3. Assign destinations to the keys you need (at least one is required) — click each cell and choose via the `DestinationPicker`.
4. Set the **On timeout** and **On invalid key** destinations (both required).
5. Click **Add**.

### Change or clear a key's destination
1. Open the IVR for editing, click the key cell you need, and choose a new destination.
2. To clear a key, click the X icon next to the cell.

### Enable direct dial
1. In IVR editing, turn on the **Direct dial** toggle — now callers can dial another extension's full number without waiting for the menu to finish.

### Link the IVR to an inbound route
1. On the [Inbound routes](/docs/inbound) screen, route a DID to this IVR.
2. Or select this IVR as the destination on a button in another IVR (for nested menus).

### Delete
1. Click the trash icon at the end of the row.
2. If the IVR is used elsewhere, deletion is blocked — remove those links first.

> [!WARNING]
> If one IVR is selected as a key's destination (or timeout/error destination) in another IVR, and that chain loops back to itself, a "loop" error appears when saving, along with the path involved. Review the chain in that case.

> [!TIP]
> If "Audio for invalid key" is left empty, an invalid key press moves straight to the assigned destination without playing a message — shortening the wait time.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| The "Add" button won't click | No key is assigned, or the timeout/error destination isn't chosen | Fill in at least one key and both required destinations |
| "Loop" error on save | The IVR connects to itself directly or through another IVR | Check the path shown and break the chain |
| Can't delete the IVR | It's used in an inbound route or another key | Remove those links first |
| The audio selection list is empty | No audio has been uploaded yet | Upload a file in the [Audio library](/docs/audio) |

## Related sections

- [Audio library](/docs/audio)
- [Inbound routes](/docs/inbound)
- [Queues](/docs/queues)
- [Business hours](/docs/timegroups)
