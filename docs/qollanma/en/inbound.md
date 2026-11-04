---
id: inbound
title: Inbound routes
group: connect
order: 20
path: /inbound
summary: Route calls arriving from outside by DID/CallerID to the right destination (extension, queue, IVR...).
---

# Inbound routes

Inbound routes determine where a call coming from outside (through a carrier trunk) is sent — to an extension, ring group, queue, IVR, business-hours schedule, etc. — based on which DID number it arrived on and which caller number it came from.

## Where to find it

Menu: **Connectivity → Inbound routes**. Who sees it: the `connect:view` permission. Adding/editing/deleting requires `connect:edit`; without it, a **"You don't have permission to manage routes — view only"** note appears.

## Core concepts

- **DID** — the external phone number the carrier assigned to you; if **Any DID** is enabled, the call falls into this route regardless of which number it arrived on.
- **CallerID (CID)** — a filter based on the caller's number; if **Any caller number** is enabled, it matches no matter who calls.
- **CID lookup source** — looks up and displays the caller's name from an external source (phonebook/CRM/HTTP); an optional **CID name prefix** is added before the caller's name.
- **Alert-Info** — an optional SIP header for a custom ring tone or device LED.
- **View call path** — shows where a route actually leads (a chain like queue → IVR → extension) as a tree computed by the server; clicking a node takes you to the relevant page.
- **Deleted (#id)** marker — indicates that the route's destination (e.g. a deleted IVR) no longer exists.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| **Name** | A recognizable name for the route | — (required) |
| **Any DID** / **DID** | Which external number it matches | DID: 3–15 digits, e.g. `712000001` |
| **Any caller number** / **CallerID (CID)** | Which caller number it matches | e.g. `+998901234567` |
| **Destination** | Where the call is routed | Extension, ring group, queue, IVR, or business-hours schedule |
| **Enabled** | Temporarily disable the route | default: enabled |
| **CID lookup source** | Source used to find the caller's name | default: Not selected |
| **CID name prefix** | Text added before the found name | e.g. `Reception: ` |
| **Alert-Info** | SIP header for a custom ring tone/LED | e.g. `Bellcore-dr2` |

## How to

### Add a new inbound route
1. Click **New route**.
2. Enter a **Name**; turn off **Any DID** and enter the specific DID number (or leave it enabled).
3. If needed, turn off **Any caller number** and enter a specific CID.
4. Choose where the call should go in the **Destination** field.
5. Click **Add**.

### Add a CID lookup and Alert-Info
1. Edit the route.
2. Select a **CID lookup source**, and optionally enter a **CID name prefix**.
3. If a custom ring tone is needed, enter a value in the **Alert-Info** field, then click **Save**.

### View the call path
1. In the table, click the route (path) icon on the route's row.
2. The panel that opens shows the call's actual path (e.g. IVR → queue → extension) as a tree.

## Tips and limitations

> [!WARNING]
> If a destination (IVR, queue, etc.) has been deleted, the route table shows a **"Deleted (#id)"** marker — calls may go unanswered until you reconfigure this route.

> [!TIP]
> If you need multiple routes for the same DID, you can use the **CallerID (CID)** filter to send different callers to different destinations.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "DID must be 3–15 digits" | The DID field was entered in an invalid format | Enter digits only (without a `+`) |
| "CallerID is in an invalid format" | The CID field doesn't match the expected format | Enter it with a `+` or as plain digits (3–15 digits) |
| "Alert-Info is in an invalid format" | Disallowed characters were entered | Only use Latin letters/digits and the characters `=<>:;/._@-` |
| "Deleted (#id)" | The route's destination (IVR/queue, etc.) has been deleted | Edit the route and choose a new destination |
| Calls aren't arriving | No route matches the DID/CID, or the route is disabled | Check that it's **Enabled** and the DID/CID, and review the "Call path" |

## Related sections

- [Trunks](/docs/trunks)
- [CID lookup sources](/docs/cidsources)
- [Outbound routes](/docs/outbound)
