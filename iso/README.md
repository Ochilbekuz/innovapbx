# Innova PBX — o'rnatish ISO'si

Bitta ISO: **Debian 13 «trixie» (kernel 6.12 LTS)** + Docker + Innova PBX obrazlari. O'rnatish
**internetsiz** ishlaydi — hamma narsa ISO ichida.

## Nega Debian (Rocky emas)

- FreePBX 17 ham Debian 12 ga o'tgan (Sangoma CentOS asosidagi SNG7 ni to'xtatgan) — telefoniya
  dunyosida Debian asosiy platforma bo'lib qoldi.
- Debian 13 LTS qo'llab-quvvatlashi 2030 yilgacha; kernel 6.12 — uzoq muddatli (LTS) yadro.
- `docker.io` va `docker-compose` rasmiy Debian omborida — tashqi repo kerak emas, xavfsizlik
  yangilanishlari `security.debian.org` dan keladi.
- Innova PBX konteynerlarda ishlaydi, shuning uchun host OS minimal: SSH + Docker + nftables.

## O'rnatish

1. ISO'ni USB'ga yozing: `dd if=innova-pbx-<versiya>-amd64.iso of=/dev/sdX bs=4M conv=fsync`
   (yoki Rufus/balenaEtcher, «DD rejimi»). Virtual mashinada — CD sifatida ulang.
2. Yuklang. Menyuda birinchi qator **«Innova PBX — avtomatik o'rnatish»** — 10 soniyada o'zi boshlanadi.
   BIOS va UEFI ikkalasi ham ishlaydi.
3. Faqat bitta savol beriladi: **`innova` foydalanuvchisi paroli** (SSH va konsol uchun).
   DHCP bo'lmasa — tarmoq sozlamalari ham so'raladi.
4. ⚠️ O'rnatish muhiti bo'lmagan **birinchi disk to'liq o'chiriladi** (LVM, bitta bo'lim).
5. Qayta yuklangandan keyin birinchi ishga tushish 2–5 daqiqa oladi (obrazlar yuklanadi).
   Konsolda manzil chiqadi: `http://<IP>/` — brauzerda oching, **administrator yaratish** sahifasi chiqadi.

Talablar: x86-64, 2+ yadro, 4 GB RAM, 32 GB disk (yozuvlar ko'p bo'lsa — kattaroq).

## O'rnatilgandan keyin

| Nima | Qayerda |
|---|---|
| Stek fayllari, `.env` (avtomatik yaratilgan sirlar) | `/opt/innova/deploy/` (faqat root) |
| Servis | `systemctl status innova-pbx` |
| Konteynerlar | `sudo docker ps` |
| Firewall | `/etc/nftables.conf` |

Ochiq portlar: SSH 22, veb 80, SIP 5060 (UDP/TCP), SIP-TLS 5061, RTP 10000–20000/UDP.
AMI 5038, Asterisk HTTP 8088, Postgres va API tashqaridan **yopiq**.

Asterisk host tarmog'ida ishlaydi (SIP/RTP NAT'siz) — telefonlarni to'g'ridan-to'g'ri server IP'siga ulang.

**Statik IP** (PBX uchun tavsiya etiladi): `/etc/network/interfaces` da `iface <nic> inet static`
(`address`, `gateway`), `/etc/resolv.conf` da DNS, keyin `sudo systemctl restart networking`.

**Brauzer softfoni** mikrofon uchun HTTPS talab qiladi — `http://IP` da softfon qo'ng'iroq qila olmaydi;
stol telefonlari va SIP ilovalar ishlaydi.

## ISO yig'ish (dasturchi uchun)

```bash
# Debian netinst (sha256 skriptda tekshiriladi)
curl -LO https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-13.7.0-amd64-netinst.iso
iso/build-iso.sh --src debian-13.7.0-amd64-netinst.iso --version 2026.11.02
```

Kerak: Docker (compose v2), `xorriso`, `zstd`. Skript obrazlarni yig'adi, `debian:trixie` konteynerida
oflayn paket omborini tayyorlaydi, `preseed.cfg` va yuklash menyularini qo'shib ISO'ni qayta yozadi.

`--test-password-hash '<crypt>'` — faqat QEMU sinovi uchun (parol savolisiz to'liq avtomatik o'rnatish).
Bunday ISO'ni tarqatmang.

| Fayl | Vazifa |
|---|---|
| `preseed.cfg` | Debian o'rnatuvchisi javoblari (til, vaqt mintaqasi, disk, paketlar) |
| `files/install-target.sh` | `late_command`: Docker (lokal ombordan), firewall, servis |
| `files/innova-start.sh` | Har yuklanishda: birinchi marta `.env` + `docker load`, keyin `compose up` |
| `files/nftables.conf` | Host firewall (Docker jadvallariga tegmaydi) |
| `../deploy/docker-compose.appliance.yml` | Appliance qatlami: Asterisk host tarmog'ida, tayyor obrazlar |
