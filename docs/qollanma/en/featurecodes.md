---
id: featurecodes
title: Feature codes
group: system
order: 90
path: /settings/feature-codes
summary: Change the codes used from a phone to access features, and turn them on or off.
---

# Feature codes

Voicemail, DND, call forwarding, pickup, park, and similar features can be used by dialing a
`*`-code from an extension (e.g. `*97` for voicemail). The code for each feature is changed here,
and any feature you don't need can be disabled entirely.

## Where
Menu: **System → Feature codes**. Who can see it: everyone can view the table, but only a user
with `*` (full administrator) permission can change a code or its enabled/disabled state.

## Key concepts

- **Feature** — an action triggered by dialing a code from a phone: Voicemail (`*97`),
  another extension's voicemail (`*98`), toggle DND (`*76`), enable/disable unconditional
  forwarding (`*72`/`*73`), enable/disable forward-on-busy (`*90`/`*91`), group pickup (`*8`),
  direct pickup (`**`), park (`*70`), echo test (`*43`), speaking clock (`*60`), toggle Follow Me
  (`*21`), queue login/logout (`*45`), pause in queue (`*46`), intercom (auto-answer, `*80`),
  toggle call waiting (`*56`/`*57`). The queue and intercom features themselves are managed on
  their own pages (Queues, extension settings) — on this page you can only change their code or
  reset it to default.
- **Code** — a sequence starting with `*`, 1–6 characters long (digits, `*`, `#`), e.g.
  `*97`.
- **Default code** — every feature has its own default code; if a changed code differs
  from the default, a **reset to default** button appears.
- **Clash** — two codes are considered clashing not only if they're **exactly** the
  same, but also if one is a **prefix** of the other (e.g. `*7` and `*72`) — Asterisk can't tell
  the two apart reliably. In that case the system refuses to save.
- **Enabled/disabled** — if a feature is fully disabled, its code no longer connects to
  anything.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Feature | Which action this is (can't be changed) | — |
| Code | `*` + 1–6 characters (digit/`*`/`#`) | `*97` |
| Enabled | Turns the feature on/off | — |

## How to

### Change a code
1. Click the pencil icon on the feature row you need.
2. Enter the new code (format: starts with `*`, 1–6 characters).
3. Click the checkmark (✓) to save, or ✕ to cancel.

### Reset a code to default
1. If a code differs from the default, a **reset** icon appears on the row — click it.
2. The code immediately reverts to its default value.

### Enable/disable a feature
1. Click the **Enabled** checkbox on the row you need to toggle it.

## Tips and limits

> [!WARNING]
> You can't give two features the same code **or** a code that's a prefix of another's
> (e.g. `*7` and `*72` can't coexist) — the system shows "This code clashes with another
> feature."

> [!TIP]
> After changing a code, let extension users know about the new code — the old one no
> longer works.

- The code format is strict: only `*`, digits, and `#`, 1–6 characters long.
- Everyone can view, but only a full administrator can change — the table is read-only
  for everyone else and no edit buttons appear.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Invalid code" | The format doesn't match (too long/wrong character) | Start with `*`, use only digits/`*`/`#`, 1–6 characters |
| "This code clashes with another feature" | The code is already used by another feature, or is its prefix/extension | Choose a different code, or change the old one first |
| "Could not save" | A server error | Try again |
| Edit buttons aren't visible | You don't have full administrator permission | Ask an administrator for `*` permission |

## Related sections

- [SIP & network](/docs/sip)
- [Security](/docs/security)
