---
id: time
title: Date and time
group: system
order: 130
path: /settings/time
summary: Choose the server and PBX time zone, and sync time with NTP servers over the internet.
---

# Date and time

Here you set the server's time zone and let the time be corrected automatically from internet **NTP**
servers. The chosen zone is used as both the **server** and **PBX** zone: business-hours rules (time
conditions, holidays), campaign windows, and the backup schedule all run in this zone.

## Where to find it
Menu: **System → Date and time**. Who sees it: only a user with the `*` (full administrator) permission.

## Core concepts

- **Server time** — the large clock at the top: the server's current time **in the server's zone**
  (ticks every second), with the date, zone, UTC offset (e.g. `UTC+05:00`), and UTC time next to it. It's
  based on the server, not your browser's clock.
- **Time source** — the NTP server that last provided the time (e.g. `0.asia.pool.ntp.org`) and the sync
  service's name (`timesyncd`). "No response" means the server hasn't gotten a response from any NTP
  server yet.
- **Synced/not synced** — whether the server's time currently matches the NTP source.
- **Time zone** — chosen from a list: searchable by city name or offset (`+05:00`), with the UTC offset
  shown next to each zone; Uzbekistan and neighboring zones appear at the top of the list.
- **NTP** — when enabled, the server's time is automatically corrected from internet NTP servers.
- **NTP servers** — IPs or hostnames, separated by commas or lines, up to 5. **If left empty**, the
  `pool.ntp.org` servers for the chosen zone's region are used (Asia — `0–3.asia.pool.ntp.org`, Europe —
  `europe`, etc.); if you specify your own servers, those remain as a fallback too.
- **Sync now** — restarts the NTP service and waits ~10 seconds for a response.
- **Changes apply immediately** — unlike **Network**/**Firewall**, this page has **no** confirm/automatic
  rollback flow — the change takes effect immediately after clicking **Save**.

## Fields

| Field | What it does | Example / default |
|---|---|---|
| Time zone | Server and PBX time zone | `Asia/Tashkent` (UTC+05:00) |
| NTP enabled | Turns automatic time sync from the internet on/off | Enabled |
| NTP servers | List of sync sources | Empty — the zone's regional pool servers |

## How to

### Change the time zone
1. Click the **Time zone** field — a searchable list opens.
2. Type a city name (e.g. "Tashkent") or an offset (`+05`) and choose the zone you need (the current time
   in that zone is shown below the field).
3. Click **Save**. If the zone changed, the PBX switches to the new zone too — a "PBX time zone updated"
   message appears.

### Sync the time with the internet
1. Check that **NTP enabled** is on (if off, turn it on and click **Save**).
2. Leave **NTP servers** empty (regional pool) or enter your own servers.
3. Click **Sync now** — "Time synced with the internet" and the source server's name appear.

### Enable/disable NTP and configure servers
1. Set the **NTP enabled** toggle to the state you want.
2. If enabled, enter the sources you need (IP or hostname) in the **NTP servers** field, separated by
   commas or one per line.
3. Click **Save**.

## Tips and limitations

> [!TIP]
> Choosing the right time zone matters for day/night mode, reports, and call log timestamps to display
> correctly — check this first after installing the server.

> [!WARNING]
> Changes on this page apply **immediately** — there's no automatic rollback like on the Network/Firewall
> pages, so enter the time zone and NTP servers carefully.

- If NTP is disabled, the servers field can't be edited and the **Sync now** button is disabled.
- Time-based conditions (business hours) are evaluated in the PBX zone — even though the Asterisk
  container itself runs in UTC.
- If the page is in "view-only" mode (`readonly_reason`), the reason is shown as a banner and nothing can
  be changed.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Time zone not found in the IANA list" | An invalid/nonexistent name was entered | Choose an exact name from the list |
| "Invalid NTP server" | The IP/hostname format is wrong | Enter a valid IP or hostname |
| "No more than N NTP servers allowed" | More servers were entered than allowed | Remove the extra servers |
| Page is "view-only" | Blocked by `readonly_reason` | Resolve the shown reason |
| "Not synced" always shown | No connection to NTP servers, or the service isn't running | Check the server's internet/network connection and the NTP server list |
| "No response from NTP server" (Sync now) | No internet, or outbound UDP port 123 is closed | Open UDP 123 in the firewall/router, or specify an internal NTP server |
| "NTP is disabled" | Sync was clicked while NTP is off | Turn on **NTP enabled** and save |

## Related sections

- [Network](/docs/network)
- [System status](/docs/status)
