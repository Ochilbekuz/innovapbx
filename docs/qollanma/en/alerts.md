---
id: alerts
title: Alerts
group: system
order: 40
path: /settings/alerts
summary: Settings for automatically sending Telegram notifications on security and trunk events.
---

# Alerts

When an IP is blocked, a toll-fraud block triggers, the concurrent call limit is reached, or a
trunk goes down/comes back up, the system automatically sends a message about the event to the
chosen Telegram chats. This page configures which events trigger a message, which chats receive
it, and how often.

## Where
Menu: **System → Alerts**. Who can see it: everyone can view, but only a user with `*` (full
administrator) permission can change the settings and send a test message.

## Key concepts

- **Telegram bot token** — must first be configured in the Notifications section of the
  [SIP & network](/docs/sip) page; if no token is set, a warning with a link to that page appears
  at the top.
- **Chat IDs** — the list of Telegram chats messages are sent to (a numeric ID, e.g.
  `-1001234567890`); you can add as many chats as you need.
- **Event types** — each can be turned on/off independently: IP banned, toll-fraud
  block, concurrent call limit, trunk went down, trunk came back up.
- **Dedup window** — the same event isn't resent within the set number of seconds (to
  avoid spam); `0` sends it every time.
- **History** — the status of every message sent: pending, sent, failed, suppressed
  (due to dedup), disabled (not sent because the event type was off).

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Chat ID | A Telegram chat (numeric) to send to | `-1001234567890` |
| IP banned (SIP attack) | Send on this event | — |
| Toll-fraud block | Send on this event | — |
| Concurrent call limit | Send on this event | — |
| Trunk went down | Send on this event | — |
| Trunk came back up | Send on this event | — |
| Dedup window (seconds) | `0` — always sent | — |

## How to

### Add/remove a chat ID
1. In the **Chat IDs** section, enter the Telegram chat ID in the field (pressing `Enter`
   also works).
2. Click **Add**.
3. To remove one, click the **×** button next to the chat you need.

### Choose which events send a message
1. In the "Which events to send" section, turn the events you need on/off.
2. In the **Dedup window** field, enter a number of seconds to limit how often the same
   message is resent.
3. Click **Save**.

### Send a test message
1. In the **Test message** section, click **Send test message**.
2. The system sends a real message with the current settings to every added chat and
   shows the result (how many chats it reached).
3. The sent message also appears in the **History** table.

### View the message history
1. In the **Sent alerts history** table at the bottom of the page, check the time, message
   text, and status.

## Tips and limits

> [!WARNING]
> If the Telegram bot token isn't configured, no message will be sent — set the token on
> the [SIP & network](/docs/sip) page first.

> [!TIP]
> After changing a setting, immediately click **Send test message** to confirm the chat ID
> was entered correctly.

- The same chat ID can't be added twice.
- A repeated event that arrives within the dedup window is logged in history as
  **suppressed**, with no message sent — this isn't an error.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Telegram bot token is not configured" banner | No token was entered on the SIP page | Configure the token on [SIP & network](/docs/sip) |
| Test message "Could not send" | The token is wrong, or the chat blocked the bot/the bot isn't in the chat | Check the token and chat ID; add the bot to the group/chat you need |
| An event occurred but no message arrived | The event type is disabled, or it was suppressed within the dedup window | Check "Which events to send"; check its status in **History** |
| "Settings were changed elsewhere" | Another administrator saved at the same time | The page refreshes the values — review and save again |

## Related sections

- [SIP & network](/docs/sip)
- [Security](/docs/security)
- [Audit log](/docs/audit)
