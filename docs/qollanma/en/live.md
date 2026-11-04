---
id: live
title: Live monitor
group: overview
order: 20
path: /live
summary: Track active calls, queues, and extension status in real time, with supervisor controls.
---

# Live monitor

Live monitor is a screen for supervisors and administrators: it shows in real time who is talking to whom, how many people are waiting in queues, and which extensions are busy/free — and lets you listen in, whisper, or barge into a call if needed.

## Where to find it

Menu: **Overview → Live monitor**. Who sees it: a role with the `monitor:view` permission. Supervisor controls (listen/whisper/barge) also require the matching write permission (`monitor:edit`).

## Core concepts

- **Supervisor (spy) modes** — ways to join an active call without the other party noticing:
  - **Listen** — hear only, without affecting the conversation.
  - **Whisper** — speak only to your side's agent; the caller does not hear you.
  - **Barge** — join the conversation fully as a third party; everyone can hear you.
- Page data refreshes automatically; duration counters tick live, second by second.
- If the connection to Asterisk is lost, a **"No connection to Asterisk"** warning appears at the top of the page and data temporarily stops refreshing.

## Fields

**Active calls** table:

| Column | What it shows |
|---|---|
| Direction icon | Inbound / outbound / internal call icon |
| **From** / **To** | The numbers of the call parties |
| **Status** | **Ringing**, **In call**, or **On hold** |
| **Duration** | Time elapsed since the call started (updates live) |
| Control buttons | **Listen** / **Whisper** / **Barge** |

**Queues** cards (one card per queue): **In queue** (number waiting), **Longest wait**, **Agents** (active out of total).

**Extension status** grid — for each extension: number, name, and a status indicator: **Idle**, **Ringing**, **Busy**, **Do not disturb**.

## How to

### Supervise an active call
1. Find the row you need in the **Active calls** table.
2. Click one of the three buttons on the right of the row: **Listen**, **Whisper**, or **Barge**.
3. If it starts successfully, a **"Supervision started"** notification appears.

### Check an extension's status
1. Scroll down to the **Extension status** section.
2. Each extension's card shows its current status with a colored indicator (e.g. a red **Busy** indicator).

## Tips and limitations

> [!WARNING]
> To supervise a call, your account must be linked to an extension — otherwise clicking the button shows the message **"Your account is not linked to an extension — you cannot supervise"**.

> [!TIP]
> Be careful with **Barge** mode — it makes you a full participant in the conversation, and everyone involved will hear you.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "No connection to Asterisk" warning | Connection to the Asterisk service has been lost | Check system health on the [Dashboard](/docs/dashboard); if it persists, contact the server administrator |
| "Could not start supervision" | The call has already ended, or your account is not linked to an extension | Refresh the table, check that your account has an extension assigned |
| The extension list is empty | No extensions have been created yet | Add a number in [Extensions](/docs/extensions) |

## Related sections

- [Dashboard](/docs/dashboard)
- [Extensions](/docs/extensions)
