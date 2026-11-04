---
id: conference
title: Conference rooms
group: apps
order: 30
path: /conference
summary: A room where several people join at once — number, PIN, admin PIN, and member limit.
---

# Conference rooms

A **conference** is a "room" where several internal/external calls join at once to talk. For
example, for a weekly meeting, employees dial a number and enter a PIN to join the room.

## Where

Menu: **Applications → Conference rooms**. Who can see it: users with the `apps` permission can
edit, others can only view.

## Key concepts

- **Number** — the number dialed to join the room; if left blank, one is assigned
  automatically.
- **PIN** — a password for regular participants (optional).
- **Admin PIN** — a separate password for the moderator; anyone who joins with it gets
  rights to manage the other participants.
- **Member limit** — the maximum number of people allowed in the room at once.
- **Now** column — shows live how many people are currently in the room.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Name | Room name | Up to 128 characters |
| Number | The code used to join the room | Blank — assigned automatically; 2–10 `0-9*#` characters |
| PIN | Password for participants | Optional, 4–8 digits |
| Admin PIN | Password for the moderator | Optional, 4–8 digits |
| Record the call | Records the conference audio | — |
| Member limit | Maximum number of participants | Optional, 2–100, blank — unlimited |

## How to

### Create a new conference
1. Click **Add conference** and enter a name.
2. Enter a number manually, or leave it blank to have one assigned automatically.
3. Set the **PIN** and **Admin PIN** and member limit if needed, and turn call
   recording on/off.
4. Click **Add**.

### Attach a conference to an inbound route/IVR
1. On the [Inbound routes](/docs/inbound) screen, route a DID to this conference, or
   select it as a destination on an IVR button.
2. Internal employees can also join directly by dialing the room number.

### Set moderator rights
1. Set an **Admin PIN** on the conference and give that PIN to the moderator — entering
   with it grants separate management rights.

### Delete
1. Click the trash icon at the end of the row.
2. If the conference is used elsewhere (a route, IVR), deletion is blocked — remove those
   links first.

> [!TIP]
> Use different PINs for regular participants and the moderator — that way the
> moderator is always identified separately and keeps their management rights.

> [!WARNING]
> Once the **member limit** is reached, further calls trying to join are rejected — set
> a sufficient limit for important meetings, or leave it blank (unlimited).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Number is taken" error | The number is already used by another destination | Choose a different number, or leave it blank for automatic assignment |
| A participant can't join the room | The member limit has been reached | Raise the limit, or leave it blank (unlimited) |
| PIN is rejected as incorrect | The PIN isn't 4–8 digits | Enter the PIN in the correct format |
| Can't delete the conference | It's used in a route/IVR | Remove those links first |

## Related sections

- [Inbound routes](/docs/inbound)
- [IVR](/docs/ivr)
