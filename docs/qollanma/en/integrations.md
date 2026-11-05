---
id: integrations
title: Integrations
group: system
order: 100
path: /settings/integrations
summary: REST API keys, webhooks, Bitrix24/amoCRM, 1C samples, call recording, and speech synthesis settings.
---

# Integrations

This is where you connect Innova PBX to external systems (a CRM, 1C, your own website, other
applications): keys for the open REST API, webhooks that notify you about events, Bitrix24/amoCRM
connections, ready-made 1C samples, and additional settings (public address, recording, speech
synthesis).

## Where to find it

Menu: **System → Integrations**, with seven tabs: **Overview**, **API keys**, **Webhooks**,
**Bitrix24**, **amoCRM**, **1C**, **Settings**. Who sees it: anyone can view, but only a user with `*`
(full administrator) permission can change anything — others see a "View only" banner.

## Core concepts

- **REST API keys** — a key grants access to the public `/api/public/v1/*` API; each key has its own
  **scopes**: reading calls, reading recordings, originating calls, reading extensions, an event stream
  (WebSocket). The full key value is shown **only once**, when it's created.
- **WebSocket event stream** — a key with the `events:read` scope can receive call events live; the page
  includes a ready-made connection sample.
- **Webhooks** — an HTTP POST is sent to your server about a call event (ringing/answered/ended); each
  delivery includes a signature (`X-Innova-Signature`); its secret is shown once and can be **rotated**
  at any time. Sending to loopback/internal addresses is blocked.
- **Delivery log** — shows every webhook delivery (success/error/stopped) and its HTTP status code;
  failed/stopped deliveries can be **resent**.
- **Bitrix24** — logs completed calls into the CRM card, creates a lead for unknown numbers, with
  popup/click-to-call support. Users are matched **automatically** by the **"Internal phone"** field on
  the employee profile (**"Sync from Bitrix24"**); you can still adjust it manually. Also available:
  routing first to the **responsible manager**, showing the caller's name, uploading the recording to
  the call card, and periodic auto-sync of users.
- **amoCRM** — logs completed calls into the CRM, drops unknown numbers into "Unsorted", with
  popup/click-to-call support. User mapping is manual only for now.
- For both integrations, secret fields (token, webhook address) are **masked** once saved, and are only
  replaced when re-entered.
- **User mapping** — maps each extension to the matching CRM user; it can be set **automatically**
  (detected by the system) or **manually**. Unmatched extensions are routed to a default user.
- **1C** — no separate server is required; download ready-made **BSL** samples that work with an
  existing API key and webhook. This code has only been syntax-checked, not run inside a 1C platform.
- The **Settings** tab covers: **public address** (used as the base for CRM/webhook links), **recording
  link expiry**, **call recording** retention period and external-only restriction, and **speech
  synthesis (Yandex SpeechKit)** — provider, API key, per-language voices, and a test option.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| **API key** → Name / Scopes / Expiry | Creates a key | Empty expiry — never expires |
| **Webhook** → Name / Address (URL) / Events / Include internal calls | Creates a new webhook | HTTP/HTTPS only |
| **Bitrix24** → Inbound webhook URL / App token / Create lead / Popup duration (s) / Default user ID / Show caller name / Upload recording / Route to responsible first + ring time (5–120 s) / Auto-sync users | Connection, calls, and routing | Default ring time: 20 s |
| **amoCRM** → Portal address / Long-lived token / Drop into "Unsorted" / Default user ID | Connection | — |
| **Settings** → Public address / Recording link expiry (s) | External links | — |
| Recording → Retention (days) / External calls only | Call recording policy | — |
| Speech synthesis → Provider / API key / Uzbek-Russian-English voices | Yandex SpeechKit | Default — disabled |

## How to

### Create an API key
1. On the **API keys** tab, click **Create key**.
2. Enter a name, select the required **scopes** (at least one is required), and set an expiry date if
   needed.
3. Click **Create** — the full key value is shown **only now**; copy it and store it somewhere safe.
4. A key you no longer need can be removed from the list with **Revoke** — this action **can't be
   undone**, and any integration using that key stops working immediately.

### Add and test a webhook
1. On the **Webhooks** tab, click **Add webhook**.
2. Set the name, address (URL), and which events it should be sent for; add internal (ext-to-ext) calls
   too if needed.
3. Click **Create** — the signing secret is shown once, save it.
4. Use **Send test** on the list row to send a test event, and check the result in the **Delivery log**.
5. Retry a failed delivery from the log with **Resend**.
6. Rotate the signing secret with **Rotate secret** if needed (the old one stops working).

### Connect Bitrix24
1. On the **Bitrix24** tab, turn on **Enable Bitrix24 integration**.
2. In the Bitrix24 admin panel, create **Applications → Webhooks → Inbound webhook**, selecting at
   least these scopes: `telephony`, `crm`, `user`/`user_basic`. Enter the resulting address into the
   **Inbound webhook URL** field.
3. In the **Connection** section, click **Save** — the portal address (host) is detected and shown on
   the status card ("Connected: ...").
4. On every employee's profile, in **Bitrix24 → Employees → profile → "Internal phone"**, enter their
   PBX extension.
5. On the status card or in the **Users** section, click **Sync from Bitrix24** — portal users are
   loaded and matched **automatically** by extension; any unmatched or duplicate-number cases show up
   in the sync report.
6. For click-to-call, enter the shown address into Bitrix24's outbound webhook (`ONEXTERNALCALLSTART`)
   settings, and set the **App token (application_token)** too — it's required for verification. For a
   cloud portal, this address must be **external (public)** (see the warning below).
7. If needed, in the **Routing** section turn on **Route to responsible manager first** and set the
   ring time (5–120 seconds) — if the responsible extension is busy/offline/unanswered, the call
   continues along the regular route.
8. In the **Users** section, turn on **Auto-sync users** so the mapping refreshes itself every 10
   minutes.

### Connect amoCRM
1. Enable the integration on the **amoCRM** tab, and enter the portal address and long-lived token.
2. Enable dropping unknown numbers into "Unsorted" if you want that.
3. Click **Save** and **Test connection**.

### Configure user mapping (Bitrix24/amoCRM)
1. **Bitrix24**: after at least one **sync from Bitrix24**, the table switches to picking from a list of
   Bitrix24 users. Choosing a different user from the list in a row marks it as **"Manual"**, and it's
   left unchanged by later syncs; pick "— by internal phone in Bitrix24 (auto) —" to go back to
   automatic matching.
2. **amoCRM**: in the **User mapping** table, enter the CRM user ID for each extension row and click
   **Save mapping** (manual only, for now).
3. For both integrations, a banner shows unmatched extensions — they're routed to the default user.

### Get 1C samples
1. Read the instructions on the **1C** tab: first create an API key with the `calls:originate` scope,
   then add a webhook.
2. Click **Download** for the sample you need and connect it to your 1C configuration as an HTTP
   service.

### General settings and speech synthesis
1. On the **Settings** tab, enter the **public address** (used as the base for CRM/webhook links) and
   set the recording link expiry.
2. In the **Call recording** section, set the retention period (days) and the external-only
   restriction.
3. In the **Speech synthesis** section, choose the provider (Yandex SpeechKit), enter the API key, set
   the voice for each language, click **Save**, then **Test** (you can't test unsaved changes — save
   first).

## Tips and limits

> [!WARNING]
> An API key or webhook secret is shown **only once, at creation** — it can't be viewed again
> afterward, only a new one can be created/rotated.

> [!TIP]
> The cards on the **Overview** tab let you see at a glance which integrations are connected (status
> indicator) — use the **Configure** button to jump to the relevant tab for details.

> [!WARNING]
> If the Bitrix24 portal is cloud-hosted (`*.bitrix24.*`), the click-to-call address must be
> **external (public)** — the cloud can't reach the PBX's private/internal address. When that's the
> case, the page shows a warning with a copy button; point **Settings** at an external address and
> forward the port to the PBX, and click-to-call will work — the other features (lead, popup, sync,
> recording upload) work even without it.

- A webhook address **can't point to loopback or internal addresses** — this is blocked for security.
- Bitrix24/amoCRM secret fields (token, webhook address) are masked once saved — leaving them blank when
  saving keeps the **existing** value unchanged.
- If Bitrix24's **"Internal phone"** field is wrong or empty, that employee won't be matched
  automatically during sync — pick them manually in the table, or fix the profile and sync again.
- Always save changes before testing speech synthesis — otherwise the test runs against the saved (old)
  setting and may give a misleading result.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Select at least one scope" | No scope was selected when creating the API key | Select the required scope(s) |
| "Sending a webhook to this address is blocked" | The URL is a loopback/internal address | Provide a real external address |
| Webhook "Automatically disabled" | Repeated failed deliveries | Read the reason, check the address/server, and re-enable it |
| CRM "Connection failed" | The token/address is incorrect | Re-check the details and save |
| "Unmatched extensions" banner | User mapping is incomplete | Map them in the **User mapping** table, or set a default user |
| Bitrix24 users table is empty | No sync has run yet | Click **Sync from Bitrix24** |
| Sync report shows "Internal phone exists in Bitrix24 but not in PBX" | The employee profile has a wrong/nonexistent extension | Fix **"Internal phone"** in Bitrix24 and sync again |
| Sync report shows "... phone number is on multiple users" | More than one employee profile has the same extension | Make extensions unique across Bitrix24 profiles |
| Click-to-call warning (cloud can't reach a private address) | Bitrix24 is cloud-hosted, the PBX address is private/internal | Point **Settings** at an external (public) address and forward the port to the PBX |
| Speech synthesis "Test" doesn't work | There are unsaved changes | Click **Save** first |
| "Settings were changed elsewhere" | Another administrator saved at the same time | The page refreshes the values — re-check and save again |

## Related sections

- [SIP & network](/docs/sip)
- [Security](/docs/security)
- [Audit log](/docs/audit)
