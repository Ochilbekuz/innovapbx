#!/bin/sh
# /opt/innova/bin/innova-start — `innova-pbx.service` (har yuklanishda; idempotent).
# Birinchi marta: tasodifiy sirlar bilan `.env`, ISO'dagi obrazlarni `docker load`. Keyin stekni ko'taradi.
set -eu

ROOT=/opt/innova
DEPLOY=$ROOT/deploy
ENV_FILE=$DEPLOY/.env
IMAGES=$ROOT/images.tar.zst
VERSION=$(cat "$ROOT/VERSION")

secret() { tr -dc 'A-Za-z0-9' < /dev/urandom 2>/dev/null | head -c "${1:-40}"; }

# Shu serverning global IPv4 manzillari (vergul bilan) — veb HTTPS sertifikat SAN'i uchun
# (app/services/web_tls_cert.py). Topilmasa bo'sh — sertifikat faqat hostname/localhost bilan.
server_ips() {
  ip -4 -o addr show scope global 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | paste -sd, -
}

command -v docker >/dev/null || { echo "innova: docker CLI topilmadi (docker-cli paketi)" >&2; exit 1; }

if [ ! -s "$ENV_FILE" ]; then
  echo "innova: .env yaratilmoqda (tasodifiy sirlar)"
  umask 077
  SETUP_CODE_NEW=$(secret 20)
  cat > "$ENV_FILE.tmp" <<EOF
# Innova PBX — o'rnatishda avtomatik yaratilgan. Sirlarni o'zgartirmang (bazadagi shifr shu kalitda).
POSTGRES_USER=innova
POSTGRES_DB=innova
POSTGRES_PASSWORD=$(secret)
INNOVA_DB_KEY=$(secret 48)
SECRET_KEY=$(secret 64)
AMI_USERNAME=innova
AMI_PASSWORD=$(secret)
INTERNAL_API_TOKEN=$(secret 48)
API_HOST_PORT=8710
WEB_BIND=0.0.0.0
WEB_HOST_PORT=${INNOVA_WEB_PORT:-80}
WEB_HTTPS_PORT=443
WEB_TLS_HOSTNAME=innova-pbx
WEB_TLS_SAN_IPS=$(server_ips)
INNOVA_VERSION=$VERSION
# 1.0.4: bir martalik o'rnatish kodi (Jenkins uslubi) — /setup FAQAT shu kod bilan ishlaydi,
# administrator yaratilgandan keyin keraksiz bo'ladi (server allaqachon sozlangan tekshiruvi ustun).
SETUP_CODE=$SETUP_CODE_NEW
EOF
  mv "$ENV_FILE.tmp" "$ENV_FILE"
  mkdir -p /etc/issue.d
  printf '\nInnova PBX o'"'"'rnatish kodi (birinchi kirishda /setup so'"'"'raydi): %s\n\n' "$SETUP_CODE_NEW" \
    > /etc/issue.d/90-innova-setup.issue
fi

# 1.0.4 yangilanishi: eski `.env` da HTTPS kalitlari yo'q — qo'shiladi (aks holda 443 o'rniga 8712).
# SETUP_CODE QO'SHILMAYDI: eski server allaqachon sozlangan.
env_add() { grep -q "^$1=" "$ENV_FILE" || printf '%s=%s\n' "$1" "$2" >> "$ENV_FILE"; }
# 443 boshqa dasturda band bo'lsa — 8443 (aks holda web konteyneri ko'tarilmay, panel yopilardi).
https_port=443
if ! grep -q '^WEB_HTTPS_PORT=' "$ENV_FILE" && ss -Hltn 'sport = :443' 2>/dev/null | grep -q .; then
  https_port=8443
  echo "innova: 443 band — HTTPS 8443 portda"
fi
env_add WEB_HTTPS_PORT "$https_port"
env_add WEB_TLS_HOSTNAME innova-pbx
env_add WEB_TLS_SAN_IPS "$(server_ips)"

if [ -f "$IMAGES" ]; then
  echo "innova: obrazlar yuklanmoqda ($VERSION) — bir necha daqiqa"
  zstd -dc "$IMAGES" | docker load
  rm -f "$IMAGES"
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
else
  COMPOSE="docker-compose"
fi
cd "$DEPLOY"
# `innova-net` subnet'i (1.0.13 dan beri shu) — AMI_PERMIT_CIDR/FORWARDED_ALLOW_IPS va nftables bilan mos.
export INNOVA_NET_SUBNET=172.30.0.0/24 INNOVA_NET_GATEWAY=172.30.0.1
exec $COMPOSE -f docker-compose.yml -f docker-compose.appliance.yml --env-file "$ENV_FILE" \
  up -d --no-build --remove-orphans
