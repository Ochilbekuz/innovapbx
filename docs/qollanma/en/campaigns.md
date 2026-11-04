---
id: campaigns
title: Campaigns
group: apps
order: 60
path: /campaigns
summary: Automatic outbound calling (autodialer) to a list of numbers — play an audio message or connect to an agent.
---

# Campaigns

A **campaign** automatically dials many numbers from a list, during a set day/time window. For example:
a "Payment reminder" campaign calls 500 customers between 09:00 and 20:00 on business days, plays an
audio message, and connects anyone who presses "1" to an agent.

## Where to find it

Menu: **Applications → Campaigns**. Who sees it: users with the `apps` permission can edit; everyone
else can only view (shown with a **"You don't have permission to manage campaigns"** warning).

## Core concepts

- **Mode** — two types: **Audio message** (plays audio once the customer answers, optionally "1" to
  connect to an agent, "9" for do-not-call) or **Connect to agent** (connects directly to an
  extension/queue/group as soon as the customer answers).
- **Status** — a campaign is in one of five states: **Draft** → **Running** → **Paused**/**Finished**/
  **Stopped**. Editing/deleting is only possible in **Draft** and **Paused** states — it can't be changed
  while **Running**.
- **Calling window** — days of the week + start/end time (Tashkent time). If the end time is earlier
  than the start (e.g. `22:00`–`02:00`), the window continues past midnight.
- **Pace and retries** — how many calls run in parallel, and how many times/how long to wait before
  retrying a busy/unanswered number.
- **Contacts** — a list of numbers uploaded via CSV; each one's status (queued, dialing, retrying, done,
  unreachable, skipped) and call outcome are tracked separately.
- **Opt-out** — numbers that pressed "9" go into the opt-out list entirely and are **never dialed again
  by any campaign**; this list is retained even if the campaign itself is deleted.

## Fields

### What the customer hears

| Field | What it does | Example / default |
|---|---|---|
| Name | Campaign name | Up to 80 characters |
| Mode | **Audio message** or **Connect to agent** | — |
| Audio message | The file played in "Audio message" mode | Chosen from the [Audio library](/docs/audio), required |
| Connect to | An extension, queue, or group number | Required in "Connect to agent" mode; needed in "Audio message" mode only if "1" is enabled |
| "1" — connect to agent | Pressing "1" after the message connects to the number above | Only shown in "Audio message" mode |
| "9" — do not call again | A number that presses "9" goes into the opt-out list | Default — enabled |
| Caller ID shown to customer | The number shown as caller ID | Empty — uses the trunk's configured number, 3–15 digits |

### When calls are made

| Field | What it does | Example / default |
|---|---|---|
| Start / End | The calling window (Tashkent time) | Default `09:00`–`20:00` |
| Days of week | Which days calls are made | Default — Monday through Saturday |

### Pace and retries

| Field | What it does | Example / default |
|---|---|---|
| Concurrent | Number of parallel calls | 1–30, default `2` |
| Retries | How many times to redial on busy/no answer | 1–5, default `3` |
| Interval, minutes | Wait before retrying | 1–1440, default `600` minutes (10 hours) |
| Ring time, seconds | How many seconds each attempt rings | 10–30, default `25` |

## How to

### Create a new campaign
1. Click **New campaign**.
2. Choose a **Name** and **Mode**.
3. For "Audio message" — select the audio, and enable/disable "1"/"9" as needed.
   For "Connect to agent" — fill in the **Connect to** field.
4. Set the calling window and days, and adjust pace/retry settings if needed.
5. Click **Create** — the campaign is created in **Draft** status; now you need to upload numbers.

### Upload numbers via CSV
1. Open the campaign and go to the **Upload numbers** section.
2. Choose a CSV file, or paste the text manually. Each line: number, name (optional); separator — comma
   or semicolon; the first line can be a header.
3. Duplicate and invalid lines are detected automatically and their count is shown.
4. Enable **Replace existing list** to delete all previous contacts and their results and replace them
   with the new list.
5. Click **Upload**.

> [!WARNING]
> You can't add new numbers to a finished or stopped campaign — create a new campaign instead.

### Start/pause/stop a campaign
1. Click **Start** on a campaign in **Draft** or **Paused** status — its state moves to **Running**.
2. To temporarily halt a running campaign, click **Pause** — you can resume it later with **Resume**,
   with the remaining contacts preserved.
3. Clicking **Stop** is **irreversible**: the campaign moves to **Stopped** and can't be restarted (use
   Pause for a temporary halt instead).

### Edit
1. Open a campaign in **Draft** or **Paused** status, change the fields you need, and click **Save**.
2. A campaign in **Running** status can't be edited — pause it first.

### Monitor contact progress
1. Inside the campaign, the **Contacts** table shows each number's status, attempt count, last/next
   attempt time, and result (answered, busy, no answer, on blacklist, etc.).
2. You can filter by status and search by number/name.
3. Use **Download CSV** to export the current contact list along with their results.

### Delete
1. A campaign in **Draft** or **Paused** status can be deleted — click the trash icon at the end of the
   row.
2. The campaign, all its contacts, and results are permanently deleted; only the **opt-out list** is
   kept.
3. A campaign in **Running** status can't be deleted — stop or pause it first.

> [!TIP]
> Set the calling window to a time that's convenient for customers (e.g. business days 09:00–20:00) —
> automatic calls at night or early morning can lead to complaints.

> [!WARNING]
> Numbers that opted out by pressing "9" are automatically skipped in **all** subsequent campaigns — this
> list cannot be reset from the panel.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Can't edit/delete the campaign | Its status is **Running** | Pause it first, then edit/delete |
| Many numbers show as "invalid" when uploading CSV | Numbers are in the wrong format or outside 3–15 digits | Enter numbers as digits only, with a valid length |
| The campaign isn't starting | The current time is outside the set calling window/days | Check the window and days, and widen them if needed |
| A customer always gets the "blacklisted" result | The number is on the [Blacklist](/docs/blacklist) or previously opted out by pressing "9" | Check the blacklist or the prior opt-out status |
| Pressing "1" doesn't connect to an agent | The **Connect to** field is empty or invalid | Fill it in — it must be an extension, queue, or group number |

## Related sections

- [Audio library](/docs/audio)
- [Blacklist](/docs/blacklist)
- [Queues](/docs/queues)
- [Ring groups](/docs/ringgroups)
