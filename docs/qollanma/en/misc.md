---
id: misc
title: Misc destinations
group: routing
order: 50
path: /misc
summary: Dial codes outside the extensions table — misc destinations (e.g. fax) and custom codes (*501).
---

# Misc destinations

This section manages two things: **misc destinations** — standalone dial codes that aren't part
of the extensions list (e.g. a direct line to a fax machine), and **custom codes** — shortcuts
that connect immediately to a set destination when dialed from a phone (like `*501`).

## Where

Menu: **Routing → Misc destinations**. Who can see it: users with the `routing` permission can
edit, others can only view.

## Key concepts

- **Misc destination** — a plain "dial string" — it shows up in destination lists on
  IVR/business hours conditions and so on, but isn't in the extensions table (e.g. an analog fax
  port).
- **Custom code** — when a user dials it on their phone (e.g. `*501`), it connects
  directly to a set destination (extension, queue, IVR, etc.). It can be turned on or off at any
  time. In the UI this is shown under the **Feature codes** tab.

## Fields

### Misc destination

| Field | What it does | Example / default |
|---|---|---|
| Name | Destination name | — |
| Dial code | The code Asterisk dials to connect | E.g. `0022`; only `0-9*#+`, 1–32 characters, must not clash with an extension |

### Custom code

| Field | What it does | Example / default |
|---|---|---|
| Name | Code name | — |
| Code | Dial code | Starts with `*`, 1–6 characters (`*501`), or a plain numeric code of 1–10 digits |
| Destination | Where it goes when dialed | Extension, queue, IVR, ring group, conference, announcement, misc destination, etc. |
| Enabled | If off — the code stops working but stays saved | Default: on |

## How to

### Add a misc destination
1. On the **Destinations** tab, click **Add destination**.
2. Enter a name and dial code (make sure it doesn't clash with another extension/code).
3. Click **Add**.

### Add a custom code
1. On the **Feature codes** tab, click **Add code**.
2. Choose a name, code (e.g. `*501`), and destination.
3. Click **Add** — the code becomes active immediately.

### Temporarily disable a custom code
1. Open the code for editing, turn off **Enabled**, and click **Save**.
2. The code itself isn't deleted — it just stops working, and can be re-enabled anytime.

### Delete
1. Click the trash icon at the end of the row.
2. If a misc destination is used elsewhere, deletion is blocked — remove those links
   first.

> [!TIP]
> Custom codes are handy for quick shortcuts — e.g. `*0` to reach the front desk directly,
> or `*99` to reach on-call tech support.

> [!WARNING]
> A custom code must not clash with other [feature codes](/docs/featurecodes) (e.g.
> system codes like `*97`, `*98`) — it can't be equal to or a prefix of one (e.g. `*7` and `*72`).
> If it clashes, the panel won't save it: a clash with another enabled function shows **"This
> code clashes with another function"**, while a clash with an extension/destination shows
> **"This code clashes with an extension/destination."**

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Dial code won't save | Invalid format (disallowed character) or empty | Enter only `0-9*#+`, 1–32 characters |
| Dialing a custom code does nothing | **Enabled** is off | Edit the code and turn it on |
| Can't delete a misc destination | It's used elsewhere (IVR, business hours condition, etc.) | Remove those links first |

## Related sections

- [IVR](/docs/ivr)
- [Feature codes](/docs/featurecodes)
- [Inbound routes](/docs/inbound)
