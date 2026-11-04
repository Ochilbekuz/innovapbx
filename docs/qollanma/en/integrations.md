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
- **Bitrix24 / amoCRM** — logs completed calls into the CRM, creates a lead for unknown numbers
  (Bitrix24) or drops them into "Unsorted" (amoCRM), with popup/click-to-call support. Secret fields
  (token, webhook address) are **masked** once saved, and are only replaced when re-entered.
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
| **Bitrix24** → Inbound webhook URL / Create lead / Popup duration (s) / Default user ID / App token | Connection | — |
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
1. Enable the integration on the **Bitrix24** tab.
2. Enter the **inbound webhook URL** from Bitrix24, and an **app token** if needed.
3. Configure lead creation for unknown numbers and the popup duration.
4. Click **Save**, then click **Test connection** to check the result.
5. Enter the shown **click-to-call address** into Bitrix24's outbound webhook settings.

### Connect amoCRM
1. Enable the integration on the **amoCRM** tab, and enter the portal address and long-lived token.
2. Enable dropping unknown numbers into "Unsorted" if you want that.
3. Click **Save** and **Test connection**.

### Configure user mapping (Bitrix24/amoCRM)
1. In the **User mapping** table on the relevant tab, enter the CRM user ID for each extension row and
   click **Save mapping**.
2. A banner shows unmatched extensions — they're routed to the default user.

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

- A webhook address **can't point to loopback or internal addresses** — this is blocked for security.
- Bitrix24/amoCRM secret fields (token, webhook address) are masked once saved — leaving them blank when
  saving keeps the **existing** value unchanged.
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
| Speech synthesis "Test" doesn't work | There are unsaved changes | Click **Save** first |
| "Settings were changed elsewhere" | Another administrator saved at the same time | The page refreshes the values — re-check and save again |

## Related sections

- [SIP & network](/docs/sip)
- [Security](/docs/security)
- [Audit log](/docs/audit)
