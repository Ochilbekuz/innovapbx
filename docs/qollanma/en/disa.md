---
id: disa
title: DISA
group: apps
order: 100
path: /disa
summary: Call in from outside, enter a PIN, and use the system's outbound routes (DISA).
---

# DISA

DISA (Direct Inward System Access) lets an employee outside the office call the office number,
enter a PIN, and place outbound calls to external numbers as if calling from an office phone. For
example, a traveling employee calls the office number, enters the PIN, then dials any external
number through the office trunk.

## Where

Menu: **Applications → DISA**. Who can see it: the `apps` permission can edit, others can only
view.

## Key concepts

- **DISA** — a single settings set selected as a destination on an [Inbound
  route](/docs/inbound) or IVR; when an external caller reaches this destination, a PIN is
  requested.
- **PIN** — the sign-in password (4–8 digits); stored as a non-retrievable (HMAC) value —
  it's never shown when editing, you can only set a new PIN or remove it.
- **Allow PIN-less access** — if enabled, access is allowed without entering a PIN;
  recommended **only** for trusted trunks — this toggle **must** be enabled when the PIN is left
  blank.
- **CID override** — overrides the number shown on outbound calls placed via DISA.
- **Attempt limit** — the call is automatically dropped after this many wrong PIN
  entries.
- DISA only opens **outbound routes** — it gives no access to internal feature codes.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Name | Required | Up to 128 characters |
| PIN | 4–8 digits | Blank only allowed when "Allow PIN-less access" is enabled |
| Allow PIN-less access | — | Default: off |
| CID override | Optional | — |
| Digit entry timeout (seconds) | 1–60 | Default: `5` |
| Answer timeout (seconds) | 1–60 | Default: `10` |
| Max attempts | 1–10 | Default: `3` |
| Enabled | — | Default: on |

## How to

### Create a new DISA
1. Click **New DISA** and enter a name.
2. Enter a PIN (4–8 digits), or enable **Allow PIN-less access** and leave the PIN blank.
3. Optionally change the CID override and the timing/attempt settings, then click **Add**.

### Attach DISA to an inbound route
1. Select this DISA as a destination on the [Inbound routes](/docs/inbound) or IVR screen.
2. Calls to that DID/IVR button now go through DISA.

### Change or remove the PIN
1. Open edit and enter a new value in the **PIN** field (the old PIN is never shown
   again).
2. To use it without a PIN, check "Remove PIN" and enable **Allow PIN-less access**, then
   click **Save**.

### Temporarily disable
1. Open edit, turn off **Enabled**, and click **Save** — DISA stops working but stays
   saved.

### Delete
1. Click the trash icon at the end of the row.
2. If DISA is used elsewhere (a route, IVR), deletion is blocked — remove those links
   first. Once deleted, calls routed to it hear a "no answer" tone.

> [!WARNING]
> Enable "Allow PIN-less access" **only** on trusted, controlled trunks — otherwise
> anyone calling the office number could place free external calls (toll fraud).

> [!TIP]
> Set **Max attempts** low, e.g. 3 — this makes brute-forcing the PIN harder.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "PIN requires allow_no_pin=true" error | The PIN was left blank but "Allow PIN-less access" wasn't enabled | Enter a PIN, or enable Allow PIN-less access |
| DISA isn't connecting the outbound call | Outbound routes aren't configured, or the trunk is busy | Check [Outbound routes](/docs/outbound) |
| Call drops faster than expected on a wrong PIN | Max attempts is set too low | Increase the attempt count in settings |
| Can't delete DISA | It's used in a route/IVR | Remove those links first |

## Related sections

- [Inbound routes](/docs/inbound)
- [Outbound routes](/docs/outbound)
- [IVR](/docs/ivr)
- [Security](/docs/security)
