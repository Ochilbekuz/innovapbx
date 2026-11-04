---
id: day_night
title: Day/Night mode
group: routing
order: 70
path: /day-night
summary: Switch between day/night destinations with one tap using a feature code (*28<code>) or the panel, with a BLF indicator.
---

# Day/Night mode

**Day/Night mode** is similar to a [business hours condition](/docs/timegroups), but instead of following a schedule, it's a simple "open/closed" switch toggled manually (by phone code or panel button). For example: when the receptionist leaves in the evening, dialing `*28<code>` sends all calls to the night agent.

## Where to find it

Menu: **Routing → Day/Night**. Who sees it: users with the `routing` permission can edit; everyone else can only view.

## Core concepts

- **Mode** — a rule is always in one of two states: **Day** or **Night**. It is not tied to a schedule — only switched manually.
- **Feature code** — each rule has a one-digit code attached; dial `*28<code>` from a phone to switch the mode (e.g. if the rule's code is `1`, dial `*281`).
- **PIN** — optional, 4–8 digits. If set, a PIN is required before switching the mode by phone.
- **BLF indicator** — if a BLF key is set up on a SIP phone with the `Custom:DAYNIGHT<code>` hint code, the indicator shows the current mode (day/night) and pressing it switches the mode.
- Switching the mode in the panel does not require a PIN — the PIN only applies when switching via phone code.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Name | Rule name | Up to 128 characters |
| Feature code | The digit after `*28` | One `0-9` digit |
| Day destination | Where calls go while the mode is "Day" | Required |
| Night destination | Where calls go while the mode is "Night" | Required |
| PIN | Password requested before switching the mode | Optional, 4–8 digits |

## How to

### Add a new rule
1. Click **Add rule**, enter a name and feature code (one digit).
2. Choose the **Day destination** and **Night destination**.
3. Set a PIN if needed.
4. Click **Add** — the new rule starts in **Day** mode by default.

### Switch the mode from the panel
1. In the table, click the moon/sun icon on the rule's row — the mode instantly switches between **Day** ↔ **Night**.

### Switch the mode by phone
1. Dial `*28<code>` from a phone (e.g. `*281`).
2. If a PIN is set, enter it when prompted.

### Set up a BLF indicator
1. In the SIP phone/sip.js configuration, enter the hint code `Custom:DAYNIGHT<code>` on a BLF key — the indicator will show the current mode and switch it when pressed.

### Remove a PIN
1. Open the rule for editing, check **Remove PIN**, then **Save**.

### Delete
1. Click the trash icon at the end of the row.
2. If the rule is used elsewhere, deletion is blocked — remove those links first.
3. Calls routed to a deleted rule will now hear an unavailable tone.

> [!TIP]
> Day/Night mode is convenient for quick manual switching with a single button/code; if you need an automatic weekly schedule, a [Business hours](/docs/timegroups) condition is a better fit.

> [!WARNING]
> The mode does not revert automatically — a rule switched to "Night" stays that way until it's manually switched back to "Day" (by code or panel) in the morning.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `*28<code>` doesn't work | The code was dialed incorrectly, or the PIN was entered wrong | Check the exact code and PIN in the rule |
| The BLF indicator doesn't light up | `Custom:DAYNIGHT<code>` isn't configured correctly on the phone | Check that the code matches the rule's feature code |
| Can't delete the rule | It's used in an inbound route or another destination | Remove those links first |

## Related sections

- [Business hours](/docs/timegroups)
- [Inbound routes](/docs/inbound)
- [Feature codes](/docs/featurecodes)
