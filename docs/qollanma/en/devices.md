---
id: devices
title: Phone devices
group: users
order: 20
path: /devices
summary: Automatic provisioning for physical IP phones — add devices, program keys, view config, log.
---

# Phone devices

This section automatically configures physical IP phones (Yealink, Grandstream, Fanvil, and others) over
the network: when powered on, a device fetches its configuration by itself, with no manual setup needed.

## Where

Menu: **Users → Phone devices**. Who can see it: the `extensions:view` permission. Full
management (add/edit/delete/keys/resync) requires `extensions:edit`; without it, a banner reading **"View
only — admin access is required to change this section"** appears at the top of the page.

## Key concepts

- **Provisioning** — a device fetching its own configuration file from the network
  (automatically via DHCP option 66, or from a manually entered address).
- **Discovered devices** — devices whose MAC address isn't in the list yet but sent a
  provisioning request; they can be attached to an extension or ignored.
- **Programmable keys (BLF/speed dial)** — assign colleague-presence display (BLF), speed
  dial, line, parking, or DND functions to device keys; the number available depends on the model.
- The screen has three tabs: **Devices**, **Settings**, **Log**.

## Fields

**Devices** table:

| Column | Shows |
|---|---|
| **Status** | **Never checked in**, **Provisioned**, **Registered**, **Needs update** |
| **MAC** | The device's MAC address |
| **Vendor / model** | E.g. Yealink T46S |
| **Extension** | The attached extension, or **Unassigned** |
| **IP** | Last seen IP |
| **Firmware** | Device firmware version |
| **Last seen** | Time of the last request |

**Add/edit device** form:

| Field | What it does | Example / default |
|---|---|---|
| **MAC address** | 12 hex characters (can also be entered with `:`/`-`); unchangeable once added | — |
| **Vendor** | Device manufacturer | Yealink / Grandstream / Fanvil |
| **Model** | List of models matching the chosen vendor | — |
| **Extension** | Which extension it connects to | **A device can't be attached to an extension with browser softphone (WebRTC) enabled** |
| **Label** | Optional, shown in the table and in the config | "Front desk" |
| **Enabled** | A disabled device won't receive configuration | default: enabled |

## How to

### Add a new device manually
1. On the **Devices** tab, click **Add device**.
2. Enter the **MAC address**, **Vendor**, **Model**, and **Extension**.
3. Enter an optional **Label**, click **Save**.

### Attach a discovered device
1. If a device has connected to the network but hasn't been set up yet, it appears in the
   **"Discovered devices"** section.
2. Click **Attach to extension** on the row you need.
3. Choose the **Extension** and **Model**, enter an optional **Label**, and confirm.
4. If you don't need it, click **Ignore** to dismiss the row.

### Configure programmable keys
1. In the table, click the **Keys** icon on the device row you need.
2. For each row, choose the type (**BLF (colleague)**, **Speed dial**, **Line**, **Park**,
   **DND**, **Empty**), and enter a value and label.
3. Add rows with **Add key** up to the number of keys allowed by the model, then click
   **Save**.

### View configuration and resync
1. Click the **Config** icon on a row to view the current configuration file (passwords are
   masked with `***`).
2. If the device is running on an outdated configuration, click **Resync** to send a request
   for the device to fetch the new configuration.

### Rotate the provisioning token
1. In the **Provisioning address** card at the top of the **Devices** tab, click
   **Rotate token**.
2. Read the warning and confirm — the old address stops working immediately; every device
   will need its provisioning address updated manually or via DHCP automatically.

## Tips and limits

> [!TIP]
> If you configure **option 66** on your DHCP server to point to the provisioning URL, new
> devices start up automatically with no manual setup at all.

> [!WARNING]
> A physical device can't be attached to an extension with **browser softphone (WebRTC)**
> enabled — the two don't work together on the same extension.

> [!WARNING]
> After rotating the provisioning token, every device that didn't get the address via DHCP
> needs the new URL entered manually, otherwise it can't fetch the new configuration.

> [!NOTE]
> If several devices are attached to one extension, all of them ring at once for direct
> calls. For calls placed as a queue member, via the API, or in paging groups, only one device
> rings — this is a limitation of Asterisk's `Page()`.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Unknown MAC" (in the log) | A device not in the list sent a provisioning request | Attach it in the "Discovered devices" section |
| "Bad token" | The device still has the old provisioning address | Manually enter the new URL/DHCP address on the device |
| "Network denied" | The device's IP isn't in the allowed networks list on the **Settings** tab | Add the device's network to **Allowed networks (CIDR)** on the Settings tab |
| **Needs update** status | The device's configuration changed, but the device hasn't fetched it yet | Click **Resync**, or reboot the device |
| "Rate limited" (in the log) | Requests from one device are coming in too fast | Wait a bit and try again; if it persists, check the network/device settings |

## Related sections

- [Extensions](/docs/extensions)
- [My portal](/docs/portal)
