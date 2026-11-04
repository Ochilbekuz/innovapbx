---
id: network
title: Network
group: system
order: 80
path: /settings/network
summary: Hostname, DNS, network interfaces, and static routes — with safe apply and automatic rollback.
---

# Network

The server's network settings: hostname, DNS servers, each network interface (DHCP/static/manual), and
static routes. If a change isn't confirmed after taking effect, it is **automatically rolled back** to the
previous state — a safeguard against completely losing connectivity to the server.

## Where to find it
Menu: **System → Network**, three tabs: **General**, **Interfaces**, **Static routes**. Who sees it:
only a user with the `*` (full administrator) permission.

## Core concepts

- **View-only mode** — if the server's network is managed by **netplan** or **NetworkManager**, editing
  from this page **does not work** (editing is only possible on a Debian/ifupdown setup) — the reason is
  shown in a banner.
- **If the network service (netd) is down** — changes cannot be applied at all; the error is shown in a
  banner.
- **Draft** — on-screen changes are not sent to the server immediately; they are first saved as a
  **draft**; the number of pending changes is shown below.
- **Apply → Confirm flow**: clicking **Apply** first validates the changes, then shows **what will
  change (diff)**, you set a **timeout**, and confirm. The change takes effect immediately, but stays in a
  **pending** state.
- **Automatic rollback** — if you don't click **Confirm** within the set time, the change is
  **automatically rolled back** to the previous state — protecting you from, for example, losing server
  connectivity after entering a wrong IP. You can also roll back at any time with **Roll back now**.
- **Interface mode**: DHCP, Static (manual IP/CIDR and gateway), Manual, Unconfigured.
- **Static route** — a destination (CIDR), gateway, optional interface, and metric.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Hostname | The server's name on the network | — |
| DNS servers | IPs separated by commas or lines | — |
| Search domains | DNS search domains | `innova.local` |
| **Interface** → Mode | DHCP / Static / Manual | — |
| Address (CIDR) | IP/mask in static mode | `192.168.10.20/24` |
| Gateway | Optional | `192.168.10.1` |
| MTU | The interface's MTU value | — |
| **Route** → Destination (CIDR) | Which network | `10.20.0.0/16` |
| Gateway / Interface / Metric | How to route it | Interface default: Automatic |
| Confirmation time | How long you have to confirm after applying | — |

## How to

### Change general settings
1. On the **General** tab, edit the hostname, DNS servers, and search domains.
2. See the number of pending changes in the panel below.

### Configure an interface
1. On the **Interfaces** tab, click **Configure** on the interface's row (this button doesn't appear for
   interfaces that can't be edited).
2. Choose a **Mode**: DHCP, Static, or Manual.
3. If Static is chosen, enter the **Address (CIDR)** and optional **Gateway**, and **MTU** if needed.
4. Click **Save** — this is added to the draft and is not yet sent to the server.

### Add/edit/delete a static route
1. On the **Static routes** tab, click **Add route**, or choose **Edit**/**Delete** on an existing row.
2. Enter the destination (CIDR), gateway, optional interface, and metric.
3. Click **Save**.

### Apply and confirm changes
1. If there are changes in the draft, click **Apply** in the bottom panel.
2. The system validates them; if there's an error, the relevant fields are marked in red.
3. If it's valid, **what will change (diff)** and any warnings are shown — set the **Confirmation time**
   (a default value is provided), and confirm **Apply**.
4. The change takes effect immediately and moves to a **pending** state — a live countdown is shown
   above.
5. Once you've confirmed the new setting works correctly, click **Confirm** — this makes the change
   permanent.
6. If you don't confirm within the time limit, the system **automatically rolls back** to the previous
   state; you can also click **Roll back now** to revert immediately.

### Cancel the draft
1. You can discard changes that haven't been applied yet by clicking **Cancel** — the draft reverts to
   the server's current state.

## Tips and limitations

> [!WARNING]
> If a new setting is wrong and you lose connectivity to the server — **don't worry**, if you haven't
> confirmed it, the system rolls back to the previous state **on its own** once the time limit expires.

> [!TIP]
> If you need more time to test, increase the **Confirmation time** — but if you don't confirm before it
> expires, it still rolls back automatically, so don't rush to confirm until you're sure it's working.

- On servers managed by Netplan/NetworkManager, this page works in **view-only** mode.
- Only one **pending** change can exist at a time — until it's resolved (confirmed/rolled back), a new one
  cannot be applied.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Network settings are view-only" | Managed by Netplan/NetworkManager | Editing is only possible on a Debian (ifupdown) setup |
| "Network service (netd) is not running" | The netd service has stopped | Check/restart the netd service on the server |
| "Validation failed" | Invalid CIDR/IP format or a required field is empty | Fix the fields marked in red |
| The change stayed pending | Not confirmed/rolled back | Click **Confirm** or **Roll back now**, or wait for the time limit to expire |
| Can't connect to the server after applying | A wrong IP/gateway was entered | Do nothing — it will roll back automatically once the time limit expires |

## Related sections

- [Firewall](/docs/firewall)
- [SIP & network](/docs/sip)
- [System status](/docs/status)
- [Troubleshooting](/docs/muammolar)
