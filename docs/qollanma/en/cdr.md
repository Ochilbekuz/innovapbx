---
id: cdr
title: Call history
group: reports
order: 10
path: /cdr
summary: History of every call — date/direction filters, advanced search, listen to recordings, CSV export.
---

# Call history

Every single call that passed through the PBX is stored here: who called, who they called, when, how long
it lasted, how it ended (answered/no answer/busy) and, if recording was enabled, the audio recording. For
example, if a customer says "nobody called me back," you can search for their number here and see when
and who called them.

## Where
Menu: **Reports → Call history**. Who can see it: a user with `reports:view`/`reports:edit`
permission sees **all** calls; an operator with only `calls:read:own` permission sees **only** calls
(incoming or outgoing) belonging to their own extension.

## Key concepts

- **Direction**: Inbound (from outside), Outbound (to outside), Internal (between two extensions).
- **Outcome (disposition)**: Answered, No answer, Busy, Failed.
- **DID** — the external number an inbound call arrived on (the number on the trunk).
- **Account (accountcode)** — the PIN account tag attached to the call (if related to `/pinsets`).
- **QA** — if this call has been scored, the score is shown as a percentage (details —
  [Quality scoring](/docs/quality)).

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Start / End | Date range (date + hour:minute, Tashkent time) | Default: last 7 days, 00:00–23:59 |
| Direction | All / Inbound / Outbound / Internal | Default: All |
| **Advanced search** → From (src) | Calling number — with a match mode (contains/begins with/ends with/exact) + "Exclude" (negation) | e.g. `99890` |
| To (dst) | Receiving number — same mode/negation | e.g. `99890` |
| DID | Inbound external number — same mode/negation | e.g. `998712345678` |
| Caller name | Exact text search | — |
| Extension (ext) | Exact text search | — |
| Trunk | Search by trunk name | — |
| Account (accountcode) | Search by account code | — |
| Recording | All / With recording / Without recording | Default: All |
| Duration (seconds) | Min/Max — whole, non-negative number | — |
| Outcome | Multiple values can be selected (Answered, No answer, Busy, Failed) | Default: all |

## How to

### Simple search (date + direction)
1. Pick the **Start**/**End** date and time (default — last 7 days).
2. Choose the **Direction** if needed.
3. The table updates automatically.

### Advanced search
1. Click **Advanced search** — a panel opens (in the style of FreePBX's "CDR Reports").
2. Choose a match mode (contains, begins with, ends with, exact match) for From/To/DID,
   and enable **Exclude** (negation) if needed — e.g. to find calls where "DID contains `998`
   is **excluded**".
3. Fill in the other fields (name, ext, trunk, account, duration, outcome, recording).
4. Click **Search**. The number of active filters is shown as a badge next to the button.
5. **Clear** — cancels all advanced filters.

### Save and reuse a search template
1. Fill in the filters you need in the advanced panel.
2. Enter a name in **Save current search** and click **Save** (a template with the same
   name is replaced).
3. Later, pick it from the **Saved template** list and click **Apply** — the form is fully
   restored.
4. If you don't need it anymore, select the template and remove it with the delete icon.
5. Templates are only saved in this browser (`localStorage`) — they don't appear on another
   device/browser.

### Listen to, download, or delete a recording
1. In the table, click the player button in the **Recording** column to listen directly
   from there (you can also change the playback speed).
2. Click the download icon to save the `.wav` file — the filename is formed automatically as
   `date_time_from_to`.
3. Only a user with `reports:edit` permission can click the delete icon, confirm, and
   permanently remove the recording.

### Evaluate a call
1. Click the **Evaluate** button in the **QA** column — the evaluation panel opens.
2. For details, see [Quality scoring](/docs/quality).

### Add an inbound number to the blacklist
1. The **Block** button only appears on inbound call rows.
2. Enter a reason (optional) and click **Add** — the number is added to the
   [Blacklist](/docs/blacklist), and its future calls are rejected automatically.

### Export to CSV
1. Apply the date range and filters you need.
2. Click **Export CSV** — a `calls.csv` file is downloaded (matching the current filters).

## Tips and limits

> [!TIP]
> For a quick search, the simple search field above the table also works (by number/DID) —
> without opening the advanced panel.

> [!WARNING]
> Deleting a recording cannot be undone — the file is permanently removed from the server.

- CSV export outputs at most **10,000** rows at a time — if your range is very wide,
  narrow it down with an additional filter.
- The operator role only sees calls belonging to its own extension — the block and delete
  recording buttons aren't visible/active for it.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "No calls found in this range" | The date range or filter is too narrow | Widen the date range or cancel the advanced filters with **Clear** |
| Recording column is empty | Recording wasn't enabled for the call, or the file wasn't found | Check the recording setting (trunk/advanced settings) |
| An error appears while listening to a recording | The audio file is corrupted, or the connection to the server was lost | Refresh the page; if it persists, contact an administrator |
| Block button isn't visible | The call isn't inbound, or you lack permission | Only works on inbound calls and with `apps:edit` permission |

## Related sections

- [Live monitor](/docs/live)
- [Quality scoring](/docs/quality)
- [Blacklist](/docs/blacklist)
- [Analytics](/docs/analytics)
