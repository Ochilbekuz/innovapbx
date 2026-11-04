---
id: firewall
title: Firewall
group: system
order: 140
path: /settings/firewall
summary: Control who can reach SSH/web panel/SIP/RTP services and which addresses are blocked, with a safe apply-and-confirm flow.
---

# Firewall

Manage the server's outer defenses here — which addresses may connect to **SSH**, the **web panel**,
**SIP**, and **RTP (voice)**, and which addresses are **blocked entirely**. As on the **Network** page,
a change is validated first, then waits for confirmation, and **automatically rolls back** if not
confirmed in time — this protects you from locking yourself out of the server entirely.

## Where
Menu: **System → Firewall**. Who can see it: only a user with `*` (full administrator) permission.

## Key concepts

- **Service** — there are four: **SSH**, **Web panel**, **SIP**, **RTP (voice)**. Each has an
  independent mode.
- **Mode**: **Open to all** (no restriction) or **Allowlist only** — only the listed
  IPv4 CIDR addresses may connect.
- **Allowed CIDRs** — the list of addresses entered in allowlist mode (e.g.
  `192.168.1.0/24`); if left empty, no one can connect (at least one CIDR is required).
- **Blocked addresses** — **ALL** ports (regardless of service) are closed for addresses on
  this list — the strictest restriction.
- **Self-lockout protection** — the system rejects a setting that would **automatically
  block** the address/session you're connected from — a warning appears and the change is prevented.
- **Draft** — changes on screen aren't sent to the server immediately; the number of
  pending changes is shown at the bottom.
- **Apply → confirm flow** — the same as the **Network** page: **Apply** validates, shows
  **what's changing (diff)**, you set a **confirmation window** (default **120 seconds**), and
  confirm it. The change takes effect immediately but stays in a **pending** state.
- **Automatic rollback** — if you don't click **Confirm** within the set time, the change is
  **rolled back automatically**; you can also roll it back any time with **Roll back now**.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| **Service** → Mode | Open to all / Allowlist only | Default: depends on the service |
| Allowed CIDRs | Allowed addresses in allowlist mode | `192.168.1.0/24` |
| Blocked addresses | Addresses with every port closed | — |
| Confirmation window (seconds) | Time to confirm after applying | 120 seconds |

## How to

### Change a service's mode
1. In the **Services** section, choose the mode for the service you need (SSH/Web
   panel/SIP/RTP).
2. If you choose **Allowlist only**, enter the addresses (comma or newline separated) in the
   **Allowed CIDRs** field.

### Block an address
1. Enter the IPv4 CIDRs you need (comma or newline separated) in the **Blocked addresses**
   field.

### Apply and confirm changes
1. If there are changes in the draft, click **Apply** in the bottom bar.
2. The system validates them; invalid fields are highlighted in red if there's an error.
3. If valid, **what's changing (diff)** is shown — set the **confirmation window** (default
   120 seconds) and confirm **Apply**.
4. The change takes effect immediately and moves to **pending** — a live countdown is shown
   at the top.
5. Once you've confirmed the server is still reachable (SSH/web panel) under the new rules,
   click **Confirm**.
6. If you don't confirm in time, the system **rolls it back automatically**; to roll back
   immediately, click **Roll back now**.

### Discard the draft
1. You can discard changes that haven't been applied yet by clicking **Discard**.

## Tips and limits

> [!WARNING]
> If new rules cut off your own access to the server (especially SSH/web panel) —
> **don't worry**, if you don't confirm, the system reverts to the previous state automatically
> once the time expires.

> [!TIP]
> Before restricting SSH and the web panel to **allowlist only**, **make sure** to add your
> own connecting address(es) to the list first — otherwise the setting is rejected (self-lockout
> protection).

- The blocked-addresses list takes priority over service mode — an address on it can't reach
  any service.
- Only one **pending** change can exist at a time — a new one can't be applied until the
  current one is resolved (confirmed/rolled back).
- Allowlist mode can't be left with an empty list — at least one CIDR is required.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Warning: this setting could have locked out the current administrator" | Your address ended up in the allowlist/blocked list | Add your address to the allowlist, or remove it from the blocked list |
| "No one — allowlist mode needs at least one CIDR" | Allowlist mode is selected but the list is empty | Enter at least one CIDR |
| "Validation failed" | Invalid CIDR format or a required field is empty | Fix the fields highlighted in red |
| The change stayed pending | Not confirmed/rolled back | Click **Confirm** or **Roll back now**, or wait for the window to expire |
| Can't reach the server (SSH/web) after applying | An incorrect CIDR was entered | Do nothing — it rolls back automatically once the window expires |
| "Firewall settings are read-only" | Blocked by `readonly_reason` | Resolve the shown reason and try again |

## Related sections

- [Network](/docs/network)
- [Security](/docs/security)
- [System status](/docs/status)
