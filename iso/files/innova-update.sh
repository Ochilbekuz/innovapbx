#!/usr/bin/env bash
# innova-update — Innova PBX ni yangi versiyaga yangilash (install.sh o'rnatadi: /usr/local/sbin/innova-update).
#
#   innova-update                 # GitHub'dan yangi versiya → baza zaxirasi → yangilash
#   innova-update --check         # faqat tekshirish (yangi versiya bo'lsa exit 10)
#   innova-update --force         # yangi versiya bo'lmasa ham qayta o'rnatish (buzilganini tuzatish)
#   innova-update --images FAYL   # oflayn: tayyor obrazlar bilan (git'ga tegmaydi)
#
# Sozlamalar (.env sirlari, baza, port) saqlanadi. Har yangilashdan oldin baza zaxirasi:
# /opt/innova/backups/pre-update-<eski versiya>-<vaqt>.sql.gz (oxirgi 5 tasi).
set -euo pipefail

DEST=${INNOVA_DEST:-/opt/innova}
PG_CONTAINER=innova-m0-postgres-1
KEEP_BACKUPS=5

log() { printf '\033[1;33m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mXATO:\033[0m %s\n' "$*" >&2; exit 1; }

parse_args() {
  CHECK=0 FORCE=0 IMAGES=""
  while [ $# -gt 0 ]; do
    case $1 in
      --check) CHECK=1; shift ;;
      --force) FORCE=1; shift ;;
      --images) IMAGES=$(realpath "${2:?--images FAYL}"); shift 2 ;;
      -h|--help) sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
      *) die "noma'lum parametr: $1 (--help)" ;;
    esac
  done
}

env_value() { sed -n "s/^$1=//p" "$DEST/deploy/.env"; }

source_dir() {
  local src
  src=$(cat "$DEST/SOURCE" 2>/dev/null) || true
  if [ -z "$src" ] || [ ! -d "$src/.git" ]; then
    die "manba papka topilmadi ($DEST/SOURCE). Bir marta qo'lda:
  git clone git@github.com:Ochilbekuz/innovapbx.git && cd innovapbx && ./install.sh"
  fi
  echo "$src"
}

git_src() { git -c safe.directory="$SRC" -C "$SRC" "$@"; }

# Yangi versiya bormi: 0 = bor, 1 = yo'q. NEW_VERSION ni to'ldiradi.
fetch_update() {
  log "yangilanish tekshirilmoqda ($SRC)"
  git_src fetch -q origin || die "GitHub'ga ulanib bo'lmadi (internet / deploy kalit)"
  NEW_VERSION=$(git_src show '@{u}:VERSION' 2>/dev/null || echo "?")
  [ "$(git_src rev-parse HEAD)" != "$(git_src rev-parse '@{u}')" ]
}

backup_db() {
  local dir=$DEST/backups file
  file=$dir/pre-update-$CUR_VERSION-$(date +%Y%m%d-%H%M%S).sql.gz
  install -d -m 0700 "$dir"
  log "baza zaxirasi: $file"
  if ! docker exec "$PG_CONTAINER" pg_dump -U "$(env_value POSTGRES_USER)" "$(env_value POSTGRES_DB)" \
      | gzip > "$file.partial"; then
    rm -f "$file.partial"
    die "baza zaxirasi olinmadi — yangilash to'xtatildi (docker ps: $PG_CONTAINER ishlayaptimi?)"
  fi
  mv "$file.partial" "$file"
  BACKUP=$file
  # eng eskilarini o'chiramiz (yangi birinchi); nomlar o'zimizniki — ls xavfsiz
  # shellcheck disable=SC2012
  ls -1t "$dir"/pre-update-*.sql.gz | tail -n +$((KEEP_BACKUPS + 1)) | xargs -r rm -f
}

run_install() {
  local args=(--web-port "$(env_value WEB_HOST_PORT)")
  [ -z "$IMAGES" ] || args+=(--images "$IMAGES")
  "$SRC/install.sh" "${args[@]}" && return 0
  printf '\033[1;31mXATO:\033[0m yangilash yakunlanmadi. Orqaga qaytarish:\n' >&2
  printf '  git -C %s checkout %s && %s/install.sh --web-port %s\n' "$SRC" "$OLD_REV" "$SRC" "${args[1]}" >&2
  printf '  baza zaxirasi: %s\n' "$BACKUP" >&2
  exit 1
}

main() {
  parse_args "$@"
  [ "$(id -u)" = 0 ] || [ -n "${INNOVA_DEST:-}" ] || die "root huquqi kerak"
  CUR_VERSION=$(cat "$DEST/VERSION" 2>/dev/null || echo "?")
  SRC=$(source_dir)
  OLD_REV=$(git_src rev-parse --short HEAD)
  NEW_VERSION=$CUR_VERSION
  local available=0
  if [ -z "$IMAGES" ] && fetch_update; then available=1; fi

  if [ "$CHECK" = 1 ]; then
    [ "$available" = 1 ] || { log "eng so'nggi versiya: $CUR_VERSION"; return 0; }
    log "yangi versiya bor: $CUR_VERSION → $NEW_VERSION (o'rnatish: innova-update)"
    return 10
  fi
  if [ "$available" = 0 ] && [ "$FORCE" = 0 ] && [ -z "$IMAGES" ]; then
    log "eng so'nggi versiya: $CUR_VERSION — yangilash shart emas (qayta o'rnatish: --force)"
    return 0
  fi

  backup_db
  if [ "$available" = 1 ]; then
    log "kod yangilanmoqda: $CUR_VERSION → $NEW_VERSION"
    git_src merge -q --ff-only '@{u}' || die "git yangilanmadi: $SRC da qo'lda o'zgartirilgan fayllar bor (git -C $SRC status)"
  fi
  run_install
  log "yangilandi: $(cat "$DEST/VERSION" 2>/dev/null || echo "$NEW_VERSION")"
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  main "$@"
fi
