---
id: sip
title: SIP & network
group: system
order: 10
path: /settings/sip
summary: External IP/hostname, local networks, SIP/RTP ports, codecs, TLS certificate, and notification channels.
---

# SIP & network

The core network settings that define how the PBX "talks" to the outside world and to phones: which
external IP/hostname is announced, which ports are used for voice (RTP), which codecs are enabled, the SIP
TLS (encrypted connection) certificate, and the email/Telegram channels used to send voicemail and alert
messages.

## Where
Menu: **System → SIP & network**. Who can see it: only a user with `*` (full administrator)
permission can change it; others see "You don't have permission to manage system settings — view only"
(fields are shown disabled).

## Key concepts

- **External IP/hostname** — the address the PBX announces for voice (RTP) streams when
  phones connect from behind NAT. If your server sits behind NAT, this must be its **public** IP address.
- **Local networks (CIDR)** — devices on these networks are treated as "NAT-free" (local); no
  special NAT handling is applied to them.
- **RTP range** — the port range used for voice packets; each active call takes a pair of
  ports from this range.
- **TLS certificate** — for encrypting SIP signaling (`sips://`); you can upload your own
  certificate or generate a self-signed one on the server.
- **Notifications** — settings for sending voicemail and other system messages via email
  (SMTP) and/or Telegram (e.g. [Alerts](/docs/alerts) arrive through these channels).

## Fields

| Field | What it does | Example / default |
|---|---|---|
| External IP | Public IP behind NAT (optional) | `203.0.113.10` |
| External hostname | External domain name (optional) | `pbx.company.com` |
| Local networks (CIDR) | One network per line | `192.168.1.0/24` |
| SIP UDP port | SIP signaling port | — |
| SIP TLS port | Encrypted SIP port (optional, must differ from the UDP port) | may be disabled |
| RTP start / end | Voice port range — at least a 100-port difference required | — |
| Codecs | `ulaw`, `alaw`, `g722`, `opus` — at least one must be selected | — |
| **TLS** → Certificate/Key/Chain | Files to upload (PEM format) | — |
| Common name | Domain name for the self-signed certificate | `pbx.company.com` |
| **Notifications** → SMTP host/port/encryption/user/password | SMTP server details for sending email | — |
| From email | The "From" field | — |
| Telegram bot token | Bot API token | — |
| Telegram API URL | Usually the default — rarely needs changing | — |

## How to

### Apply the detected network
1. The **Detected network** block at the top of the page shows the external IP and local
   networks the server detected automatically.
2. **Apply** — copies the detected external IP into the **External IP** field.
3. **Apply all** — copies the detected local networks into the **Local networks** field.

### Change SIP/RTP settings
1. Fill in the fields you need (external IP/hostname, local networks, ports, RTP range, codecs).
2. Click **Save**.
3. If the network settings changed, a warning appears at the top of the page — click
   **Restart** to reload the Asterisk service, otherwise the new settings won't take effect.
4. If there are active calls right now, the system warns you — choosing **Restart anyway**
   drops all active calls.

### Upload a TLS certificate
1. In the **TLS certificate** block, click **Upload certificate**.
2. Choose the certificate (`cert`) and private key (`key`) files (PEM format); the chain
   (`chain`) is optional.
3. Confirm **Upload certificate**.
4. If the certificate/key don't match, have expired, or aren't in PEM format, the system
   shows the exact reason.

### Generate a self-signed certificate
1. Click **Generate self-signed**.
2. Enter the **Common name** (domain name) and confirm.

### Set up notification channels
1. In the **Notifications** block, enter SMTP details (host, port, encryption type, user,
   password, from email) and/or the Telegram bot token and API URL.
2. Leaving the password/token field blank keeps the previously saved value unchanged.
3. Click **Save**.
4. In the **Test message** block, choose a channel (Email/Telegram), enter the address
   (email or Telegram chat ID/@channel), and click **Send test** to verify the channel is set up
   correctly.

## Tips and limits

> [!WARNING]
> Restarting the Asterisk service **drops all active calls**. Do this during a low-traffic
> period whenever possible.

> [!TIP]
> If the server is behind NAT at a cloud provider and you don't set the **External IP**
> correctly, calls may have one-way or no audio at all — see [Troubleshooting](/docs/muammolar) for
> details.

- The RTP range must be at least **100 ports**.
- The SIP UDP and TLS ports can't be the same.
- At least one codec must be selected.
- If the certificate is close to expiring (the number of days left is shown) or has already
  expired, a clear warning appears on the page.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "The RTP range must be at least 100 ports" | Not enough difference between start and end | Widen the range |
| "The UDP and TLS ports must not be the same" | Both ports have the same value | Change the TLS port to a different value |
| Certificate won't upload, "Key doesn't match the certificate" | Files from a mismatched pair were uploaded | Upload the correct cert/key pair |
| Certificate won't upload, "File isn't in PEM format" | A `.der` or other format was uploaded | Convert the file to PEM (`.pem`/`.crt`) and upload it |
| Test message not sent, "Couldn't connect to the SMTP server" | Wrong host/port, or the network is blocking it | Check the SMTP details |
| Test message not sent, "Invalid Telegram bot token" | The token was entered incorrectly | Check the token from the bot and re-enter it |
| No audio / one-way audio after restart | External IP or RTP range not open in the firewall | Check [Firewall](/docs/firewall) and [Troubleshooting](/docs/muammolar) |

## Related sections

- [Alerts](/docs/alerts)
- [Firewall](/docs/firewall)
- [Network](/docs/network)
- [Troubleshooting](/docs/muammolar)
