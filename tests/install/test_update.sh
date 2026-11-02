#!/usr/bin/env bash
# innova-update testi (soxta git origin, soxta docker/install.sh): `bash tests/install/test_update.sh`
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
UPDATE=$HERE/../../iso/files/innova-update.sh

FAILS=0 PASSES=0
ok() { if "$@"; then PASSES=$((PASSES + 1)); else echo "FAIL: $*"; FAILS=$((FAILS + 1)); fi; }
not() { ! "$@" 2>/dev/null; }
eq() { [ "$1" = "$2" ] || { echo "  kutilgan [$2], olindi [$1]" >&2; return 1; }; }
contains() { [[ $1 == *"$2"* ]] || { echo "  [$1] ichida [$2] yo'q"; return 1; }; }

T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t

# origin (GitHub o'rnida) + o'rnatilgan klon
git init -q -b main "$T/work"
cat > "$T/work/install.sh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "$INSTALL_LOG"
[ -z "${INSTALL_FAIL:-}" ] || exit 7
EOF
chmod +x "$T/work/install.sh"
echo 1.0.0 > "$T/work/VERSION"
git -C "$T/work" add -A && git -C "$T/work" commit -qm v1.0.0
git clone -q --bare "$T/work" "$T/origin.git"
git clone -q "$T/origin.git" "$T/src"

# o'rnatilgan tizim: /opt/innova o'rnida
DEST=$T/opt
mkdir -p "$DEST/deploy"
echo 1.0.0 > "$DEST/VERSION"
echo "$T/src" > "$DEST/SOURCE"
printf 'POSTGRES_USER=innova\nPOSTGRES_DB=innova\nWEB_HOST_PORT=8080\n' > "$DEST/deploy/.env"

# soxta docker: pg_dump o'rniga SQL matn chiqaradi
mkdir -p "$T/bin"
cat > "$T/bin/docker" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "$DOCKER_LOG"
case "$*" in *pg_dump*) [ -z "${DUMP_FAIL:-}" ] || exit 3; echo "-- dump";; esac
EOF
chmod +x "$T/bin/docker"
export PATH="$T/bin:$PATH" INNOVA_DEST=$DEST INSTALL_LOG=$T/install.log DOCKER_LOG=$T/docker.log
: > "$INSTALL_LOG"

run() { bash "$UPDATE" "$@" 2>&1; }
publish() { # origin'ga yangi versiya
  echo "$1" > "$T/work/VERSION"
  git -C "$T/work" commit -qam "v$1" && git -C "$T/work" push -q "$T/origin.git" main
}

# 1) yangilanish yo'q
out=$(run --check); rc=$?
ok eq "$rc" 0
ok contains "$out" "eng so'nggi versiya: 1.0.0"

# 2) yangi versiya chiqdi — --check faqat xabar beradi, hech narsa o'zgarmaydi
publish 1.0.1
out=$(run --check); rc=$?
ok eq "$rc" 10
ok contains "$out" "1.0.0 → 1.0.1"
ok eq "$(cat "$T/src/VERSION")" 1.0.0
ok eq "$(wc -c < "$INSTALL_LOG" | tr -d ' ')" 0

# 3) yangilash: zaxira → git ff → install.sh (port saqlanadi)
out=$(run); rc=$?
ok eq "$rc" 0
ok eq "$(cat "$T/src/VERSION")" 1.0.1
ok eq "$(cat "$INSTALL_LOG")" "--web-port 8080"
ok eq "$(find "$DEST/backups" -name 'pre-update-1.0.0-*.sql.gz' | wc -l | tr -d ' ')" 1
ok eq "$(gzip -dc "$DEST/backups"/pre-update-1.0.0-*.sql.gz)" "-- dump"
ok contains "$(cat "$DOCKER_LOG")" "pg_dump -U innova innova"

# 4) ikkinchi marta — idempotent: yangilanish yo'q, install.sh chaqirilmaydi
: > "$INSTALL_LOG"
echo 1.0.1 > "$DEST/VERSION"
out=$(run); rc=$?
ok eq "$rc" 0
ok contains "$out" "eng so'nggi versiya"
ok eq "$(wc -c < "$INSTALL_LOG" | tr -d ' ')" 0

# 5) --force: yangilanish yo'q bo'lsa ham qayta o'rnatadi (masalan buzilgan o'rnatishni tuzatish)
out=$(run --force); rc=$?
ok eq "$rc" 0
ok eq "$(cat "$INSTALL_LOG")" "--web-port 8080"

# 6) zaxira olinmasa — yangilash TO'XTAYDI, kod o'zgarmaydi
publish 1.0.2
: > "$INSTALL_LOG"
out=$(DUMP_FAIL=1 run); rc=$?
ok not eq "$rc" 0
ok contains "$out" "zaxira"
ok eq "$(cat "$T/src/VERSION")" 1.0.1
ok eq "$(wc -c < "$INSTALL_LOG" | tr -d ' ')" 0
ok eq "$(find "$DEST/backups" -name '*.partial' | wc -l | tr -d ' ')" 0

# 7) install.sh yiqilsa — orqaga qaytarish yo'riqnomasi (eski commit + zaxira fayli) ko'rsatiladi
old=$(git -C "$T/src" rev-parse --short HEAD)
out=$(INSTALL_FAIL=1 run); rc=$?
ok not eq "$rc" 0
ok contains "$out" "git -C $T/src checkout $old"
ok contains "$out" "pre-update-1.0.1-"

# 8) yangilanadigan fayl qo'lda o'zgartirilgan — git ff rad etadi, install.sh chaqirilmaydi
publish 1.0.3
echo local > "$T/src/VERSION"
: > "$INSTALL_LOG"
out=$(run); rc=$?
ok not eq "$rc" 0
ok eq "$(wc -c < "$INSTALL_LOG" | tr -d ' ')" 0
ok contains "$out" "git -C $T/src status"
git -C "$T/src" checkout -q -- VERSION

# 9) --images: oflayn yangilash — git'ga tegmaydi, faylni install.sh ga uzatadi
echo img > "$T/img.tar.zst"
: > "$INSTALL_LOG"
out=$(run --images "$T/img.tar.zst"); rc=$?
ok eq "$rc" 0
ok eq "$(cat "$INSTALL_LOG")" "--web-port 8080 --images $T/img.tar.zst"

# 10) faqat oxirgi 5 ta zaxira saqlanadi
for i in 1 2 3 4 5 6 7; do touch -d "2026-01-0$i" "$DEST/backups/pre-update-0.0.$i-x.sql.gz"; done
run --force >/dev/null
ok eq "$(find "$DEST/backups" -type f | wc -l | tr -d ' ')" 5
ok not test -e "$DEST/backups/pre-update-0.0.1-x.sql.gz"

# 11) SOURCE yo'q (ISO o'rnatish) — tushunarli xato
rm "$DEST/SOURCE"
out=$(run); rc=$?
ok not eq "$rc" 0
ok contains "$out" "git clone"

# 12) noma'lum parametr
out=$(run --foo); rc=$?
ok not eq "$rc" 0

echo "innova-update: $PASSES o'tdi, $FAILS xato"
[ "$FAILS" = 0 ]
