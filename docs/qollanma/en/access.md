---
id: access
title: Access (SSH and web panel)
group: system
order: 150
path: /settings/access
summary: Safely change SSH and web-panel ports — with an apply/confirm flow, a login command, and a public confirmation link.
---

# Access (SSH and web panel)

Here you see how the server is reached — the **SSH** port and the **web panel**'s HTTP/HTTPS ports — and
can safely change them. Just like on the **Firewall** page, a port change is first applied, then waits
for confirmation: if you don't confirm, it **automatically rolls back** to the previous port once the
timeout expires — this protects you from permanently losing access to the server.

## Where

Menu: **System → Access**. Who sees it: only a user with `*` (full administrator) permission.

## Key concepts

- **SSH status** — shows whether sshd is running, the current port, listening ports, and whether
  password login is enabled or disabled.
- **Login instructions** — the `ssh -p <port> innova@<host>` command for the current port — copy it with
  one click using **Copy**.
- **Root login** — disabled for security; use `sudo -i` after logging in.
- **Host firewall** — if the server is protected by an external (hosting/ufw) firewall, a note reminds
  you to open the new port there too.
- **Apply → Confirm flow** — same as the **Firewall** page: after **Apply**, the change takes effect
  immediately but stays in a **pending** state, with a live countdown shown.
- **When the web-panel port changes** — after applying, the browser automatically navigates to the public
  confirmation page (`/access-confirm`) at the new address — click **Confirm** there to switch to the new
  address.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| New SSH port | The port the SSH service listens on | 1–65535, e.g. `2222` |
| HTTP port | The web panel's unencrypted port | e.g. `8080` |
| HTTPS port | The web panel's encrypted port | e.g. `8443` |
| Confirmation timeout (seconds) | How long you have to confirm after applying | has a default, can be changed |

## How to

### Change the SSH port
1. In the **SSH** section, enter the desired port (1–65535) in **New SSH port**.
2. Click **Apply** — the change takes effect immediately and enters the **pending** state.
3. Test the new-port connection (using the `ssh -p <port> ...` command shown on the page).
4. If it works, click **Confirm**. If you don't confirm in time, the port **automatically reverts** to
   the previous one.

### Change the web-panel ports
1. In the **Web panel** section, fill in **HTTP port** and/or **HTTPS port**.
2. Click **Apply** — in the dialog showing the new address, click **Apply** again.
3. The browser automatically navigates to the confirmation page at the new address — click **Confirm**
   there to return to the login page.
4. If you don't confirm in time, the ports **automatically revert** to the previous ones.

## Tips and limits

> [!WARNING]
> If the new port (especially SSH) makes you lose access — **don't worry**: if you don't confirm, the
> system will **automatically** restore the previous port once the timeout expires.

> [!TIP]
> Before changing the web-panel port, make sure the browser tab that opens the new confirmation link
> won't be blocked by a popup blocker.

- Only one change can be **pending** at a time — a new one can't be applied until the current one is
  resolved (confirmed or automatically rolled back).
- If a port is already used by another service, the related field is highlighted in red when applying.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "This port is already used by another service" | The entered port is already in use on the server | Choose a different free port |
| Warning that sshd is not running | The SSH service is stopped or not listening on the stated port | Check the sshd status on the server |
| Change stuck in pending state | Not confirmed | Click **Confirm**, or wait for the automatic rollback once the timeout expires |
| Can't reach the web panel at the new address | The new port isn't open in the external firewall | Open the new port in the external (ufw/hosting) firewall |
| Confirmation link doesn't work | The link is expired or invalid | Check that the previous address was restored automatically, then try again |

## Related sections

- [Firewall](/docs/firewall)
- [Network](/docs/network)
- [Security](/docs/security)
