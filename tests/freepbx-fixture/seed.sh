#!/usr/bin/env bash
# Innova PBX — FreePBX haqiqiy manba stendini (fixture) ko'tarish va
# namuna konfiguratsiya bilan to'ldirish uchun IDEMPOTENT skript.
#
# Nima qiladi (har safar qayta ishga tushirilganda xavfsiz):
#   1) `innova-fpbx` docker compose stekini ko'taradi (agar allaqachon
#      ko'tarilgan bo'lsa — tegmaydi, mavjud innova-m0 stekiga HECH QACHON
#      tegmaydi, chunki butunlay boshqa compose loyihasi/tarmog'i).
#   2) "asterisk" bazasidagi barcha sinov jadvallarini tozalaydi (DELETE +
#      AUTO_INCREMENT reset) va astdb/custom-fayllarni dastlabki holatga
#      qaytaradi — shu orqali qayta ishga tushirish "duplicate key" bilan
#      qulamaydi.
#   3) seed_src/seed.php (asosiy namuna ma'lumot) va
#      seed_src/make_backup_job.php (haqiqiy Backup&Restore job) ni
#      konteyner ichiga nusxalab, PHP CLI orqali ishga tushiradi.
#   4) `fwconsole reload` + `fwconsole backup --backup=<id>` bilan haqiqiy
#      Asterisk konfiguratsiyasi va .tar.gz backup faylini generatsiya qiladi.
#   5) export/ papkasini (asterisk.sql, har-jadval TSV, astdb.txt, flat
#      config fayllar, backup tar.gz) to'liq qayta yaratadi.
#
# Ishlatish: ./seed.sh   (loyihaning o'zidagi katalogdan yoki istalgan joydan)
set -euo pipefail

SKRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SKRIPT_DIR"

COMPOSE_PROJECT="innova-fpbx"
APP="innova-fpbx-app"
DB_HOST="db"
DB_USER="freepbxuser"
DB_PASS="notabeneNYA76"
DB_NAME="asterisk"

log() { echo "[seed.sh] $*"; }

mysql_exec() {
  # Bitta SQL buyrug'ini konteyner ichidan, heredoc'siz (ilgari heredoc+bash -lc
  # naqshi DELETE'larni jim bajarmasligi sababli chalkashlikka olib kelgan edi —
  # shu sabab bevosita -e argumenti ishlatiladi).
  docker exec "$APP" mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "$1"
}

### 1) Stekni ko'tarish ##################################################

log "docker compose (-p $COMPOSE_PROJECT) stekini ko'tarish..."
docker compose -p "$COMPOSE_PROJECT" -f "$SKRIPT_DIR/docker-compose.yml" up -d

log "DB sog'lom (healthy) bo'lishini kutish..."
for i in $(seq 1 60); do
  status="$(docker inspect -f '{{.State.Health.Status}}' innova-fpbx-db 2>/dev/null || echo starting)"
  [ "$status" = "healthy" ] && break
  sleep 2
done
[ "$status" = "healthy" ] || { echo "[seed.sh] XATO: DB healthy bo'lmadi" >&2; exit 1; }

log "FreePBX ilovasi mysql'ga javob berishini kutish..."
for i in $(seq 1 60); do
  docker exec "$APP" mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" -e 'SELECT 1' >/dev/null 2>&1 && break
  sleep 2
done

### 2) Avvalgi sinov ma'lumotlarini tozalash (IDEMPOTENTLIK uchun) #######

log "Eski sinov ma'lumotlarini tozalash (DELETE + AUTO_INCREMENT reset)..."

# Haqiqiy wipe — DESCRIBE orqali tasdiqlangan hamma jadval. Tartib muhim:
# avval bola (child) jadvallar (outbound_route_*), keyin ota (outbound_routes).
mysql_exec "
DELETE FROM outbound_route_patterns;
DELETE FROM outbound_route_trunks;
DELETE FROM outbound_route_sequence;
DELETE FROM outbound_route_email;
DELETE FROM outbound_routes;
DELETE FROM incoming;
DELETE FROM ringgroups;
DELETE FROM queues_details;
DELETE FROM queues_config;
DELETE FROM ivr_entries;
DELETE FROM ivr_details;
DELETE FROM timeconditions;
DELETE FROM timegroups_details;
DELETE FROM timegroups_groups;
DELETE FROM recordings;
DELETE FROM music;
DELETE FROM announcement;
DELETE FROM meetme;
DELETE FROM miscdests;
DELETE FROM findmefollow;
DELETE FROM sip;
DELETE FROM pjsip;
DELETE FROM devices;
DELETE FROM users;
DELETE FROM trunks;
ALTER TABLE outbound_routes AUTO_INCREMENT = 1;
ALTER TABLE ivr_details AUTO_INCREMENT = 1;
ALTER TABLE timeconditions AUTO_INCREMENT = 1;
ALTER TABLE timegroups_groups AUTO_INCREMENT = 1;
ALTER TABLE recordings AUTO_INCREMENT = 1;
ALTER TABLE music AUTO_INCREMENT = 1;
ALTER TABLE announcement AUTO_INCREMENT = 1;
ALTER TABLE miscdests AUTO_INCREMENT = 1;
UPDATE featurecodes SET customcode='' WHERE modulename='voicemail' AND featurename='myvoicemail';
"

log "astdb (CF/CFB/CFU/DND/blacklist/QPENALTY) sinov kalitlarini tozalash..."
docker exec "$APP" bash -lc "
asterisk -rx 'database deltree CF' >/dev/null 2>&1 || true
asterisk -rx 'database deltree CFB' >/dev/null 2>&1 || true
asterisk -rx 'database deltree CFU' >/dev/null 2>&1 || true
asterisk -rx 'database deltree DND' >/dev/null 2>&1 || true
asterisk -rx 'database deltree blacklist' >/dev/null 2>&1 || true
asterisk -rx 'database deltree QPENALTY' >/dev/null 2>&1 || true
"

log "Oldingi voicemail mailbox 105 yozuvini (agar bo'lsa) voicemail.conf'dan olib tashlash..."
docker exec "$APP" bash -lc "
sed -i '/^105=1105,/d' /etc/asterisk/voicemail.conf 2>/dev/null || true
sed -i '/^105@device=/d' /etc/asterisk/voicemail.conf 2>/dev/null || true
"

log "Custom fayllarni (sound/MOH) qayta yaratish uchun tozalash..."
docker exec "$APP" bash -lc "
rm -f /var/lib/asterisk/sounds/custom/sinov-tizim-yozuvi.* 2>/dev/null || true
rm -rf /var/lib/asterisk/moh/sinov-moh 2>/dev/null || true
"

log "extensions_custom.conf ni asl (bo'sh+sinov kontekst) holatga qaytarish..."
docker exec "$APP" bash -lc "cat > /etc/asterisk/extensions_custom.conf" <<'EXTCUSTOM'

; ======================================================================
; SINOV: qo'lda yozilgan custom kontekst — FreePBX GUI/DB orqali
; BOSHQARILMAYDI. Bu fayl FreePBX tomonidan generatsiya qilinmaydi va
; "Apply Config" bosilganda ham o'chirilmaydi (FreePBX konvensiyasi:
; extensions_custom.conf har doim bo'sh holatda yaratiladi va foydalanuvchi
; qo'lda to'ldirishi uchun mo'ljallangan, keyin #include qilinadi).
;
; MUHIM (Innova PBX import funksiyasi uchun fakt): bu kontekst HECH QANDAY
; MySQL jadvalida (extensions, ivr_details, va h.k.) iz qoldirmaydi —
; faqat shu matn faylida yashaydi. Demak, "FreePBX import" funksiyasi buni
; faqat FAYL DARAJASIDA (extensions_custom.conf ni o'qib tahlil qilish)
; orqali import qilishi mumkin, DB orqali EMAS. Birinchi versiyada bu holat
; QO'LLAB-QUVVATLANMAYDI (taxmin: ko'p real FreePBX serverlarida bu fayl
; ishlatiladi, shuning uchun import vositasi kamida ogohlantirish bermog'i kerak).
; ======================================================================
[sinov-custom-context]
exten => 999,1,NoOp(Sinov qo'lda yozilgan custom extension - DB'da yo'q)
 same => n,Answer()
 same => n,Playback(demo-congrats)
 same => n,Hangup()
EXTCUSTOM

### 3) Asosiy seed.php + backup job ######################################

log "seed.php va make_backup_job.php konteynerga nusxalanmoqda..."
docker cp "$SKRIPT_DIR/seed_src/seed.php" "$APP":/tmp/seed.php
docker cp "$SKRIPT_DIR/seed_src/make_backup_job.php" "$APP":/tmp/make_backup_job.php

log "seed.php ishga tushirilmoqda (namuna extension/trunk/route/IVR/... yaratish)..."
docker exec "$APP" php /tmp/seed.php

log "fwconsole reload (generatsiya qilingan Asterisk configlarni qo'llash)..."
docker exec "$APP" fwconsole reload

log "Backup & Restore job yaratilmoqda (haqiqiy FreePBX moduli orqali)..."
docker exec "$APP" php /tmp/make_backup_job.php
BACKUP_ID="$(docker exec "$APP" cat /tmp/backup_job_id.txt)"
log "Backup job id: $BACKUP_ID — haqiqiy .tar.gz generatsiya qilinmoqda..."
# `fwconsole backup` oxirida "Remote Maintenance" bosqichida benign (zararsiz)
# "Undefined array key 1" xatosi chiqishi mumkin — bu .tar.gz allaqachon to'liq
# yozilgandan KEYIN yuz beradi, shuning uchun bu yerda muvaffaqiyatsizlik
# sifatida hisoblanmaydi (`|| true`), lekin chiqish logda ko'rinadi.
docker exec "$APP" fwconsole backup --backup="$BACKUP_ID" || true

### 4) export/ papkasini to'liq qayta yaratish ###########################

log "export/ papkasi qayta generatsiya qilinmoqda..."
EXPORT_DIR="$SKRIPT_DIR/export"
mkdir -p "$EXPORT_DIR/tables" "$EXPORT_DIR/files/sounds/custom" "$EXPORT_DIR/files/moh/sinov-moh" "$EXPORT_DIR/backup"

docker exec "$APP" mysqldump -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" --single-transaction "$DB_NAME" \
  > "$EXPORT_DIR/asterisk.sql"

TABLES="users devices sip pjsip trunks outbound_routes outbound_route_patterns outbound_route_trunks outbound_route_sequence incoming ringgroups queues_config queues_details ivr_details ivr_entries timeconditions timegroups_groups timegroups_details recordings music announcement meetme miscdests findmefollow featurecodes"
for t in $TABLES; do
  docker exec "$APP" mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" -B "$DB_NAME" -e "SELECT * FROM $t;" \
    > "$EXPORT_DIR/tables/$t.tsv" 2>>"$EXPORT_DIR/tables/_errors.log" || true
done

docker exec "$APP" asterisk -rx "database show" > "$EXPORT_DIR/astdb.txt"

docker cp "$APP":/etc/asterisk/voicemail.conf "$EXPORT_DIR/files/voicemail.conf"
docker cp "$APP":/etc/asterisk/extensions_custom.conf "$EXPORT_DIR/files/extensions_custom.conf"
docker cp "$APP":/var/lib/asterisk/sounds/custom/. "$EXPORT_DIR/files/sounds/custom/" 2>/dev/null || true
docker cp "$APP":/var/lib/asterisk/moh/sinov-moh/. "$EXPORT_DIR/files/moh/sinov-moh/" 2>/dev/null || true

BACKUP_TAR="$(docker exec "$APP" bash -lc "find /var/spool/asterisk/backup -name '*.tar.gz' -newer /tmp/backup_job_id.txt 2>/dev/null | head -1 || find /var/spool/asterisk/backup -name '*.tar.gz' | sort | tail -1")"
if [ -n "$BACKUP_TAR" ]; then
  docker cp "$APP":"$BACKUP_TAR" "$EXPORT_DIR/backup/innova-fixture-backup.tar.gz"
  log "Backup fayli ko'chirildi: $EXPORT_DIR/backup/innova-fixture-backup.tar.gz"
else
  log "OGOHLANTIRISH: backup .tar.gz fayli topilmadi!"
fi

log "Tayyor. Stend ishlayapti:"
log "  GUI/API:  http://127.0.0.1:8720/"
log "  MySQL:    127.0.0.1:3320 (user=$DB_USER, db=$DB_NAME)"
log "  AMI:      127.0.0.1:5038 (faqat konteyner ichidan/portni ochmagan bo'lsak tashqaridan yo'q)"
log "To'liq hisobot/sxema: pbx-klon/replica/freepbx-source-notes.md"
