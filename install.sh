#!/usr/bin/env bash
# Innova PBX — MAVJUD Debian/Ubuntu serverga skript bilan o'rnatish (ISO o'rniga).
#
#   git clone git@github.com:Ochilbekuz/innovapbx.git && cd innovapbx
#   sudo ./install.sh                          # obrazlarni shu serverda yig'adi (internet kerak)
#   sudo ./install.sh --images images.tar.zst  # tayyor obrazlar bilan (yig'ishsiz)
#
# Parametrlar: --images FAYL, --version V (sukut: VERSION fayli), --web-port N (sukut 80), -h.
# Qayta ishga tushirish = YANGILASH: `.env` (sirlar) va baza saqlanadi, faqat obrazlar almashadi.
# O'rnatilgandan keyin yangilash: `innova-update` (GitHub'dan, baza zaxirasi bilan; --check, --images).
# Joylashuv ISO bilan bir xil: /opt/innova, servis `innova-pbx`, ishga tushirish `iso/files/innova-start.sh`.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DEST=${INNOVA_DEST:-/opt/innova}
UNIT=/etc/systemd/system/innova-pbx.service
DROPIN=$UNIT.d
SBIN=/usr/local/sbin
SERVICES="api asterisk web"
MIN_COMPOSE=2.24 # deploy/docker-compose.appliance.yml dagi `!reset` shuni talab qiladi

log() { printf '\033[1;33m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mXATO:\033[0m %s\n' "$*" >&2; exit 1; }

usage() { sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

parse_args() {
  IMAGES="" VERSION="" WEB_PORT=80
  while [ $# -gt 0 ]; do
    case $1 in
      --images) IMAGES=${2:?--images FAYL}; shift 2 ;;
      --version) VERSION=${2:?--version V}; shift 2 ;;
      --web-port) WEB_PORT=${2:?--web-port N}; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) die "noma'lum parametr: $1 (--help)" ;;
    esac
  done
  if ! [[ $WEB_PORT =~ ^[0-9]+$ ]] || [ "$WEB_PORT" -lt 1 ] || [ "$WEB_PORT" -gt 65535 ]; then
    die "--web-port 1..65535 bo'lsin"
  fi
  [ -z "$IMAGES" ] || [ -s "$IMAGES" ] || die "obrazlar fayli topilmadi: $IMAGES"
  if [ -n "$IMAGES" ]; then
    IMAGES=$(realpath "$IMAGES")
    VERSION=$(images_version "$IMAGES" "$VERSION") || exit 1
  fi
  [ -n "$VERSION" ] || VERSION=$(default_version)
  [[ $VERSION =~ ^[A-Za-z0-9._-]+$ ]] || die "--version faqat harf/raqam/._- bo'lsin"
}

default_version() {
  cat "$ROOT/VERSION" 2>/dev/null || date +%Y.%m.%d
}

# Obrazlar faylidagi versiya (innova-pbx/api:<V> tegi). --version berilgan bo'lsa — mos kelishi shart.
images_version() {
  local file=$1 asked=$2 found
  found=$(zstd -dc "$file" | tar -xOf - manifest.json 2>/dev/null \
    | grep -o '"innova-pbx/api:[^"]*"' | head -1 | tr -d '"' | cut -d: -f2) || true
  [ -n "$found" ] || die "$file ichida innova-pbx/api obrazi yo'q (docker save | zstd fayli kerak)"
  [ -z "$asked" ] || [ "$asked" = "$found" ] || die "--version $asked, faylda esa $found"
  echo "$found"
}

# a >= b (nuqtali versiyalar; `v` prefiksi tashlanadi, `+ds1`/`-4` qo'shimchalarini sort -V to'g'ri tartiblaydi)
version_ge() {
  local a=${1#v} b=${2#v}
  [ "$(printf '%s\n%s\n' "$b" "$a" | sort -V | head -1)" = "$b" ]
}

# /etc/os-release mazmuni -> docker o'rnatish usuli: distro | docker-repo | (bo'sh = qo'llanmaydi)
docker_source_for() {
  local id=$1 codename=$2
  case "$id:$codename" in
    debian:trixie) echo distro ;;
    debian:bookworm|ubuntu:jammy|ubuntu:noble) echo docker-repo ;;
    *) echo "" ;;
  esac
}

# `ss -Hlntu` chiqishidan band portlar (proto:port) — faqat bizga keraklilari
busy_ports() {
  local wanted=$1
  awk -v want=" $wanted " '{
      n = split($5, a, ":"); key = $1 ":" a[n]
      if (index(want, " " key " ")) print key
    }' | sort -u
}

require_root() { [ "$(id -u)" = 0 ] || die "root huquqi kerak: sudo $0"; }

detect_os() {
  local file=${OS_RELEASE:-/etc/os-release} pretty
  [ -r "$file" ] || die "$file yo'q — qo'llanmaydigan tizim"
  # os-release ham VERSION ni e'lon qiladi — o'zimiznikini bosmasin deb faqat subshell'da o'qiymiz
  # shellcheck disable=SC1090
  read -r OS_ID OS_CODENAME pretty < <(. "$file"; echo "${ID:-?} ${VERSION_CODENAME:--} ${PRETTY_NAME:-}")
  DOCKER_SOURCE=$(docker_source_for "$OS_ID" "$OS_CODENAME")
  [ -n "$DOCKER_SOURCE" ] || die "qo'llanadi: Debian 12/13, Ubuntu 22.04/24.04 (bu: $pretty)"
  [ "$(uname -m)" = x86_64 ] || die "faqat x86-64 (amd64) qo'llanadi"
}

check_ports() {
  if systemctl is-enabled innova-pbx >/dev/null 2>&1; then
    return 0 # yangilash — portlar o'zimizniki
  fi
  local busy
  busy=$(ss -Hlntu | busy_ports "tcp:$WEB_PORT tcp:443 tcp:5060 udp:5060 tcp:5061 tcp:5038 tcp:8088 tcp:5432 tcp:8710")
  [ -z "$busy" ] || die "portlar band: $(echo "$busy" | tr '\n' ' ')— boshqa PBX/veb-server/Postgres ishlayaptimi? (veb uchun --web-port)"
}

compose_version() {
  docker compose version --short 2>/dev/null || docker-compose version --short 2>/dev/null || true
}

install_packages() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -q
  apt-get install -y -q --no-install-recommends nftables zstd curl ca-certificates iproute2
}

install_docker() {
  local have
  have=$(compose_version)
  if [ -n "$have" ] && version_ge "$have" "$MIN_COMPOSE"; then
    log "docker mavjud (compose $have) — tegmayman"; return 0
  fi
  command -v docker >/dev/null && die "docker bor, lekin compose ${have:-topilmadi} < $MIN_COMPOSE — avval yangilang"
  log "docker o'rnatilmoqda ($DOCKER_SOURCE)"
  if [ "$DOCKER_SOURCE" = distro ]; then
    # trixie: `docker` CLI alohida paketda (docker.io uni faqat Recommends qiladi)
    apt-get install -y -q --no-install-recommends docker.io docker-cli docker-compose docker-buildx containerd runc iptables apparmor
  else
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL "https://download.docker.com/linux/$OS_ID/gpg" -o /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/$OS_ID $OS_CODENAME stable" \
      > /etc/apt/sources.list.d/docker.list
    apt-get update -q
    apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-compose-plugin docker-buildx-plugin
  fi
  systemctl enable --now docker
  have=$(compose_version)
  version_ge "${have:-0}" "$MIN_COMPOSE" || die "compose ${have:-topilmadi} < $MIN_COMPOSE"
}

install_files() {
  log "fayllar: $DEST"
  install -d -m 0700 "$DEST"
  install -d "$DEST/bin" "$DEST/deploy"
  install -m 0644 "$ROOT/deploy/docker-compose.yml" "$ROOT/deploy/docker-compose.appliance.yml" "$DEST/deploy/"
  install -m 0755 "$ROOT/iso/files/innova-start.sh" "$DEST/bin/innova-start"
  install -m 0644 "$ROOT/iso/files/innova-pbx.service" "$UNIT"
  install -m 0644 "$ROOT/iso/files/innova-guard.nft" "$DEST/guard.nft"
  install -m 0755 "$ROOT/iso/files/innova-update.sh" "$SBIN/innova-update"
  [ ! -d "$ROOT/.git" ] || echo "$ROOT" > "$DEST/SOURCE" # innova-update shu klonni yangilaydi
  install -d "$DROPIN"
  # Asterisk host tarmog'ida: AMI/HTTP faqat lokal va konteynerlardan (ISO'da buni to'liq nftables qiladi)
  # INNOVA_WEB_PORT — innova-start uni faqat `.env` birinchi yaratilganda yozadi
  printf '[Service]\nEnvironment=INNOVA_WEB_PORT=%s\nExecStartPre=/usr/sbin/nft -f %s/guard.nft\n' "$WEB_PORT" "$DEST" \
    > "$DROPIN/script.conf"
  echo "$VERSION" > "$DEST/VERSION"
  [ ! -f "$DEST/deploy/.env" ] || sed -i "s/^INNOVA_VERSION=.*/INNOVA_VERSION=$VERSION/" "$DEST/deploy/.env"
  systemctl daemon-reload
}

build_images() {
  log "obrazlar yig'ilmoqda ($VERSION) — 5–15 daqiqa"
  docker compose -f "$ROOT/deploy/docker-compose.yml" build migrate api asterisk web
  local svc
  for svc in $SERVICES; do
    docker tag "innova-m0-$svc:latest" "innova-pbx/$svc:$VERSION"
  done
  docker image inspect postgres:16 >/dev/null 2>&1 || docker pull postgres:16
}

provide_images() {
  if [ -n "$IMAGES" ]; then
    log "obrazlar fayldan: $IMAGES"
    cp "$IMAGES" "$DEST/images.tar.zst" # innova-start yuklaydi va o'chiradi
  else
    build_images
  fi
}

start_stack() {
  log "ishga tushirilmoqda"
  systemctl enable innova-pbx >/dev/null
  systemctl restart innova-pbx || {
    journalctl -u innova-pbx -n 30 --no-pager >&2; die "innova-pbx ishga tushmadi"; }
}

wait_ready() {
  local port _
  port=$(sed -n 's/^WEB_HOST_PORT=//p' "$DEST/deploy/.env")
  log "veb-panel kutilmoqda (port $port)"
  for _ in $(seq 1 90); do
    if curl -fsS -o /dev/null "http://127.0.0.1:$port/api/v1/setup/state"; then
      local ip code
      ip=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<NF;i++) if($i=="src") print $(i+1)}')
      log "TAYYOR: http://${ip:-<server-IP>}$( [ "$port" = 80 ] || echo ":$port")/ — administrator yarating"
      code=$(sed -n 's/^SETUP_CODE=//p' "$DEST/deploy/.env")
      [ -z "$code" ] || log "O'RNATISH KODI (/setup birinchi so'raydi, faqat shu safar): $code"
      return 0
    fi
    sleep 5
  done
  die "veb-panel 450 s ichida javob bermadi: journalctl -u innova-pbx; docker ps"
}

main() {
  parse_args "$@"
  require_root
  detect_os
  check_ports
  install_packages
  install_docker
  install_files
  provide_images
  start_stack
  wait_ready
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  main "$@"
fi
