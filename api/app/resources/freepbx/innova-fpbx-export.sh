#!/usr/bin/env bash
# Innova PBX — FreePBX eksport skripti (format INNOVA-FPBX-EXPORT/1).
# FreePBX serverda root sifatida ishga tushiring:   bash innova-fpbx-export.sh [chiqish_papkasi]
# Skript FAQAT O'QIYDI: FreePBX bazasi, fayllari va Asterisk holatiga hech narsa yozmaydi.
# Natija: fpbx-export-<host>-<YYYYmmdd-HHMMSS>.tar.gz — uni Innova panelidagi «Ko'chirish» bo'limiga yuklang.
# Ixtiyoriy: INNOVA_WITH_VM_MESSAGES=1 — ovozli pochta xabarlarini ham qo'shish (sukut: faqat salomlashuvlar).
set -euo pipefail
umask 077

die() { echo "XATO: $*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || die "root sifatida ishga tushiring"
command -v mysql >/dev/null || die "mysql klienti topilmadi"
command -v tar >/dev/null || die "tar topilmadi"

OUT_DIR="${1:-$PWD}"
HOST="$(hostname -s 2>/dev/null || echo freepbx)"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
NAME="fpbx-export-${HOST}-${STAMP}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
B="$WORK/$NAME"
mkdir -p "$B/conf" "$B/files" "$B/astdb"

# --- Baza ulanish ma'lumotlari: /etc/freepbx.conf (PHP) yoki /etc/amportal.conf
conf_val() {  # $1 = kalit (AMPDBUSER ...)
  local v=""
  if [ -r /etc/freepbx.conf ]; then
    v="$(grep -E "\[['\"]$1['\"]\]" /etc/freepbx.conf | head -1 | sed -E "s/.*=[[:space:]]*['\"]([^'\"]*)['\"].*/\1/")"
  fi
  if [ -z "$v" ] && [ -r /etc/amportal.conf ]; then
    v="$(grep -E "^$1=" /etc/amportal.conf | tail -1 | cut -d= -f2-)"
  fi
  printf '%s' "$v"
}
DB_USER="$(conf_val AMPDBUSER)"; DB_PASS="$(conf_val AMPDBPASS)"
DB_HOST="$(conf_val AMPDBHOST)"; DB_NAME="$(conf_val AMPDBNAME)"
DB_NAME="${DB_NAME:-asterisk}"; DB_HOST="${DB_HOST:-localhost}"
MYCNF="$WORK/my.cnf"
{ echo "[client]"; [ -n "$DB_USER" ] && echo "user=$DB_USER"; [ -n "$DB_PASS" ] && echo "password=$DB_PASS"; echo "host=$DB_HOST"; } > "$MYCNF"
MYSQL=(mysql --defaults-extra-file="$MYCNF" -N -B)
"${MYSQL[@]}" -e "SELECT 1" "$DB_NAME" >/dev/null 2>&1 || die "FreePBX bazasiga ulanib bo'lmadi ($DB_HOST/$DB_NAME)"

setting() {  # freepbx_settings jadvalidan yo'l (yo'q bo'lsa sukut)
  local v
  v="$("${MYSQL[@]}" -e "SELECT value FROM freepbx_settings WHERE keyword='$1'" "$DB_NAME" 2>/dev/null | head -1 || true)"
  printf '%s' "${v:-$2}"
}
VARLIB="$(setting ASTVARLIBDIR /var/lib/asterisk)"
SPOOL="$(setting ASTSPOOLDIR /var/spool/asterisk)"
ETC="$(setting ASTETCDIR /etc/asterisk)"
MOHDIR="$(setting MOHDIR moh)"

# --- Baza: har jadval alohida TSV (`mysql -B`: sarlavha qatori, NULL -> `NULL`, \t \n \\ escape).
# Panel administratorlari parollari ko'chirilmaydi (Innova'da o'z foydalanuvchilari bor).
IGNORED="ampusers userman_users userman_groups"
mkdir -p "$B/tables"
"${MYSQL[@]}" -e "SHOW TABLES" "$DB_NAME" > "$WORK/tables.lst"
while IFS= read -r t; do
  case " $IGNORED " in *" $t "*) continue ;; esac
  mysql --defaults-extra-file="$MYCNF" -B --quick -e "SELECT * FROM \`$t\`" "$DB_NAME" > "$B/tables/$t.tsv"
done < "$WORK/tables.lst"

# --- AstDB (DND, yo'naltirish, qora ro'yxat, Follow Me ...)
if command -v asterisk >/dev/null && asterisk -rx "core show version" >/dev/null 2>&1; then
  asterisk -rx "database show" > "$B/astdb/astdb.txt" 2>/dev/null || true
fi
[ -r "$VARLIB/astdb.sqlite3" ] && cp -p "$VARLIB/astdb.sqlite3" "$B/astdb/astdb.sqlite3" || true

# --- Konfiguratsiya fayllari (faqat o'qish va hisobot uchun)
for f in voicemail.conf; do [ -r "$ETC/$f" ] && cp -p "$ETC/$f" "$B/conf/" || true; done
for f in "$ETC"/*_custom.conf "$ETC"/*_custom_post.conf "$ETC"/extensions_override_freepbx.conf; do
  [ -r "$f" ] && cp -p "$f" "$B/conf/" || true
done

# --- Audio fayllar: tizim yozuvlari (sounds/*/custom), MOH, ovozli pochta salomlashuvlari
copy_tree() {  # $1 manba, $2 nishon (files/ ichida)
  [ -d "$1" ] || return 0
  mkdir -p "$B/files/$2"
  (cd "$1" && tar cf - .) | (cd "$B/files/$2" && tar xf -)
}
copy_tree "$VARLIB/sounds/custom" "sounds/custom"
for d in "$VARLIB"/sounds/*/custom; do
  [ -d "$d" ] || continue
  lang="$(basename "$(dirname "$d")")"
  copy_tree "$d" "sounds/$lang/custom"
done
case "$MOHDIR" in /*) copy_tree "$MOHDIR" "moh" ;; *) copy_tree "$VARLIB/$MOHDIR" "moh" ;; esac
if [ -d "$SPOOL/voicemail" ]; then
  if [ "${INNOVA_WITH_VM_MESSAGES:-0}" = "1" ]; then
    copy_tree "$SPOOL/voicemail" "voicemail"
  else
    (cd "$SPOOL/voicemail" && find . -maxdepth 3 -type f \( -name 'greet.*' -o -name 'unavail.*' -o -name 'busy.*' -o -name 'temp.*' -o -name 'busy*.*' \) -print0 \
      | tar cf - --null -T - 2>/dev/null) | (mkdir -p "$B/files/voicemail" && cd "$B/files/voicemail" && tar xf -) || true
  fi
fi

# --- meta.json
json_str() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | tr -d '\n\r'; }
FPBX_VER="$("${MYSQL[@]}" -e "SELECT value FROM admin WHERE variable='version'" "$DB_NAME" 2>/dev/null | head -1 || true)"
AST_VER="$( (asterisk -V 2>/dev/null || true) | head -1)"
DB_VER="$("${MYSQL[@]}" -e "SELECT VERSION()" 2>/dev/null | head -1 || true)"
TABLES="$(sed -e 's/.*/"&"/' "$WORK/tables.lst" | paste -sd, -)"
cat > "$B/meta.json" <<EOF
{"format": "INNOVA-FPBX-EXPORT/1", "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "host": "$(json_str "$HOST")",
 "freepbx_version": "$(json_str "$FPBX_VER")", "asterisk_version": "$(json_str "$AST_VER")", "db_version": "$(json_str "$DB_VER")",
 "db_name": "$(json_str "$DB_NAME")", "ignored_tables": ["ampusers", "userman_users", "userman_groups"],
 "vm_messages": $([ "${INNOVA_WITH_VM_MESSAGES:-0}" = "1" ] && echo true || echo false), "tables": [$TABLES]}
EOF

mkdir -p "$OUT_DIR"
tar czf "$OUT_DIR/$NAME.tar.gz" -C "$WORK" "$NAME"
echo "Tayyor: $OUT_DIR/$NAME.tar.gz ($(du -h "$OUT_DIR/$NAME.tar.gz" | cut -f1))"
