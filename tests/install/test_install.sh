#!/usr/bin/env bash
# install.sh sof funksiyalari testi: `bash tests/install/test_install.sh`
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=SCRIPTDIR/../../install.sh
. "$HERE/../../install.sh"
set +e

FAILS=0 PASSES=0
ok() { if "$@"; then PASSES=$((PASSES + 1)); else echo "FAIL: $*"; FAILS=$((FAILS + 1)); fi; }
not() { ! "$@"; }
eq() { [ "$1" = "$2" ] || { echo "  kutilgan [$2], olindi [$1]"; return 1; }; }

# version_ge: compose versiyasi formatlari
ok version_ge 2.24 2.24
ok version_ge 2.40.3+ds1-0ubuntu1~24.04.1 2.24
ok version_ge v2.27.0 2.24
ok version_ge 2.26.1-4 2.24
ok not version_ge 2.20.2 2.24
ok not version_ge 1.29.2 2.24
ok not version_ge 0 2.24

# docker_source_for: qo'llanadigan tizimlar
ok eq "$(docker_source_for debian trixie)" distro
ok eq "$(docker_source_for debian bookworm)" docker-repo
ok eq "$(docker_source_for ubuntu noble)" docker-repo
ok eq "$(docker_source_for ubuntu jammy)" docker-repo
ok eq "$(docker_source_for debian bullseye)" ""
ok eq "$(docker_source_for rocky 9)" ""

# busy_ports: `ss -Hlntu` chiqishi
SS='udp   UNCONN 0      0            0.0.0.0:5060      0.0.0.0:*
tcp   LISTEN 0      511          0.0.0.0:80        0.0.0.0:*
tcp   LISTEN 0      511             [::]:80           [::]:*
tcp   LISTEN 0      4096       127.0.0.1:5432      0.0.0.0:*
tcp   LISTEN 0      128          0.0.0.0:22        0.0.0.0:*
tcp   LISTEN 0      128          0.0.0.0:8080      0.0.0.0:*'
WANT="tcp:80 tcp:5060 udp:5060 tcp:5432"
ok eq "$(echo "$SS" | busy_ports "$WANT" | tr '\n' ' ')" "tcp:5432 tcp:80 udp:5060 "
ok eq "$(echo "$SS" | busy_ports "tcp:8 tcp:808")" ""          # 8080 qisman mos kelmasin
ok eq "$(printf '' | busy_ports "$WANT")" ""

# parse_args: to'g'ri va noto'g'ri qiymatlar (die -> subshell exit 1)
fails() { ! (parse_args "$@" >/dev/null 2>&1); }
args() { (parse_args "$@" >/dev/null 2>&1; echo "$WEB_PORT|$VERSION|$IMAGES"); }
ok eq "$(args --version 1.2 --web-port 8080)" "8080|1.2|"
ok eq "$(args --version x)" "80|x|"
ok fails --web-port 0
ok fails --web-port 70000
ok fails --web-port abc
ok fails --version "a b"
ok fails --images /yoq/fayl
ok fails --nimadir
# --images: versiya fayldagi tegdan; mos kelmasa yoki obraz yo'q bo'lsa — xato
TMPD=$(mktemp -d)
printf '[{"RepoTags":["postgres:16"]},{"RepoTags":["innova-pbx/api:2026.11.02"]}]' > "$TMPD/manifest.json"
tar -C "$TMPD" -cf - manifest.json | zstd -q -o "$TMPD/img.tar.zst"
ok eq "$(args --images "$TMPD/img.tar.zst")" "80|2026.11.02|$TMPD/img.tar.zst"
ok eq "$(args --version 2026.11.02 --images "$TMPD/img.tar.zst")" "80|2026.11.02|$TMPD/img.tar.zst"
ok fails --version 9.9 --images "$TMPD/img.tar.zst"
printf '[{"RepoTags":["postgres:16"]}]' > "$TMPD/manifest.json"
tar -C "$TMPD" -cf - manifest.json | zstd -q -f -o "$TMPD/bad.tar.zst"
ok fails --images "$TMPD/bad.tar.zst"
echo x > "$TMPD/junk"
ok fails --images "$TMPD/junk"
rm -rf "$TMPD"
# shellcheck disable=SC2016
ok eval '[[ $(args) =~ ^80\|[0-9]{4}\.[0-9]{2}\.[0-9]{2} ]]'   # sukut versiya: sana(-commit)

# detect_os: os-release dagi VERSION bizning VERSION'ni bosib ketmasin (VM'da topilgan xato)
TMPD=$(mktemp -d)
printf 'PRETTY_NAME="Debian 13"\nID=debian\nVERSION="13 (trixie)"\nVERSION_CODENAME=trixie\n' > "$TMPD/os"
detected() { (VERSION=2026.11.02; OS_RELEASE=$TMPD/os detect_os 2>&1; echo "$OS_ID|$OS_CODENAME|$DOCKER_SOURCE|$VERSION"); }
ok eq "$(detected)" "debian|trixie|distro|2026.11.02"
printf 'ID=rocky\nVERSION="9.4"\nPRETTY_NAME="Rocky Linux 9"\n' > "$TMPD/os"
contains() { [[ $1 == *"$2"* ]]; }
ok contains "$(detected)" "(bu: Rocky Linux 9)"
ok contains "$(detected)" "Debian 12/13, Ubuntu 22.04/24.04"
rm -rf "$TMPD"

echo "install.sh: $PASSES o'tdi, $FAILS xato"
[ "$FAILS" = 0 ]
