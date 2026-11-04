---
id: security
title: Security
group: system
order: 30
path: /settings/security
summary: SIP attack protection (fail2ban style), IP blocking, toll-fraud limits, events, and 2FA policy.
---

# Security

Protection against attacks reaching the PBX server over SIP (repeated attempts with wrong passwords,
calling international numbers through a compromised account — "toll fraud") is configured here. How many
attack attempts occurred in the last 24 hours, which IPs are blocked, and whether 2FA should be required
for everyone — all on one screen.

## Where
Menu: **System → Security**. Who can see it: everyone can view, but only a user with `*` (full
administrator) permission can change settings, and block/unblock IPs.

## Key concepts

- **SIP attack protection** — works like fail2ban: if more than a set number of **failed
  attempts** from one IP occur within a set **window** (seconds), that IP is **blocked**
  automatically.
- **Trusted networks** — IPs on these CIDRs are never auto-blocked (`127.0.0.0/8` is always
  trusted).
- **Treat the local network as trusted** — when enabled, an office phone (192.168.x.x,
  10.x.x.x, 172.16–31.x.x) is never blocked no matter how many times it fails to log in, but the
  attempts still show up in statistics.
- **Toll-fraud limits** — limit how many outbound calls (including international) one
  extension can make per hour/day; exceeding the limit blocks the extension automatically.
- **2FA policy** — who must use two-factor verification (via a TOTP app): no one, admins
  only, or every user.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| **SIP attack protection** → Enabled | Turns protection on/off | — |
| Max failed attempts | Blocked once this number is exceeded | — |
| Window (seconds) | Attempts are counted within this time window | — |
| Ban duration (seconds) | `0` — bans indefinitely until manually unblocked | — |
| Trusted networks (CIDR) | One per line, never blocked | `127.0.0.0/8` always |
| Never auto-block local network devices | When on — local IPs aren't blocked | — |
| **Toll fraud** → Enabled | Turns limits on/off | — |
| Concurrent outbound calls | `0` — unlimited | — |
| Outbound calls per hour per extension | Hourly limit | — |
| International calls per day per extension | Daily international call limit | — |
| **2FA** → Required for | Not required / Admins only / Every user | Default: Not required |

## How to

### View recent attack attempts
1. On the **Status** tab, see the number of failed/blocked attempts in the last 24 hours
   and the hourly chart.
2. In the **Top offending IPs** list, find a suspicious IP and click **Block** if needed.

### Block an IP manually
1. On the **Blocked IPs** tab, click **Block IP**.
2. Enter the IP address and an optional note.
3. **Duration (seconds)** — `0` blocks indefinitely, otherwise it unblocks automatically
   after that many seconds.
4. Confirm **Block**.

### Unblock an IP
1. On the **Blocked IPs** list, click **Unblock** on the row you need.

### Configure SIP protection and toll-fraud limits
1. Open the **Settings** tab.
2. In the **SIP attack protection** block, set whether it's enabled, the limits, and
   trusted networks.
3. In the **Toll-fraud limits** block, enter the outbound call limits.
4. Click **Save**.

### Unblock an extension blocked for toll fraud
1. On the **Toll fraud** tab, find the blocked extension and click **Unblock**.

### Set the 2FA policy
1. On the **Settings** tab, choose **Required for** in the **Two-factor verification
   (2FA)** block.
2. Click **Save** — the chosen group will be required to connect via a TOTP app on their
   next sign-in.

### View security events
1. On the **Events** tab, filter by type (IP blocked, unblocked, toll fraud, etc.) and
   browse the history.

## Tips and limits

> [!WARNING]
> If you mark the local network as trusted, a compromised/infected device inside the
> office can also attempt logins without limit — only use this on a genuinely trusted office
> network.

> [!TIP]
> If you connect to the admin panel from your own static IP, add it to **Trusted
> networks** — so you don't accidentally block yourself.

- If the ban duration is `0`, the IP stays blocked until manually unblocked.
- Setting the 2FA policy to "Every user" requires every user to connect via a TOTP app on
  their next sign-in (for lost 2FA devices — see [Troubleshooting](/docs/muammolar)).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| My own IP got blocked | SIP protection treated incorrect login attempts as an attack | An administrator unblocks it from **Blocked IPs**; then add your IP to **Trusted networks** |
| Extension can't place calls, "toll fraud" reason | The hourly/daily limit was exceeded | Unblock it on the **Toll fraud** tab; raise the limit in **Settings** if needed |
| "Invalid IP address" | The CIDR/IP format is wrong | Enter it in the correct format, e.g. `203.0.113.9` |
| 2FA device lost | The user can't access their TOTP app | See the "If a 2FA device is lost" item in [Troubleshooting](/docs/muammolar) |

## Related sections

- [Firewall](/docs/firewall)
- [Audit log](/docs/audit)
- [Users and roles](/docs/rollar)
- [Troubleshooting](/docs/muammolar)
