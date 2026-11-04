---
id: portal
title: My cabinet
group: users
order: 30
path: /me
summary: A personal page for each employee — DND, forwarding, queues, stats, voicemail, 2FA, browser phone.
---

# My cabinet

**My cabinet** is a personal page for each user to manage their own extension: controlling
do-not-disturb and forwarding, logging in/out of queues, viewing today's stats, listening to recent calls
and voicemail, and protecting the account with two-factor verification.

## Where

Menu: **Users → My portal**. Who can see it: any signed-in user, for their own data (`me:*`).
If no extension is linked to the account, the page shows **"No extension linked"** and the rest of the
sections are hidden — contact your admin.

## Key concepts

- **Do not disturb (DND)** — when on, calls won't reach you.
- **Call forwarding** — forwards all incoming calls permanently to another internal/external
  number (unconditional forwarding).
- **Follow Me** — rules for trying other numbers in sequence when busy/unanswered (details —
  [Extensions](/docs/extensions)).
- **Connect a phone (QR)** — set up the mobile Linphone app without typing a password, via a
  QR code; the link is one-time and expires after 60 seconds.
- **Browser phone** — the softphone chip at the top of the page (header): place/receive calls
  directly from the browser via WebRTC. Only shown for users whose extension has WebRTC enabled.
- **2FA (two-factor verification)** — optional; requires a 6-digit code from an app at sign-in.

## Fields

| Section | Shows/does |
|---|---|
| **Do not disturb (DND)** | On/off toggle + **Call forwarding** field (internal or external number) |
| **Today's stats** | **Calls**, **Missed**, **Talk time** |
| Follow Me | A condensed view — the list of sequential rules |
| **Connect a phone** | Button to open the QR dialog |
| **My queues** | Each queue: status (**Logged in**/**Logged out**/**Paused**), **Log in**/**Log out**/**Pause**/**Resume** buttons |
| **Recent calls** | Last 24 hours: time, direction, number, outcome badge, duration, call recording |
| **My evaluations** | Scorecards completed by quality control: date, checklist name, score percentage, comment |
| **Two-factor verification (2FA)** | Enable/disable, regenerate recovery codes |
| **Voicemail** | From, date, duration, listen/delete, unread badge |

## How to

### Turn on do-not-disturb and forwarding
1. In the **Do not disturb (DND)** card, turn on the toggle (if needed).
2. Enter an internal or external number in the **Call forwarding** field (leave it blank to
   disable forwarding).
3. Click **Save**.

### Connect a mobile phone via QR
1. Click **Connect a phone**.
2. Install the Linphone app on your mobile phone and open **Settings → Assistant →
   "Scan QR code"**.
3. Point the camera at the QR code shown — the number is added automatically. If the QR
   expires, click **New QR**.

### Log in, log out, or pause in a queue
1. In the **My queues** card, find the queue row you need.
2. Click **Log in** to join it; click **Log out** to leave.
3. For a temporary break, click **Pause**, enter an optional reason and confirm; click
   **Resume** when you're back.

### Place a call from the browser (browser phone)
1. Click the softphone chip at the top of the page to open the panel.
2. Dial the number or enter it on the keypad and click **Call**.
3. During the call, use the mute, hold, transfer, or hang-up buttons as needed.

### Enable 2FA
1. In the **Two-factor verification (2FA)** card, click **Enable**.
2. Scan the QR code shown with an authenticator app (e.g. Google Authenticator) and enter
   the code to confirm.
3. Save the recovery codes shown somewhere safe, then click **Done**.

### Listen to or delete a voicemail message
1. Find the message you need in the **Voicemail** list.
2. Listen to it with the player; click the confirm icon to mark an unread message as read.
3. Click **Delete** if you no longer need it.

## Tips and limits

> [!WARNING]
> The **Connect a phone** QR link is one-time — it becomes invalid 60 seconds after the
> phone fetches it, and the password is never stored inside the QR code.

> [!WARNING]
> The browser phone requires **HTTPS** (or `localhost`) to access the microphone — the
> microphone won't work on a page opened over plain HTTP, and a warning appears.

> [!TIP]
> If queue membership is **static**, the **Log in**/**Log out** buttons aren't shown — the
> text reads "Static membership — ask your admin to log in/out for you."

> [!NOTE]
> If several physical devices are attached to one extension, all of them ring at once for
> direct calls; for calls placed as a queue member or via the API, only one device rings.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "No extension linked" | No extension has been attached to your account yet | Contact your administrator — it should be linked in [Extensions](/docs/extensions) |
| "HTTPS required" warning | The panel was opened over HTTP | Open the panel through an `https://` address |
| "Microphone access denied" | The browser didn't grant microphone access | Allow microphone access in the browser settings and refresh the page |
| "Data is stale" (when saving DND) | The data was changed elsewhere | Click the shown button and save again |
| QR code expired | More than 60 seconds passed | Click **New QR** and scan again |

## Related sections

- [Extensions](/docs/extensions)
- [Phone devices](/docs/devices)
