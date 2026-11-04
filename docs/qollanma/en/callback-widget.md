---
id: callback-widget
title: Callback widget
group: apps
order: 110
path: /settings/integrations/widget
summary: A "Request a call back" button for your website — the customer leaves a number and the system calls them.
---

# Callback widget

A **widget** is a small script you add to your website that shows a button/form where a customer can
leave their phone number. Once the customer submits a number, the system first calls the **operator**
(an extension/queue/group/IVR), then calls the customer and connects the two. For example: a "Request a
call back" button on your site lets a customer leave their number — the system immediately calls the
sales department, then calls the customer.

## Where to find it

Menu: **Settings → Integrations → Website widget** (`/settings/integrations/widget`). Who sees it: users
with the `connect` permission can edit; everyone else can only view.

## Core concepts

- **Public key** — an identifier automatically generated for each widget and embedded in the code added
  to your website; it doesn't require a JWT/login, so the **Allowed domains** list is important to
  prevent abuse on untrusted sites.
- **Recipient (destination)** — the extension/queue/group/IVR that the customer's request is first
  called and connected to.
- **Allowed domains** — the widget script only works on domains in this list (e.g. `https://site.uz`);
  if the list is empty, the widget doesn't work at all.
- **Business hours group** — linked to a [Business hours](/docs/timegroups) condition; if none is
  selected, the widget is treated as always open.
- **Outside business hours** — "Reject" (the request is declined) or "Queue" (the call is made once
  business hours start).
- **Retries / Retry interval** — how many times and how long to wait before retrying if the operator
  doesn't answer.
- **Caller ID prefix** — text added before the name shown on the operator's phone (e.g. "Website:").
- **Appearance** — the button's color, position (left/right), and the title/button/success text for the
  uz/ru/en languages.
- **Request log** — the status of each incoming request (queued, dialing, connected, failed, rejected,
  cancelled) and its retry history.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Name | Widget name (internal, shown only in the panel) | Up to 128 characters |
| Recipient (operator side) | Where the call is routed first | Extension, queue, group, or IVR |
| Allowed domains | Domains the widget works on | e.g. `https://site.uz`; empty — doesn't work |
| Business hours group | Which schedule determines open/closed | Not selected — always open |
| Outside business hours | Reject or queue | Default — "Queue" |
| Retries | How many times to call if the operator doesn't answer | 1–5, default `2` |
| Retry interval (seconds) | Wait time between attempts | 60–1800, default `120` |
| Caller ID prefix | Extra text shown on the operator's screen | Up to 16 characters, e.g. `Website:` |
| Allow international numbers | Whether to accept a customer's international (+number) entry | Default — disabled |
| Color (HEX) | Button color | e.g. `#0f766e` |
| Position | Button's left/right screen corner | Default — right |
| Title / Button / Success text | Text for the uz/ru/en languages | — |

## How to

### Create a new widget
1. Click **New widget** and enter a name.
2. Choose the **Recipient** (extension/queue/group/IVR).
3. Add at least one domain (e.g. `https://site.uz`) to **Allowed domains**.
4. Set the business hours group, retries, Caller ID prefix, and appearance settings if needed.
5. Click **Add**.

### Add the widget to your website
1. Open the **Embed code** block on the created widget's row.
2. Click **Copy code** and paste it into your website right before the `</body>` tag.
3. If the server address (`public_base_url`) isn't configured, the system warns about it — contact an
   administrator.

### Edit a widget
1. Click the edit button on the row, change the fields you need, and click **Save**.

### Rotate the key
1. If you believe the public key has been compromised or misused, click **Rotate key**.
2. **Note**: the old URL stops working — you'll need to replace the embed script on your site with the
   new one.

### View the request log
1. Go to the **Request log** tab — see each request's time, phone/name, status, number of attempts, and
   (if it failed) the error text.

### Delete
1. Click the trash icon at the end of the row and confirm — the widget is removed and the site's script
   stops working.

> [!WARNING]
> Don't leave **Allowed domains** empty — otherwise the widget won't work at all. Only add domains you
> actually control, otherwise other sites could use the script too.

> [!TIP]
> Set a **Caller ID prefix** so the operator can immediately tell an inbound call came from the website.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| The widget doesn't appear on the site at all | The site's domain isn't in **Allowed domains**, or the list is empty | Add the correct domain (with https) |
| "Server address not configured" warning | `public_base_url` isn't set at the system level | Contact an administrator to configure the shared address |
| The customer left a number but the call never arrives | The business-hours condition is "Reject," or the recipient is busy | Check the business-hours setting and the recipient |
| International numbers aren't accepted | **Allow international numbers** is disabled | Enable this setting if needed |
| The old script stopped working | The key was rotated but the site's embed code wasn't updated | Copy the new embed code and update your site |

## Related sections

- [Business hours](/docs/timegroups)
- [Queues](/docs/queues)
- [Ring groups](/docs/ringgroups)
- [IVR](/docs/ivr)
- [Integrations](/docs/integrations)
