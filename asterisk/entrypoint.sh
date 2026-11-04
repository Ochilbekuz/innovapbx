#!/bin/bash
# Innova PBX — Asterisk konteyneri entrypoint ustquruma.
# Sirlarni (.conf shablon) ENV'dan envsubst bilan to'ldiradi, keyin asl
# andrius/asterisk entrypoint'ga (PUID/PGID moslashuvi) topshiradi.
set -euo pipefail

: "${POSTGRES_HOST:?POSTGRES_HOST kerak}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_DB:?POSTGRES_DB kerak}"
: "${POSTGRES_USER:?POSTGRES_USER kerak}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD kerak}"
: "${AMI_USERNAME:?AMI_USERNAME kerak}"
: "${AMI_PASSWORD:?AMI_PASSWORD kerak}"
# M12 C L8: AMI ACL subnet'i — `docker-compose.yml`/`.appliance.yml` haqiqiy
# `innova-net` subnet'iga mos sukut beradi (xavfsizlik hisoboti).
: "${AMI_PERMIT_CIDR:=172.28.0.0/24}"
: "${DIALPLAN_DIR:=/srv/dialplan}"
: "${DIALPLAN_FILENAME:=extensions_innova.conf}"
: "${SECURITY_LOG_PATH:=/var/log/asterisk/innova/security.log}"
: "${SIP_ACL_FILENAME:=pjsip_acl_innova.conf}"

export POSTGRES_HOST POSTGRES_PORT POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD AMI_USERNAME AMI_PASSWORD AMI_PERMIT_CIDR SECURITY_LOG_PATH

# Image'dagi konfiguratsiya `/etc/asterisk` (baza image VOLUME'i — eski anonim
# hajm saqlanib qolishi mumkin) ga har ishga tushishda o'rnatiladi (Dockerfile izohi).
INNOVA_SHARE=/usr/share/innova/asterisk
cp -a "$INNOVA_SHARE/etc/." /etc/asterisk/

for tpl in res_pgsql.conf cdr_pgsql.conf manager.conf logger.conf; do
    envsubst < "/etc/asterisk/${tpl}.tpl" > "/etc/asterisk/${tpl}"
done

# M2c §2 — `security` logger kanali fayli uchun katalog. Asterisk `asterisk`
# (nomuvofiq) foydalanuvchi sifatida ishga tushadi (quyida `-U asterisk`) —
# katalog `root:root` bo'lib qolsa, Asterisk yoza olmay kanal JIM ravishda
# ro'yxatga kirmaydi (jonli aniqlangan xato, voicemail spool bilan BIR XIL qolip).
mkdir -p "$(dirname "$SECURITY_LOG_PATH")"
chown asterisk:asterisk "$(dirname "$SECURITY_LOG_PATH")"

mkdir -p "$DIALPLAN_DIR"
dialplan_file="$DIALPLAN_DIR/$DIALPLAN_FILENAME"
if [ ! -f "$dialplan_file" ]; then
    printf '; Innova PBX — API hali hech narsa qo'"'"'llamagan (bo'"'"'sh dialplan).\n' > "$dialplan_file"
fi

# MOH (M1b) — `musiconhold.conf`dagi #include birinchi ishga tushishda ham
# muvaffaqiyatli bo'lishi uchun (API hali hech qanday MOH sinfini qo'llamagan
# bo'lsa ham) — xuddi yuqoridagi dialplan bootstrap bilan BIR XIL qolip.
moh_file="$DIALPLAN_DIR/${MOH_FILENAME:-musiconhold_innova.conf}"
if [ ! -f "$moh_file" ]; then
    printf '; Innova PBX — API hali hech qanday MOH sinfini qo'"'"'llamagan (bo'"'"'sh).\n' > "$moh_file"
fi

# Park (M2a §3) — `res_parking.conf`dagi #include birinchi ishga tushishda ham
# muvaffaqiyatli bo'lishi uchun (lotni API `apply` paytida yozadi) — MOH bilan BIR XIL qolip.
park_file="$DIALPLAN_DIR/${PARKING_FILENAME:-res_parking_innova.conf}"
if [ ! -f "$park_file" ]; then
    printf '; Innova PBX — API hali park lotini yozmagan (bo'"'"'sh).\n' > "$park_file"
fi

# Konferensiya (M2a §4) — `confbridge.conf`dagi #include birinchi ishga
# tushishda ham muvaffaqiyatli bo'lishi uchun (profillarni API `apply`
# paytida yozadi) — MOH/park bilan BIR XIL qolip.
confbridge_file="$DIALPLAN_DIR/${CONFBRIDGE_FILENAME:-confbridge_innova.conf}"
if [ ! -f "$confbridge_file" ]; then
    printf '; Innova PBX — API hali konferensiya profilini yozmagan (bo'"'"'sh).\n' > "$confbridge_file"
fi

# SIP ACL (M2c §2, S33) — `pjsip.conf`dagi #include birinchi ishga tushishda
# ham muvaffaqiyatli bo'lishi uchun (ban ro'yxatini API `apply_acl()` yozadi) —
# MOH/park/confbridge bilan BIR XIL qolip.
acl_file="$DIALPLAN_DIR/$SIP_ACL_FILENAME"
if [ ! -f "$acl_file" ]; then
    printf '; Innova PBX — hozircha bloklangan IP yo'"'"'q.\n' > "$acl_file"
fi

# SIP/RTP (S32) — API sozlamalardan generatsiya qiladi; birinchi ishga tushishda
# image'dagi standart (API `BOOT_DEFAULT` bilan bir xil — pytest majburlaydi).
for conf in pjsip_transports_innova.conf rtp_innova.conf; do
    if [ ! -f "$DIALPLAN_DIR/$conf" ]; then
        cp "/etc/asterisk/${conf%.conf}.default.conf" "$DIALPLAN_DIR/$conf"
        chmod 0644 "$DIALPLAN_DIR/$conf"
    fi
done

# Ovozli pochta (M1c §2): qutilar fayli (voicemail.conf #include) va
# `voicemail` umumiy hajm. Hajm API konteyneri tomonidan birinchi bo'lib
# yaratilsa ildizi root:root bo'lib qoladi — Asterisk (uid 1000) xabar yoza
# olishi uchun egasi har ishga tushishda tiklanadi (faqat ildiz, -R emas).
# Ovoz fayllari ham baza image VOLUME'ida — versiya belgisi bo'yicha o'rnatiladi.
sounds_en=/var/lib/asterisk/sounds/en
if ! cmp -s "$INNOVA_SHARE/sounds-en/.innova-core-sounds" "$sounds_en/.innova-core-sounds"; then
    mkdir -p "$sounds_en"
    cp -a "$INNOVA_SHARE/sounds-en/." "$sounds_en/"
    chown -R asterisk:asterisk "$sounds_en"
fi
vm_file="$DIALPLAN_DIR/${VOICEMAIL_FILENAME:-voicemail_innova.conf}"
if [ ! -f "$vm_file" ]; then
    cp /etc/asterisk/voicemail_innova.default.conf "$vm_file"
    chmod 0644 "$vm_file"
fi
mkdir -p /var/spool/asterisk/voicemail
chown asterisk:asterisk /var/spool/asterisk/voicemail
chmod 0750 /var/spool/asterisk/voicemail
# M3b §1 — MixMonitor yozuvlari (`recordings` volume; API ham rw — saqlash muddati tozalashi).
mkdir -p /var/spool/asterisk/monitor/innova
chown asterisk:asterisk /var/spool/asterisk/monitor /var/spool/asterisk/monitor/innova
chmod 0750 /var/spool/asterisk/monitor /var/spool/asterisk/monitor/innova

exec /usr/local/bin/entrypoint.sh "$@"
