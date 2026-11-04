---
id: timegroups
title: Business hours
group: routing
order: 10
path: /timegroups
summary: Weekly work/off schedule, holidays, and "open/closed" conditions — split a call into two destinations by time.
---

# Business hours

When the office isn't working, calls need to go somewhere else (e.g. voicemail or a night agent). The **Business hours** section is exactly for that: a weekly schedule (when it's "open"), a holiday list, and a "condition" that splits a DID in two — all gathered here.

## Where to find it

Menu: **Routing → Business hours**. Who sees it: users with the `routing` permission can edit; everyone else can only view.

## Core concepts

- **Group** — a weekly schedule: several time ranges per day (e.g. "Monday 09:00–13:00, 14:00–18:00"). Set by clicking or dragging across cells.
- **Holiday** — a special day with a date (`YYYY-MM-DD`) and a "repeats every year" flag. For conditions with `honor_holidays` enabled, a holiday is always treated as "closed" regardless of the schedule.
- **Condition** — links to a group and defines two destinations: **when open** and **when closed**. Select this condition in an **Inbound route** and the call is automatically split based on the time.
- **Mode (override)** — each condition can also be controlled manually: `Automatic` (follows the schedule), or `Night mode` (force closed). The moon/sun toggle on the panel page switches this.
- **Override code** — an optional code like `*271`: lets you switch a condition to night mode/automatic using phone keys (set separately for each condition).

## Fields

### Group

| Field | What it does | Example / default |
|---|---|---|
| Name | Group name | Up to 60 characters |
| Business hours schedule | A weekly grid of cells | Default — empty (never "open") |

### Holiday

| Field | What it does | Example / default |
|---|---|---|
| Name | Holiday name | Up to 60 characters |
| Date | In `YYYY-MM-DD` format | — |
| Repeats every year | When enabled — counted on this day/month every year | Enabled by default when newly added |

### Condition

| Field | What it does | Example / default |
|---|---|---|
| Name | Condition name | Up to 60 characters |
| Number | Optional — for direct dialing | 2–10 characters of `0-9*#` |
| Business hours group | Which weekly schedule it is based on | — |
| Honor holidays | When enabled — a holiday is always "closed" | Enabled by default |
| When open | Destination used when the schedule says "open" | Extension, queue, IVR, ring group, conference, announcement, misc destination, busy/stop |
| When closed | Destination used when "closed" | Same list as above |
| Override code | Optional, `*` + 2–4 digits | e.g. `*271` |

## How to

### Create a business hours group
1. On the **Groups** tab, click **Add group**.
2. Enter a name, mark the working hours on the weekly grid (click or drag to select).
3. Click **Add**. Conditions linked to this group start following the new schedule immediately.

### Add Uzbekistan holidays
1. On the **Holidays** tab, click **Add Uzbekistan holidays** — official holidays for the current year are added automatically.
2. Holidays whose date isn't fixed year to year (e.g. religious holidays) are skipped — add the dates shown in the notification manually.

### Add a holiday manually
1. Click **New holiday**, enter a name and date.
2. Turn off "Repeats every year" if not needed (for a one-time day).

### Create a business hours condition and link it to an inbound route
1. First, you need at least one group in **Groups**.
2. On the **Conditions** tab, click **Add condition**, give it a name, and choose a business hours group.
3. Choose the **When open** and **When closed** destinations (e.g. a queue when open, voicemail when closed).
4. Configure "Honor holidays" and an override code if needed, then click **Add**.
5. On the [Inbound routes](/docs/inbound) screen, route a DID to this condition — the call will now be automatically split based on the time.

### Switch a condition to night mode manually
1. In the table, click the moon/sun icon on the condition's row — the mode switches between `Automatic` ↔ `Night mode` instantly.
2. The same action can be done by phone — dial the **Override code** set in the condition's settings.

### Delete
1. Click the trash icon at the end of the row.
2. If the group/condition is used elsewhere (e.g. in an inbound route), deletion is blocked, and the places using it are shown — remove those links first.

> [!TIP]
> A business hours condition can be selected not only in **inbound routes**, but also in the "destination" fields of an IVR/queue/ring group — meaning you can split paths by "open/closed" at virtually any point.

> [!WARNING]
> A condition manually switched to "Night mode" does not revert automatically — even if the schedule shows "open," calls will keep going to the "closed" destination until you switch it back to "Automatic."

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| The condition always shows "closed" | The group's schedule is empty, or today isn't marked | Edit the group and mark the needed day/hours |
| It stayed "open" even on a holiday | "Honor holidays" is disabled on the condition | Enable it when editing the condition |
| Can't delete the group/condition | It's used elsewhere (inbound route, etc.) | Remove it from the shown list first |
| The override code doesn't work | It doesn't match the code format, or is empty | Enter it in `*` + 2–4 digit format |

## Related sections

- [Inbound routes](/docs/inbound)
- [IVR](/docs/ivr)
- [Queues](/docs/queues)
- [Day/Night mode](/docs/day_night)
- [Feature codes](/docs/featurecodes)
