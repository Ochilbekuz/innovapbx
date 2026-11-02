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

command -v docker >/dev/null || { echo "innova: docker CLI topilmadi (docker-cli paketi)" >&2; exit 1; }

if [ ! -s "$ENV_FILE" ]; then
  echo "innova: .env yaratilmoqda (tasodifiy sirlar)"
  umask 077
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
INNOVA_VERSION=$VERSION
EOF
  mv "$ENV_FILE.tmp" "$ENV_FILE"
fi

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
exec $COMPOSE -f docker-compose.yml -f docker-compose.appliance.yml --env-file "$ENV_FILE" \
  up -d --no-build --remove-orphans
