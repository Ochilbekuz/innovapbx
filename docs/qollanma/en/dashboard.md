---
id: dashboard
title: Dashboard
group: overview
order: 10
path: /dashboard
summary: See system health, live calls, today's call volume, queues, and alerts on a single screen.
---

# Dashboard

The dashboard is the first screen you see after logging in: it shows at a glance whether Asterisk and the database are running, how many calls happened today, who is talking right now, and where problems are occurring. Data refreshes automatically every 10 seconds.

## Where to find it

Menu: **Overview → Dashboard**. Who sees it: any role with the `monitor:view` permission (usually **admin**; for custom roles — if they have been granted view access to the Monitoring area). The **Parking** card below additionally requires the `apps:view` permission — without it, the card does not appear at all (e.g. for the operator role).

## Core concepts

- **System health** — the status of Asterisk, the database, disk space, and each trunk. Each is shown in green (`ok`) or red (`crit`); if there is a problem, a short reason is given (e.g. "The Asterisk process is not responding").
- **Alerts** — appear at the top of the page only when there is a problem; clicking one takes you to the relevant section.
- **Hourly volume** — today's inbound/outbound/missed call counts, shown as an hourly bar chart.

## Fields

This screen has no form — only view-only cards:

| Card | What it shows |
|---|---|
| KPI row | **Active calls**, **Total today**, **Answered**, **Missed**, **Average wait** |
| **Hourly volume** | Today's inbound/outbound/missed calls — hourly chart |
| System health | Asterisk, Database, Disk, status of each trunk (**Details** link — to the System status page) |
| **Live calls** | Calls in progress right now — from, to, direction, duration |
| **Queues** | For each queue: number of online agents, number waiting, longest wait time |
| **Missed calls** | Time, caller, which DID, called-back/not-called-back flag, call-back link |
| **Parking** | Calls currently parked — slot number, who parked it, how long ago |

## How to

### Find a problem and go to the relevant section
1. Look at the alert list at the top of the page — each row states which issue it relates to.
2. Click **View** to go to the problem area (e.g. if a trunk connection is down, the Trunks page opens).
3. If the system health card shows a red marker, use the **Details** link to go to the System status page for full diagnostics.

### Call back a missed call
1. Find the row you need in the **Missed calls** card.
2. If the row is marked **Not called back**, click the **Call back** link (the number is dialed through your browser/system phone app).

## Tips and limitations

> [!TIP]
> All cards update automatically — you don't need to reload the page.

> [!WARNING]
> The **Parking** card is only visible to users with the `apps:view` permission. The operator role does not have this permission, so this card does not appear on the operator's panel at all — this is not a bug.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Failed to load." message | Network/API issue between the panel and the server | Click **Retry**; if it persists, check the network connection |
| Red marker on a trunk row | The trunk is not registered or has no connectivity | Check the trunk status in [Trunks](/docs/trunks) |
| "The Asterisk process is not responding" | The Asterisk service is down or overloaded | Contact the server administrator or check the [System status](/docs/status) page |
| Red/yellow marker on the disk row | Disk space is running low | Clean up old records/backups or expand the disk |

## Related sections

- [Live monitor](/docs/live)
- [Trunks](/docs/trunks)
