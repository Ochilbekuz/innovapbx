---
id: missedcalls
title: Missed call alerts
group: apps
order: 90
path: /missed-calls
summary: Rules that automatically notify you about missed calls via Telegram/E-mail.
---

# Missed call alerts

This section sends an immediate notification to the right people about calls that went unanswered, via
**Telegram** or **E-mail**. For example: you could create a rule so that missed calls on any DID number
notify the manager's Telegram chat.

## Where to find it

Menu: **Applications → Missed call alerts**. Who sees it: users with the `apps` permission can edit;
everyone else can only view.

## Core concepts

- **Rule** — defines which calls (scope) it applies to, and who (recipients) gets notified.
- **Scope** — which calls the rule applies to: **All**, a specific **DID**, **Queue**, **Group**, or
  **Extension**.
- **Also include internal calls** — if disabled, only missed calls from outside are reported; if
  enabled, missed calls between extensions are also counted.
- **Recipients** — Telegram chat ID(s) and/or E-mail address(es); a rule can have several.
- **Message log** — a history showing each sent (or unsent) message's status (pending/sent/failed), the
  number of attempts, and the error text.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Name | Rule name | Required, up to 128 characters |
| Scope type | Which calls it applies to | All / DID / Queue / Group / Extension |
| Value | If the scope type isn't "All" — the specific DID/queue/group/extension | e.g. `998712345678` for DID |
| Also include internal calls | Whether internal-to-internal missed calls are also reported | Default — disabled |
| Telegram chat ID | Telegram chat(s) to notify | e.g. `-100123456789` |
| E-mail | Email address(es) to notify | e.g. `name@company.uz` |
| Enabled | Whether the rule is active or temporarily paused | Default — enabled |

## How to

### Create a new rule
1. Click **New rule** and enter a name.
2. Choose the **Scope type**; if it's not "All," enter the relevant value (DID/queue/group/extension).
3. Enable **Also include internal calls** if needed.
4. Add one or more **Telegram chat ID**s and/or **E-mail** addresses.
5. Click **Add**.

### Test a rule
1. Click the test icon (test button) on the rule's row — a test message is sent to all recipients.
2. The result appears as a toast notification: success or an error message.

### Temporarily disable a rule
1. Open the rule for editing, turn off **Enabled**, and click **Save** — the rule stops working but
   stays saved.

### View the message log
1. Go to the **Message log** tab — see the time, rule, call details, status, attempt count, and (if it
   failed) the error text for every sent message.

### Delete
1. Click the trash icon at the end of the row, and confirm.

> [!TIP]
> Use the **Test** button first to check that Telegram/E-mail is set up correctly — don't assume a
> previously working setup still is.

> [!WARNING]
> A single call can match multiple rules (e.g. an "All" rule and a specific "Queue" rule) — in that case,
> a separate notification is sent for **each matching rule**, so you may get duplicates.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| No notification arrives | The rule is disabled, or the scope doesn't match | Set the rule to **Enabled**, check the scope |
| Telegram message doesn't arrive | The chat ID is wrong, or the bot isn't in the group | Check the chat ID, add the bot to the group, confirm with **Test** |
| E-mail doesn't arrive | The address is wrong, or SMTP isn't configured | Check the SMTP settings in [Integrations](/docs/integrations) |
| Many "Failed" entries in the log | The recipient's address/chat is invalid | Read the error text and correct the recipient |

## Related sections

- [Integrations](/docs/integrations)
- [Queues](/docs/queues)
- [Ring groups](/docs/ringgroups)
- [CDR (call history)](/docs/cdr)
