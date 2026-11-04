---
id: xususiyat-kodlari
title: Feature codes (full list)
group: appendix
order: 10
summary: The full list of standard feature codes dialed with * from a phone.
---

# Feature codes (full list)

The complete list of every standard `*`-code dialed from an extension's phone keypad in Innova
PBX — provided as a quick reference. The codes themselves are changed on the [Feature
codes](/docs/featurecodes) page.

## Default code list

| Feature | Default code | Note |
|---|---|---|
| Own voicemail | `*97` | Access your voicemail |
| Another extension's voicemail | `*98` | Leave a message in another extension's voicemail |
| Toggle DND | `*76` | Turn "do not disturb" on/off |
| Unconditional forwarding — on | `*72` | Forward every call unconditionally |
| Unconditional forwarding — off | `*73` | |
| Forward-on-busy — on | `*90` | |
| Forward-on-busy — off | `*91` | |
| Group pickup | `*8` | Pick up a call ringing within a group |
| Direct pickup | `**` + extension | Pick up a call ringing on a specific extension |
| Park | `*70` | Put a call into a "parking" slot |
| Echo test | `*43` | Check audio quality |
| Speaking clock | `*60` | A spoken time announcement |
| Toggle Follow Me | `*21` | Toggle the "Follow Me" feature |
| Queue login/logout | `*45` | A queue agent logging in/out (usually managed from the Queues section) |
| Toggle pause | `*46` | A queue agent's pause (usually managed from the Queues section) |
| Intercom (internal quick call) | `*80` + extension | |
| Call waiting — on | `*56` | Call waiting |
| Call waiting — off | `*57` | |

## Format rule

Every code starts with `*`, followed by 1–6 characters (digits, `*`, or `#`): `^\*[0-9*#]{1,6}$`.

## Clash rule

Two features can't be given the same code **or** a code where one is a **prefix** of the
other — for example `*7` and `*72` can't both exist at the same time, because Asterisk can't
reliably tell which one a dialed number belongs to. In that case, the system refuses to save and
shows the error "This code clashes with another function."

> [!NOTE]
> The Day/Night mode switch code (`*28<code>`) is a separate mechanism — it doesn't
> appear in the [Feature codes](/docs/featurecodes) table, but is instead configured per time
> condition on the [Day/Night mode](/docs/day_night) page.

## Related sections

- [Feature codes](/docs/featurecodes)
- [Day/Night mode](/docs/day_night)
- [SIP & network](/docs/sip)
