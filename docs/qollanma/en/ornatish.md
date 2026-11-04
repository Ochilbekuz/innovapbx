---
id: ornatish
title: Installation
group: start
order: 20
summary: Install Innova PBX via ISO or a script on an existing server, and update it afterward.
---

# Installation

Innova PBX can be installed in two ways — fully automatically via a ready-made **ISO**, or with a **script** on an existing Linux server; both result in the same outcome: an `/opt/innova` folder, an `innova-pbx` systemd service, and automatically generated secret keys.

## Core concepts

- **Requirements**: a 64-bit (x86-64) server, at least 2 cores, 4 GB RAM, 20 GB+ disk (32 GB+ for the ISO).
- **Asterisk runs in host network mode** — there is no NAT for SIP/RTP, so traffic reaches the server's IP directly.
- **ISO** — based on Debian 13 (trixie), can be installed without internet access, and takes over the entire disk for the server.
- **Script (`install.sh`)** — installs on top of Debian 12/13 or Ubuntu 22.04/24.04, requires internet access (to build or download Docker images), and does not touch other services on the server (only the required ports need to be free).
- Both methods end with a one-time **Installation code** printed to the console — this code is required when creating the administrator account during the [First-time setup](/docs/birinchi-sozlash) step.

## How to

### Install via ISO
1. Download the ISO and write it to a USB flash drive (using `dd`, Rufus, or Etcher in "DD mode") or attach it as a CD in a virtual machine.
2. Boot the server from that external drive. The first boot menu item — **"Innova PBX — automatic installation"** — starts on its own after 10 seconds (works with both BIOS and UEFI).
3. Only one question is asked: a password for the `innova` user (needed later for SSH and console access). If DHCP is not found, network settings (IP, mask, gateway, DNS) are also requested.
4. After installation finishes, the server reboots automatically; the first boot takes 2–5 minutes (Docker images are loaded).
5. Open the `http://<server-IP>/` address shown in the console in a browser from another computer — the administrator setup page ([First-time setup](/docs/birinchi-sozlash)) opens.

> [!WARNING]
> During installation, **the first disk found other than the selected one is completely wiped** (turned into LVM with a single partition). If the server has another disk holding data you need to keep, disconnect it before installing.

### Install via script (on an existing server)
1. Log in to the server as **root** and copy the project files (the repository) to the server.
2. Run the following command:
   ```
   sudo ./install.sh
   ```
3. The script first checks the required ports (80, 443, 5060, 5061, 5038, 8088, 5432, 8710) — if one is already in use (e.g. by an old FreePBX/Asterisk, another web server, or Postgres), it stops with an error.
4. If Docker is not installed, it is installed automatically (Debian 13 — from the official Debian repository; Debian 12/Ubuntu — from `download.docker.com`; this step is skipped if compose 2.24+ is already present).
5. Files are placed in `/opt/innova`, and the `innova-pbx` systemd service is created and started.
6. When ready, the console shows a `READY: http://<server-IP>/` message and a one-time **Installation code**.

### Additional parameters (script method only)
1. `--web-port 8080` — use a different port if port 80 is already in use (only applies on the first install; cannot be changed afterward).
2. `--images images.tar.zst` — install using a pre-built Docker images file (useful offline or for a faster install; the `innova/images.tar.zst` file from the ISO, or one prepared beforehand with `docker save ... | zstd`).
3. `--version V` — install a specific version (by default, the version from the project's `VERSION` file is used).

### Updating afterward
1. Log in to the server and run:
   ```
   innova-update
   ```
   This pulls the latest version from GitHub, first backs up the database to `/opt/innova/backups/`, and leaves the `.env` file / database / web port unchanged.
2. Only check whether a new version is available: `innova-update --check`.
3. Update using a pre-built images file: `innova-update --images FILE`.
4. Force a reinstall even if the version appears "up to date" (to fix a broken state): `innova-update --force`.

> [!NOTE]
> Systems installed before version 1.0.1 do not have `innova-update` — you need to run `git pull && ./install.sh` manually once, after which `innova-update` becomes available.

## Tips and limitations

> [!WARNING]
> Before installing, stop any other services occupying ports 80, 5060, 5061, 5038, 8088, 5432, 8710 (old FreePBX/Asterisk, a web server, Postgres) — otherwise the script will stop at this point.

> [!TIP]
> Giving the server a static IP is recommended — if DHCP changes the IP, SIP devices may lose their connection.

> [!WARNING]
> The browser softphone (WebRTC) requires **HTTPS** to access the microphone — it will not work over plain `http://server-IP`. Desktop phones and mobile SIP apps work fine regardless.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "ports in use" error | Another PBX/web server/Postgres is occupying these ports | Stop the conflicting service, or use `--web-port` for the web port |
| The `innova-pbx` service did not start | Docker container error | Check the cause with `journalctl -u innova-pbx -n 30` and `docker ps` |
| The web panel takes a long time to open | Images are still loading, or an error occurred | Check the logs with the commands above, then try again |
| Browser softphone doesn't work | The server has no HTTPS | Set up HTTPS (a certificate) for the server, or use a desktop phone/SIP app |

## Related sections

- [First-time setup](/docs/birinchi-sozlash)
- [Quick start](/docs/tez-boshlash)
- [Introduction](/docs/kirish)
