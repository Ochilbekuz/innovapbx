---
id: parking
title: Parking & pickup
group: apps
order: 40
path: /parking
summary: Places to "park" a call temporarily and pick it up again from a different phone.
---

# Parking & pickup

**Parking** lets you put a call on hold in a temporary "slot" and continue it from a different
room or phone. For example: an operator parks the call (transferring it to `*70` or the parking
code) and tells the employee "pick up slot 701" — the employee dials `701` on their own phone to
continue the call.

## Where

Menu: **Applications → Parking & pickup**. Who can see it: users with the `apps` permission can
edit, others can only view. The settings are **single**, per tenant (you can't create a new
"parking lot" — only the existing settings can be edited).

## Key concepts

- **Parking lot code** — transferring a call to this code parks it.
- **First slot number and number of slots** — the range of numbers parked calls are
  assigned from (e.g. starting at 701 with 20 slots — `701`–`720`).
- **On timeout** — if no one picks up, the call either **returns to the parker** or is
  sent to **another destination** (e.g. a queue).
- **Hold music** — the music played to the caller while parked.
- Phone codes: picking up another ringing phone in a group — `*8` (group pickup); picking
  up a specific phone — `**` (direct pickup); parking a call — `*70` (standard [feature
  codes](/docs/featurecodes), changeable).

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Parking lot code | The code a call is transferred to in order to park it | Default `700`, 1–10 `0-9*#` characters |
| First slot number | The first parking slot number | Default `701` |
| Number of slots | How many parking slots there are | 1–100, default `20` |
| Timeout (seconds) | How long to wait if no one picks up | 10–3600, default `60` |
| On timeout | "Return to the parker" or "Send to another destination" | Default: return to the parker |
| Destination on timeout | If "Another destination" is chosen — where | Optional |
| Hold music class | The music heard while parked | Blank — default tone |

## How to

### Change the parking settings
1. In the **Settings** block, change the fields you need (code, first slot number,
   number of slots, timeout).
2. For **On timeout**, if you choose "Send to another destination", set the destination.
3. Click **Save**.

### Park a call (for users)
1. During a call, transfer it to the parking code (default `700`).
2. The system announces a free slot number (e.g. `701`).
3. Tell another employee that number.

### Pick up a parked call
1. Dial the parking slot number (e.g. `701`) from any phone — the call continues.

### Pick up a ringing phone from elsewhere (pickup)
1. To pick up a ringing phone within a group, dial the `*8` (group pickup) code.
2. To pick up one specific phone, use the `**` (direct pickup) code.

### Monitor parked calls live
1. The **Parked calls** table refreshes automatically every 5 seconds — showing the slot,
   caller, who parked it, elapsed time, and time left until timeout.

> [!TIP]
> Choose "Number of slots" to match your team's size — if many employees park calls at
> once, slots may run out.

> [!WARNING]
> If "On timeout" is set to "Return to the parker," check separately where the call goes
> if the parker has already hung up their phone — otherwise the call may get "stuck."

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Parking doesn't work | The parking code was dialed wrong, or it clashes with another code | Check the exact code in the settings |
| No free slot found | All slots are occupied | Increase the number of slots, or make sure parked calls are picked up faster |
| On timeout, the call went somewhere unexpected | The "On timeout" destination is set incorrectly | Check and fix the setting |

## Related sections

- [Feature codes](/docs/featurecodes)
- [Audio library](/docs/audio)
