---
id: analytics
title: Analytics
group: reports
order: 20
path: /analytics
summary: Call statistics — KPIs, daily/hourly charts, and tables broken down by queue and agent.
---

# Analytics

An overview of the call center and overall call flow: how many calls there were, how many were
answered, average wait time, and the SLA level. For a manager — all the numbers on one screen
instead of a daily report.

## Where
Menu: **Reports → Analytics**. Who can see it: a user with `reports:view` or `reports:edit`
permission.

## Key concepts

- **SLA level** — the percentage of calls answered within a set time (based on the
  SLA threshold in the queue's settings, see [Queues](/docs/queues)).
- **Missed** — calls that went unanswered or were cut off after waiting too long in a
  queue.
- Charts and tables update to match the selected **range** and **queue filter**.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Range | Today / Yesterday / Last 7 days / Last 30 days / Custom (date range) | Default: Last 7 days |
| From / To | Only shown when "Custom" is selected — the date range | Max 92 days |
| Queue | Filter by a single queue | Default: All queues |

## How to

### View by range and queue
1. Choose a **Range** (a quick option, or **Custom** with your own date range).
2. If needed, choose a single queue from the **Queue** list — every KPI, chart, and
   table narrows to that queue.
3. The KPI cards (total calls, answered, missed, avg wait, avg talk time, SLA level) are
   calculated automatically.

### Read the charts
1. The **By day** chart shows answered/missed call counts for each day.
2. The **By hour** chart shows the inbound/answered/missed breakdown by hour of day —
   useful for spotting your busiest hours.

### Analyze the queue and agent tables
1. In the **By queue** table, compare calls, answered, missed, avg wait, and SLA for
   each queue.
2. In the **By agent** table, see each agent's answered call count, total talk time, and
   average talk time.

## Tips and limits

> [!TIP]
> If you use several queues, first check the overall picture with **All queues**, then
> review each queue separately — this helps you spot a problem queue faster.

- The date range can be at most **92 days** — a longer range triggers an error message.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Invalid date range" message | The end date is before the start, or the range exceeds 92 days | Shorten the range or fix the order |
| Chart/table shows "No data for this period" | No calls occurred in the selected range/queue | Change the range or queue |
| KPI values show "—" | Data is still loading, or no matching record was found | Wait a moment; refresh the page if it persists |

## Related sections

- [Call history](/docs/cdr)
- [Queues](/docs/queues)
- [Quality scoring](/docs/quality)
- [Dashboard](/docs/dashboard)
