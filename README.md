# Innova PBX

Asterisk 22 ustida o'z veb-paneli bo'lgan IP-ATS: FastAPI + PostgreSQL 16 + React (Vite/TS), Docker Compose steki.

## O'rnatish

Ikki usul. Natija bir xil: `/opt/innova`, `innova-pbx` servisi, sirlar avtomatik yaratiladi.

| Usul | Qachon |
|---|---|
| **ISO** (`iso/README.md`) | Bo'sh server/VM: Debian 13 + Innova bitta diskdan, internetsiz |
| **Skript** (`install.sh`) | Mavjud Debian 12/13 yoki Ubuntu 22.04/24.04 server (x86-64) |

### Skript bilan

```bash
git clone git@github.com:Ochilbekuz/innovapbx.git && cd innovapbx
sudo ./install.sh                  # obrazlarni shu serverda yig'adi (internet, 5–15 daqiqa)
```

Oxirida `TAYYOR: http://<IP>/` chiqadi — brauzerda oching va administrator yarating.

Parametrlar:

- `--images images.tar.zst` — tayyor obrazlar bilan, yig'ishsiz. Fayl: ISO ichidagi `innova/images.tar.zst`
  yoki `docker save innova-pbx/api:V innova-pbx/asterisk:V innova-pbx/web:V postgres:16 | zstd -o images.tar.zst`.
  Versiya fayldan olinadi.
- `--web-port 8080` — 80-port band bo'lsa (masalan, serverda nginx bor). Faqat birinchi o'rnatishda yoziladi.
- `--version V` — obraz tegi (sukut: `YYYY.MM.DD-<commit>`).

**Yangilash** — `innova-update` (GitHub'dan yangi versiyani oladi, avval bazani `/opt/innova/backups/` ga zaxiralaydi,
so'ng qayta o'rnatadi; `.env` sirlari, baza va port saqlanadi). `innova-update --check` — faqat tekshirish,
`--force` — buzilgan o'rnatishni qayta o'rnatish, `--images FAYL` — oflayn. Joriy versiya: `cat /opt/innova/VERSION`.
`innova-update` 1.0.1 dan boshlab bor; undan eski o'rnatishda bir marta: `cd innovapbx && git pull && ./install.sh`.

Skript nima qiladi:

1. Tizimni va portlarni tekshiradi: 80, 5060, 5061, 5038, 8088, 5432, 8710. Band bo'lsa to'xtaydi —
   mavjud FreePBX/Asterisk bilan bir serverda ishlamaydi.
2. Docker o'rnatadi: Debian 13 — rasmiy Debian omboridan; Debian 12/Ubuntu — download.docker.com dan.
   Docker allaqachon bo'lsa (compose ≥ 2.24) — tegmaydi.
3. Fayllar `/opt/innova` ga (faqat root), `innova-pbx` servisi, ishga tushirish va tayyorlikni kutish.
4. Firewall: serverdagi qoidalaringizga TEGMAYDI. Faqat `inet innova_guard` jadvalini qo'shadi —
   AMI (5038) va Asterisk HTTP (8088) tashqaridan yopiladi. SIP 5060/5061, RTP 10000–20000/UDP va veb-port
   ochiq bo'lishi kerak — serveringizda firewall bo'lsa, o'zingiz oching.

Talablar: 2+ yadro, 4 GB RAM, 20+ GB bo'sh disk. Asterisk host tarmog'ida ishlaydi (SIP/RTP NAT'siz).

## Ishlab chiqish

- Dev stek: `deploy/docker-compose.yml` (API 127.0.0.1:8710, veb 127.0.0.1:8711).
- Testlar: `api/` — pytest; `web/` — vitest; `scripts/m*-proof.sh --fresh` — jonli isbotlar;
  `bash tests/install/test_install.sh` — o'rnatuvchi.
