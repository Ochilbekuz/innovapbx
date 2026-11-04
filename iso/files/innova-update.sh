#!/usr/bin/env bash
# innova-update — Innova PBX ni yangi versiyaga yangilash (install.sh o'rnatadi: /usr/local/sbin/innova-update).
#
#   innova-update                 # GitHub'dan yangi versiya → baza zaxirasi → yangilash
#   innova-update --check         # faqat tekshirish (yangi versiya bo'lsa exit 10)
#   innova-update --force         # yangi versiya bo'lmasa ham qayta o'rnatish (buzilganini tuzatish)
#   innova-update --images FAYL   # oflayn: tayyor obrazlar bilan (git'ga tegmaydi)
#   innova-update --agent         # systemd path xizmati chaqiradi — status papkadagi `request`ni bajaradi
#
# Sozlamalar (.env sirlari, baza, port) saqlanadi. Har yangilashdan oldin baza zaxirasi:
# /opt/innova/backups/pre-update-<eski versiya>-<vaqt>.sql.gz (oxirgi 5 tasi).
#
# Paneldan yangilash (m11-update-contract.md): `--agent`/`--check` status papkaga
# (sukut /var/lib/innova/update, env INNOVA_UPDATE_DIR) `status`/`update.log`/
# `changelog.md`/`history` yozadi — FAQAT shu ikki rejim yozadi. Barcha rejimlar
# bitta vaqtda bitta ish uchun `flock -n` (yo'l env INNOVA_UPDATE_LOCK bilan).
set -euo pipefail

DEST=${INNOVA_DEST:-/opt/innova}
PG_CONTAINER=innova-m0-postgres-1
KEEP_BACKUPS=5
UPD=${INNOVA_UPDATE_DIR:-/var/lib/innova/update}
# H1c: `request`ni API konteyneri yozadi — shu SABAB o'z ALOHIDA yozish
# mumkin bo'lgan quyi papkada ($UPD/req), `status`/`history`/`update.log`/
# `changelog.md` esa $UPD TUBIDA qoladi (API konteyneriga FAQAT o'qish uchun
# `:ro` bog'lanadi, `deploy/docker-compose.appliance.yml`). Host agenti
# (shu skript) ikkisiga ham to'liq (haqiqiy fayl tizimi) kirishi davom etadi.
REQ=$UPD/req
LOCK=${INNOVA_UPDATE_LOCK:-/run/innova-update.lock}

# status fayli kalitlari (m11-update-contract.md bo'lim 1)
STATUS_KEYS="state phase current latest available checked_at started_at finished_at error backup"
declare -A STATUS
WRITE_STATUS=0   # 1 bo'lsa — die()/trap status papkaga yozadi
AGENT_LOG_ACTIVE=0
ERRCODE=""
CUR_VERSION="" NEW_VERSION="" SRC="" OLD_REV="" BACKUP="" CHECK_AVAILABLE=0

# H1a: `$UPD` ichidagi fayllarga yozishdan OLDIN har doim shu tekshiruv —
# fayl o'zi symlink BO'LMASLIGI va (mavjud bo'lsa) oddiy fayl bo'lishi kerak.
# Aks holda jim rad etiladi (symlink-hujum: `>>`/`tee -a` symlink'ni
# KUZATIB o'tib, nishon faylga yozardi). `mktemp+mv` (status/changelog,
# pastda yangi log-reset) BUTUNLAY xavfsiz — `mv` yo'lning o'zini
# almashtiradi, symlink nishoniga YOZMAYDI.
is_safe_append_target() {
  local path=$1
  [ -L "$path" ] && return 1
  [ -e "$path" ] && [ ! -f "$path" ] && return 1
  return 0
}

log() {
  printf '\033[1;33m==>\033[0m %s\n' "$*"
  if [ "$AGENT_LOG_ACTIVE" = 1 ] && is_safe_append_target "$UPD/update.log"; then
    printf '==> %s\n' "$*" >> "$UPD/update.log"
  fi
  return 0
}
die() {
  printf '\033[1;31mXATO:\033[0m %s\n' "$*" >&2
  if [ "$AGENT_LOG_ACTIVE" = 1 ] && is_safe_append_target "$UPD/update.log"; then
    printf 'XATO: %s\n' "$*" >> "$UPD/update.log"
  fi
  exit 1
}

# die()/kutilmagan chiqishda status papkaga `failed`+kod yozadi (faqat WRITE_STATUS=1 bo'lsa).
on_exit() {
  local rc=$?
  if [ "$WRITE_STATUS" = 1 ] && [ "$rc" != 0 ]; then
    status_set state=failed error="${ERRCODE:-install_failed}" finished_at="$(now_iso)"
    status_flush
    history_append "${CUR_VERSION:-}" "${NEW_VERSION:-}" "failed:${ERRCODE:-install_failed}"
  fi
  return 0
}
trap on_exit EXIT

parse_args() {
  CHECK=0 FORCE=0 IMAGES="" AGENT=0
  while [ $# -gt 0 ]; do
    case $1 in
      --check) CHECK=1; shift ;;
      --force) FORCE=1; shift ;;
      --agent) AGENT=1; shift ;;
      --images) IMAGES=$(realpath "${2:?--images FAYL}"); shift 2 ;;
      -h|--help) sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
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

strip_ansi() { sed -E "s/$(printf '\033')\\[[0-9;]*[A-Za-z]//g"; }

run_install() {
  local args=(--web-port "$(env_value WEB_HOST_PORT)") rc=0
  [ -z "$IMAGES" ] || args+=(--images "$IMAGES")
  # Izoh: `set -e` ostida "CMD; rc=$?" CMD muvaffaqiyatsiz bo'lsa `rc=$?` ga
  # yetmasdan skript to'xtaydi — shu uchun natija OR-ro'yxat orqali olinadi.
  if [ "$AGENT_LOG_ACTIVE" = 1 ] && is_safe_append_target "$UPD/update.log"; then
    "$SRC/install.sh" "${args[@]}" 2>&1 | strip_ansi | tee -a "$UPD/update.log" >/dev/null \
      || rc=${PIPESTATUS[0]}
  elif [ "$AGENT_LOG_ACTIVE" = 1 ]; then
    # H1a: update.log xavfsiz EMAS (symlink/g'ayrioddiy fayl) — faylga
    # yozilmaydi, faqat konsolga (pastdagi xato xabari bilan bir xil holat).
    "$SRC/install.sh" "${args[@]}" 2>&1 | strip_ansi || rc=${PIPESTATUS[0]}
  else
    "$SRC/install.sh" "${args[@]}" || rc=$?
  fi
  [ "$rc" = 0 ] && return 0
  printf '\033[1;31mXATO:\033[0m yangilash yakunlanmadi. Orqaga qaytarish:\n' >&2
  printf '  git -C %s checkout %s && %s/install.sh --web-port %s\n' "$SRC" "$OLD_REV" "$SRC" "${args[1]}" >&2
  printf '  baza zaxirasi: %s\n' "$BACKUP" >&2
  if [ "$AGENT_LOG_ACTIVE" = 1 ] && is_safe_append_target "$UPD/update.log"; then
    {
      printf 'XATO: yangilash yakunlanmadi. Orqaga qaytarish:\n'
      printf '  git -C %s checkout %s && %s/install.sh --web-port %s\n' "$SRC" "$OLD_REV" "$SRC" "${args[1]}"
      printf '  baza zaxirasi: %s\n' "$BACKUP"
    } >> "$UPD/update.log"
  fi
  exit 1
}

# ---------------------------------------------------------------- status papka
upd_usable() { [ -d "$UPD" ] && [ -w "$UPD" ]; }
now_iso() { date -u +%Y-%m-%dT%H:%M:%SZ; }
# H1b: ruxsat etilgan belgilar + uzunlik qopqog'i (32) — versiya/holat/vaqt
# belgilari uchun yetarli, lekin shell-metabelgilar/haddan tashqari uzun
# qiymatlarni (keyinroq history/log fayllariga, yoki boshqa status_set
# chaqiruvlariga oqib o'tishi mumkin bo'lgan) kesib tashlaydi. Qat'iy
# ro'yxatga olingan ro'yxat o'rniga umumiy belgilar to'plami ishlatiladi —
# `state`/`phase` ham, `current`/`latest` versiyalar ham, ISO vaqt
# belgilari ham shu bitta qolipga mos keladi (DRY).
sanitize_value() { printf '%s' "$1" | tr -cd 'A-Za-z0-9._:+-' | cut -c1-32; }

status_load() {
  local k
  for k in $STATUS_KEYS; do STATUS[$k]=""; done
  STATUS[state]=idle
  STATUS[available]=0
  # H1b: `[ -f ]` symlink'ni KUZATIB o'tib, nishon oddiy fayl bo'lsa TO'G'RI
  # deb topardi — tashqi (masalan /etc/shadow emas, lekin ixtiyoriy) faylni
  # status sifatida o'qib olish xavfi. `-L` BIRINCHI tekshiriladi.
  if [ -L "$UPD/status" ]; then
    return 0
  fi
  [ -f "$UPD/status" ] || return 0
  local k2 v
  while IFS='=' read -r k2 v; do
    case " $STATUS_KEYS " in *" $k2 "*) STATUS[$k2]=$(sanitize_value "$v") ;; esac
  done < "$UPD/status"
}

status_set() {
  local kv k v
  for kv in "$@"; do
    k=${kv%%=*}
    v=${kv#*=}
    STATUS[$k]=$(sanitize_value "$v")
  done
}

status_flush() {
  local tmp k
  tmp=$(mktemp "$UPD/.status.XXXXXX")
  for k in $STATUS_KEYS; do printf '%s=%s\n' "$k" "${STATUS[$k]}"; done > "$tmp"
  mv -f "$tmp" "$UPD/status"
}

# oldingi yugurish o'lgan (masalan reboot — /run lock ham tozalangan, status esa
# checking/updating holatida qolgan) → bitta aniq failed/interrupted yozuv.
status_fix_interrupted() {
  case "${STATUS[state]}" in
    checking|updating)
      local from=${STATUS[current]} to=${STATUS[latest]}
      status_set state=failed error=interrupted finished_at="$(now_iso)" phase=
      status_flush
      history_append "$from" "$to" "failed:interrupted"
      ;;
  esac
}

history_append() { # from to result
  upd_usable || return 0
  is_safe_append_target "$UPD/history" || return 0  # H1a
  printf '%s\t%s\t%s\t%s\n' "$(now_iso)" "$1" "$2" "$3" >> "$UPD/history"
}

changelog_write() {
  local tmp
  tmp=$(mktemp "$UPD/.changelog.XXXXXX")
  if git_src show '@{u}:CHANGELOG.md' > "$tmp" 2>/dev/null; then
    mv -f "$tmp" "$UPD/changelog.md"
  else
    rm -f "$tmp"
  fi
}

# Agent qulfni KUTADI: chiqib ketsa `request` qoladi va systemd path uni qayta-qayta
# ishga tushirib start-limit'ga uradi (path unit kuzatishni to'xtatadi). Kutish
# chegarasi — xizmatning TimeoutStartSec. CLI esa kutmaydi.
acquire_lock() {
  exec 9>"$LOCK" || die "lock fayl ochilmadi: $LOCK"
  if [ "$AGENT" = 1 ]; then flock 9; return; fi
  flock -n 9 || die "boshqa yangilanish ishlab turibdi (band: $LOCK)"
}

# CUR_VERSION/SRC/OLD_REV/NEW_VERSION/CHECK_AVAILABLE ni to'ldiradi; WRITE_STATUS=1
# bo'lsa status (current/latest/available/checked_at) + changelog.md ham yozadi.
perform_check_and_record() {
  CUR_VERSION=$(cat "$DEST/VERSION" 2>/dev/null || echo "?")
  [ "$WRITE_STATUS" = 1 ] && ERRCODE=no_source
  SRC=$(source_dir)
  OLD_REV=$(git_src rev-parse --short HEAD)
  NEW_VERSION=$CUR_VERSION
  [ "$WRITE_STATUS" = 1 ] && ERRCODE=fetch_failed
  CHECK_AVAILABLE=0
  if [ -z "${IMAGES:-}" ] && fetch_update; then CHECK_AVAILABLE=1; fi
  if [ "$WRITE_STATUS" = 1 ]; then
    status_set current="$CUR_VERSION" latest="$NEW_VERSION" available=$CHECK_AVAILABLE checked_at="$(now_iso)"
    status_flush
    changelog_write
  fi
}

# ---------------------------------------------------------------- --agent
# Band holatni yozadi, so'ng so'rovni o'chiradi. Tartib muhim: aksincha bo'lsa oraliqda
# API «request yo'q, state=idle» ko'rib yangi so'rov qabul qiladi.
claim_request() {
  status_flush
  rm -f "$REQ/request"
}

agent_check() {
  status_set state=checking phase= error=
  claim_request
  perform_check_and_record
  status_set state=idle error=
  status_flush
}

agent_update() {
  status_set state=updating started_at="$(now_iso)" error= backup= phase=
  claim_request
  perform_check_and_record
  if [ "$CHECK_AVAILABLE" = 0 ]; then
    status_set state=idle phase= finished_at="$(now_iso)"
    status_flush
    return 0
  fi
  # H1a: ILGARI `: > "$UPD/update.log"` — symlink bo'lsa NISHONNI bo'shatardi.
  # `mktemp+mv` — `mv` yo'l nomining O'ZINI almashtiradi (symlink bo'lsa ham),
  # nishonga HECH QACHON tegmaydi (status_flush/changelog_write bilan BIR XIL
  # allaqachon xavfsiz qolip).
  local log_reset_tmp
  log_reset_tmp=$(mktemp "$UPD/.update_log.XXXXXX")
  mv -f "$log_reset_tmp" "$UPD/update.log"
  AGENT_LOG_ACTIVE=1
  log "yangilash boshlandi: $CUR_VERSION → $NEW_VERSION"
  status_set phase=backup
  status_flush
  ERRCODE=backup_failed
  backup_db
  status_set phase=code backup="$(basename "$BACKUP")"
  status_flush
  ERRCODE=git_dirty
  git_src merge -q --ff-only '@{u}' || die "git yangilanmadi: $SRC da qo'lda o'zgartirilgan fayllar bor (git -C $SRC status)"
  status_set phase=install
  status_flush
  ERRCODE=install_failed
  run_install
  status_set state=done phase= error= finished_at="$(now_iso)" current="$NEW_VERSION"
  status_flush
  history_append "$CUR_VERSION" "$NEW_VERSION" ok
  log "yangilandi: $(cat "$DEST/VERSION" 2>/dev/null || echo "$NEW_VERSION")"
}

agent_main() {
  upd_usable || { log "status papkasi mavjud emas yoki yozib bo'lmaydi: $UPD"; return 0; }
  status_load
  status_fix_interrupted
  [ -f "$REQ/request" ] || { log "so'rov yo'q"; return 0; }
  local req
  req=$(cat "$REQ/request" 2>/dev/null)
  WRITE_STATUS=1
  case "$req" in
    check) agent_check ;;
    update) agent_update ;;
    *)
      status_set state=failed error=bad_request finished_at="$(now_iso)"
      claim_request
      history_append "${STATUS[current]}" "${STATUS[latest]}" "failed:bad_request"
      ;;
  esac
}

main() {
  parse_args "$@"
  acquire_lock
  [ "$(id -u)" = 0 ] || [ -n "${INNOVA_DEST:-}" ] || die "root huquqi kerak"
  if [ "$AGENT" = 1 ]; then
    agent_main
    return 0
  fi

  if [ "$CHECK" = 1 ] && upd_usable; then
    status_load
    status_fix_interrupted
    WRITE_STATUS=1
  fi
  perform_check_and_record
  local available=$CHECK_AVAILABLE

  if [ "$CHECK" = 1 ]; then
    if [ "$WRITE_STATUS" = 1 ]; then status_set state=idle error=; status_flush; fi
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
