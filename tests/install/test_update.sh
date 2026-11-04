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
export INNOVA_UPDATE_LOCK="$T/lock.lock" # /run yozib bo'lmasligi mumkin — testlar o'z qulfidan foydalanadi
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

# ---------------------------------------------------------------- --agent (status papka, m11-update-contract.md)
AT=$T/agent
mkdir -p "$AT"

git init -q -b main "$AT/work"
cat > "$AT/work/install.sh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "$INSTALL_LOG"
[ -z "${INSTALL_FAIL:-}" ] || exit 7
EOF
chmod +x "$AT/work/install.sh"
echo 2.0.0 > "$AT/work/VERSION"
printf '## 2.0.0\n- boshlangich\n' > "$AT/work/CHANGELOG.md"
git -C "$AT/work" add -A && git -C "$AT/work" commit -qm v2.0.0
git clone -q --bare "$AT/work" "$AT/origin.git"
git clone -q "$AT/origin.git" "$AT/src"

ADEST=$AT/opt
mkdir -p "$ADEST/deploy"
echo 2.0.0 > "$ADEST/VERSION"
echo "$AT/src" > "$ADEST/SOURCE"
printf 'POSTGRES_USER=innova\nPOSTGRES_DB=innova\nWEB_HOST_PORT=8080\n' > "$ADEST/deploy/.env"
AUPD=$AT/update
mkdir -p "$AUPD"
export INNOVA_DEST=$ADEST INNOVA_UPDATE_DIR=$AUPD INSTALL_LOG=$AT/install.log DOCKER_LOG=$AT/docker.log
: > "$INSTALL_LOG"; : > "$DOCKER_LOG"

arun() { bash "$UPDATE" --agent 2>&1; }
apublish() { # versiya changelog-qatori
  echo "$1" > "$AT/work/VERSION"
  { printf '## %s\n- %s\n\n' "$1" "$2"; cat "$AT/work/CHANGELOG.md"; } > "$AT/work/CHANGELOG.md.new"
  mv "$AT/work/CHANGELOG.md.new" "$AT/work/CHANGELOG.md"
  git -C "$AT/work" add -A && git -C "$AT/work" commit -qam "v$1" && git -C "$AT/work" push -q "$AT/origin.git" main
}
status_val() { sed -n "s/^$1=//p" "$AUPD/status" 2>/dev/null; }
no_ansi() { ! grep -qP '\x1b' "$1"; }

# a1) so'rov yo'q, status ham yo'q — hech narsa yozilmaydi
out=$(arun); rc=$?
ok eq "$rc" 0
ok not test -e "$AUPD/status"

# a2) check — yangilanish bor
apublish 2.0.1 "ikkinchi versiya"
echo check > "$AUPD/request"
out=$(arun); rc=$?
ok eq "$rc" 0
ok not test -e "$AUPD/request"
ok eq "$(status_val state)" idle
ok eq "$(status_val current)" 2.0.0
ok eq "$(status_val latest)" 2.0.1
ok eq "$(status_val available)" 1
ok contains "$(cat "$AUPD/changelog.md" 2>/dev/null)" "## 2.0.1"

# a3) update — mavjud yangilanishni qo'llaydi
echo update > "$AUPD/request"
out=$(arun); rc=$?
ok eq "$rc" 0
ok not test -e "$AUPD/request"
# shellcheck disable=SC1010 # "done" — status qiymati, bash kalit so'zi emas
ok eq "$(status_val state)" done
ok eq "$(status_val current)" 2.0.1
ok eq "$(cat "$AT/src/VERSION")" 2.0.1
ok eq "$(cat "$INSTALL_LOG")" "--web-port 8080"
backup_name=$(status_val backup)
ok test -n "$backup_name"
ok test -f "$ADEST/backups/$backup_name"
ok contains "$(cat "$AUPD/update.log")" "yangilash boshlandi"
ok no_ansi "$AUPD/update.log"
ok contains "$(cat "$AUPD/history")" $'\t2.0.0\t2.0.1\tok'
echo 2.0.1 > "$ADEST/VERSION" # haqiqiy install.sh DEST/VERSION'ni yozardi — soxtasi yozmaydi

# a4) check — yangilanish yo'q
echo check > "$AUPD/request"
out=$(arun); rc=$?
ok eq "$rc" 0
ok eq "$(status_val available)" 0
ok eq "$(status_val current)" 2.0.1
ok eq "$(status_val latest)" 2.0.1

# a5) update — yangilanish yo'q bo'lsa install.sh chaqirilmaydi
: > "$INSTALL_LOG"
echo update > "$AUPD/request"
out=$(arun); rc=$?
ok eq "$rc" 0
ok not test -e "$AUPD/request"
ok eq "$(status_val state)" idle
ok eq "$(wc -c < "$INSTALL_LOG" | tr -d ' ')" 0

# a6) git_dirty — manba qo'lda o'zgartirilgan, zaxira olingan, install.sh chaqirilmaydi
apublish 2.0.2 "uchinchi versiya"
echo local > "$AT/src/VERSION"
: > "$INSTALL_LOG"
echo update > "$AUPD/request"
out=$(arun); rc=$?
ok not eq "$rc" 0
ok not test -e "$AUPD/request"
ok eq "$(status_val state)" failed
ok eq "$(status_val error)" git_dirty
backup_name=$(status_val backup)
ok test -n "$backup_name"
ok test -f "$ADEST/backups/$backup_name"
ok eq "$(wc -c < "$INSTALL_LOG" | tr -d ' ')" 0
git -C "$AT/src" checkout -q -- VERSION

# a7) install_failed — kod birlashadi, install.sh yiqiladi, orqaga qaytarish yo'riqnomasi logga yoziladi
apublish 2.0.3 "to'rtinchi versiya"
: > "$INSTALL_LOG"
echo update > "$AUPD/request"
out=$(INSTALL_FAIL=1 arun); rc=$?
ok not eq "$rc" 0
ok not test -e "$AUPD/request"
ok eq "$(status_val state)" failed
ok eq "$(status_val error)" install_failed
ok eq "$(cat "$AT/src/VERSION")" 2.0.3
ok contains "$(cat "$AUPD/update.log")" "checkout"
ok no_ansi "$AUPD/update.log"

# a8) bad_request — noma'lum so'rov matni
echo chiqindi > "$AUPD/request"
out=$(arun); rc=$?
ok eq "$rc" 0
ok not test -e "$AUPD/request"
ok eq "$(status_val state)" failed
ok eq "$(status_val error)" bad_request

# a9) interrupted — avvalgi yugurish o'lik holatda qolgan (lock yo'q, so'rov yo'q)
cat > "$AUPD/status" <<'EOF'
state=updating
phase=install
current=2.0.1
latest=2.0.3
available=1
checked_at=
started_at=
finished_at=
error=
backup=
EOF
rm -f "$AUPD/request"
out=$(arun); rc=$?
ok eq "$rc" 0
ok eq "$(status_val state)" failed
ok eq "$(status_val error)" interrupted
ok contains "$(cat "$AUPD/history")" $'\t2.0.1\t2.0.3\tfailed:interrupted'

# a10) busy-lock — agent qulf bo'shashini KUTADI va so'rovni bajaradi (chiqib ketsa
# request qoladi → systemd path qayta-qayta ishga tushirib start-limit'ga uriladi)
flock -n "$T/lock.lock" sleep 1 &
BGPID=$!
for _ in $(seq 1 50); do flock -n "$T/lock.lock" -c true 2>/dev/null || break; sleep 0.05; done
echo check > "$AUPD/request"
out=$(arun); rc=$?
ok eq "$rc" 0
ok not test -e "$AUPD/request"
ok eq "$(status_val state)" idle
wait "$BGPID" 2>/dev/null

# a11) CLI rejimi qulf band bo'lsa kutmaydi — darhol xato
flock -n "$T/lock.lock" sleep 3 &
BGPID=$!
for _ in $(seq 1 50); do flock -n "$T/lock.lock" -c true 2>/dev/null || break; sleep 0.05; done
out=$(INNOVA_DEST=$DEST bash "$UPDATE" --check 2>&1); rc=$?
ok eq "$rc" 1
ok contains "$out" "band"
kill "$BGPID" 2>/dev/null; wait "$BGPID" 2>/dev/null

# a12) so'rov status BAND yozilgandan KEYIN o'chiriladi — oraliqda API «request yo'q,
# state=idle» ko'rib ikkinchi so'rovni qabul qilmasin (u update'dan keyin done'ni bosib ketardi)
mkdir -p "$AT/rmspy"
cat > "$AT/rmspy/rm" <<EOF
#!/bin/bash
for a in "\$@"; do
  [ "\$a" = "$AUPD/request" ] && sed -n 's/^state=//p' "$AUPD/status" >> "$AT/rm-seen"
done
exec /bin/rm "\$@"
EOF
chmod +x "$AT/rmspy/rm"
for word in check update; do
  : > "$AT/rm-seen"
  echo "$word" > "$AUPD/request"
  PATH="$AT/rmspy:$PATH" arun >/dev/null; rc=$?
  ok eq "$rc" 0
  ok not test -e "$AUPD/request"
  case $word in check) want=checking ;; update) want=updating ;; esac
  ok eq "$(head -n1 "$AT/rm-seen")" "$want"
done

echo "innova-update: $PASSES o'tdi, $FAILS xato"
[ "$FAILS" = 0 ]
