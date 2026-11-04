---
id: cidsources
title: CID lookup sources
group: connect
order: 50
path: /cidsources
summary: Look up a caller's name from an external source (phonebook, CRM, HTTP) for inbound calls.
---

# CID lookup sources

A CID lookup source is a setting attached to an [inbound route](/docs/inbound) that, when a call comes in, finds the caller's name (e.g. from the phonebook, a CRM, or an external HTTP service) and shows it on screen/device.

## Where to find it

Menu: **Connectivity → CID lookup sources**. Who sees it: the `connect:view` permission. Adding/editing/deleting requires `connect:edit`; without it, a **"You don't have permission to manage these sources — view only"** note appears. The Test button works with view access too.

## Core concepts

- **Source type**:
  - **Phonebook** — looks up the system's internal phonebook entries.
  - **CRM** — looks up the connected CRM integration.
  - **HTTP (JSON)** — sends a request to the given HTTP address and extracts the name from the JSON response.
- The `{number}` placeholder in the **HTTP address** is automatically replaced with the caller's number (e.g. `https://crm.local/lookup?q={number}`).
- **JSON path** — which field in the HTTP response to use as the name (e.g. `data.name`).
- **Timeout** and **Cache duration** — how long to wait for a response and how long the result is remembered (so subsequent calls from the same number don't trigger another request).
- **Test** — available for any source in its row; enter a number to see the result (found/not found/error, and response time) immediately.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| **Name** | A recognizable name for the source | — (required) |
| **Type** | Phonebook / CRM / HTTP (JSON) | default: Phonebook |
| **HTTP address** | *(HTTP type only)* The URL called for the lookup | `https://crm.local/lookup?q={number}` (required for HTTP type) |
| **JSON path** | *(HTTP type only)* The field path used to get the name from the response | `data.name` |
| **Timeout (ms)** | How long to wait for a response | default: 1500 |
| **Cache duration (seconds)** | How long the result is remembered | default: 3600 |
| **Enabled** | Temporarily disable the source | default: enabled |

## How to

### Add a new source (Phonebook or CRM)
1. Click **New source**.
2. Enter a **Name**, and choose **Phonebook** or **CRM** as the **Type**.
3. Click **Add**.

### Add a new source (HTTP)
1. Click **New source**, and choose **HTTP (JSON)** as the **Type**.
2. Enter the URL in **HTTP address**, marking where the number goes with `{number}`.
3. Fill in **JSON path** if needed, and set the **Timeout** and **Cache duration**.
4. Click **Add**.

### Test a source
1. In the table, click the test (flask) icon on the source's row.
2. Enter a **Test number**, and click **Run**.
3. The result shows as **"Found: <name> (<ms> ms)"**, **"Not found (<ms> ms)"**, or **"Error: <message>"**.

### Attach a source to an inbound route
1. Edit the route you need in [Inbound routes](/docs/inbound).
2. Select the source you created in the **CID lookup source** field, enter an optional **CID name prefix**, and click **Save**.

### Delete a source
1. Click the **Delete** icon on the row.
2. If the source is still used in an inbound route, the system shows which routes and blocks deletion — remove it from the route first.

## Tips and limitations

> [!TIP]
> After adding a new HTTP source, immediately verify it with **Test** using a real number — a wrong URL/JSON path will cause inbound calls to show without a name.

> [!TIP]
> Increasing the **Cache duration** reduces load on the external service, but changes in the CRM/phonebook may not show up until that duration has elapsed.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Not found" (when testing) | The number isn't in the source, or the JSON path is wrong | Check the JSON path and the data in the source |
| "Error: ..." (when testing) | Could not connect to the HTTP address, or the response format is wrong | Check the URL, network, and JSON format |
| Can't delete the source | The source is still used in an inbound route | Remove it from the shown route(s) first |
| No name appears on the call | The source isn't attached to the inbound route, or isn't **Enabled** | Attach the source to the route in [Inbound routes](/docs/inbound) and check that it's enabled |

## Related sections

- [Inbound routes](/docs/inbound)
- [Trunks](/docs/trunks)
