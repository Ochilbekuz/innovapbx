#!/usr/bin/env bash
# Innova PBX o'rnatish ISO'si — Debian 13 (trixie) netinst + preseed + oflayn Docker obrazlari.
#
#   iso/build-iso.sh --src debian-13.7.0-amd64-netinst.iso [--out innova-pbx-<ver>.iso] [--version X]
#                    [--skip-build] [--test-password-hash '<crypt>']
#
# Talablar (build hostida): docker (compose v2), xorriso, zstd, sha256sum.
# --test-password-hash FAQAT sinov uchun (QEMU'da to'liq avtomatik o'rnatish). Ishlab chiqarish
# ISO'sida parol yo'q — o'rnatuvchi uni so'raydi.
set -euo pipefail

SRC_SHA256=a7ef94ac2fb9a7fec454552abd629b7cc9d5155c886165a45649f5ce6167e355  # debian-13.7.0-amd64-netinst.iso
ROOT=$(cd "$(dirname "$0")/.." && pwd)
ISO_DIR=$ROOT/iso
SRC="" OUT="" TMP="" VERSION="" SKIP_BUILD=0 TEST_HASH=""
# trixie: `docker` CLI alohida `docker-cli` paketida (docker.io uni faqat Recommends qiladi).
DEB_PACKAGES="docker.io docker-cli docker-compose containerd runc iptables apparmor nftables zstd curl ca-certificates dbus"

die() { echo "xato: $*" >&2; exit 1; }
step() { echo "==> $*"; }

parse_args() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --src) SRC=$2; shift 2 ;;
      --out) OUT=$2; shift 2 ;;
      --version) VERSION=$2; shift 2 ;;
      --skip-build) SKIP_BUILD=1; shift ;;
      --test-password-hash) TEST_HASH=$2; shift 2 ;;
      -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
      *) die "noma'lum parametr: $1" ;;
    esac
  done
  [ -f "$SRC" ] || die "--src Debian netinst ISO topilmadi"
  VERSION=${VERSION:-$(date +%Y.%m.%d)}
  OUT=${OUT:-$PWD/innova-pbx-$VERSION-amd64.iso}
}

verify_source() {
  step "manba ISO sha256"
  [ -n "${INNOVA_SKIP_SHA:-}" ] && return 0
  echo "$SRC_SHA256  $SRC" | sha256sum -c --quiet - || die "sha256 mos emas (boshqa Debian versiyasi? INNOVA_SKIP_SHA=1)"
}

build_images() {
  local stage=$1
  if [ "$SKIP_BUILD" = 0 ]; then
    step "obrazlar yig'ilmoqda"
    docker compose -f "$ROOT/deploy/docker-compose.yml" build migrate api asterisk web
  fi
  step "teglar: innova-pbx/*:$VERSION"
  local svc
  for svc in api asterisk web; do
    docker tag "innova-m0-$svc:latest" "innova-pbx/$svc:$VERSION"
  done
  docker image inspect postgres:16 >/dev/null 2>&1 || docker pull postgres:16
  step "docker save | zstd"
  docker save "innova-pbx/api:$VERSION" "innova-pbx/asterisk:$VERSION" "innova-pbx/web:$VERSION" postgres:16 \
    | zstd -T0 -10 -q -o "$stage/innova/images.tar.zst"
}

download_debs() {
  local stage=$1
  step "Debian paketlari (oflayn ombor)"
  mkdir -p "$stage/innova/debs"
  # Bo'sh dpkg holati — apt butun bog'liqlik zanjirini yuklaydi (minimal tizimda nima borligidan qat'i nazar).
  docker run --rm -e DEBIAN_FRONTEND=noninteractive -v "$stage/innova/debs:/out" debian:trixie sh -euc "
    apt-get -qq update
    apt-get -qq install -y --no-install-recommends dpkg-dev >/dev/null
    : > /tmp/status
    apt-get -qq -o Dir::State::status=/tmp/status -o Dir::Cache::archives=/out \
      install -y --download-only --no-install-recommends $DEB_PACKAGES >/dev/null
    rm -f /out/lock; rm -rf /out/partial
    cd /out && dpkg-scanpackages -m . /dev/null 2>/dev/null > Packages && gzip -9k Packages
    chown -R $(id -u):$(id -g) /out"
  echo "$DEB_PACKAGES" > "$stage/innova/packages.txt"  # install-target.sh shu ro'yxatni o'rnatadi
  ls "$stage/innova/debs"/*.deb | wc -l | sed 's/^/    deb: /'
}

stage_files() {
  local stage=$1
  step "fayllar"
  mkdir -p "$stage/innova/deploy" "$stage/innova/files"
  cp "$ROOT/deploy/docker-compose.yml" "$ROOT/deploy/docker-compose.appliance.yml" "$stage/innova/deploy/"
  cp "$ISO_DIR"/files/* "$stage/innova/files/"
  echo "$VERSION" > "$stage/innova/VERSION"
  local hash_line="# (parol o'rnatishda so'raladi)"
  [ -n "$TEST_HASH" ] && hash_line="d-i passwd/user-password-crypted password $TEST_HASH"
  awk -v l="$hash_line" '$0 == "#INNOVA_TEST_PASSWORD#" { print l; next } { print }' \
    "$ISO_DIR/preseed.cfg" > "$stage/preseed.cfg"
}

patch_boot_menus() {
  local stage=$1 work=$2
  step "yuklash menyulari"
  local args="auto=true priority=critical preseed/file=/cdrom/preseed.cfg locale=en_US.UTF-8 keymap=us"
  args="$args hostname=innova-pbx domain=local"
  osirrox_extract "$work" /isolinux/menu.cfg /boot/grub/grub.cfg
  mkdir -p "$stage/isolinux" "$stage/boot/grub"
  cat > "$stage/isolinux/innova.cfg" <<EOF
label innova
	menu label ^Innova PBX - avtomatik o'rnatish (disk tozalanadi)
	menu default
	kernel /install.amd/vmlinuz
	append vga=788 initrd=/install.amd/initrd.gz $args --- quiet
EOF
  # menu.cfg oxiridagi spkgtk.cfg 30 s da nutq sintezli o'rnatishni ishga tushiradi — undan KEYIN
  # o'z timeout/ontimeout'imiz (oxirgi direktiva amal qiladi).
  { sed 's/^include gtk.cfg$/include innova.cfg\ninclude gtk.cfg/' "$work/menu.cfg"
    echo "timeout 100"
    echo "ontimeout /install.amd/vmlinuz vga=788 initrd=/install.amd/initrd.gz $args --- quiet"
    echo "menu autoboot Innova PBX avtomatik o'rnatish # soniyadan keyin boshlanadi..."
  } > "$stage/isolinux/menu.cfg"
  awk -v a="$args" '
    /^set theme=/ && !done {
      print; print "set default=0"; print "set timeout=10"
      print "menuentry \"Innova PBX - avtomatik o'\''rnatish (disk tozalanadi)\" {"
      print "    set background_color=black"
      print "    linux    /install.amd/vmlinuz vga=788 " a " --- quiet"
      print "    initrd   /install.amd/initrd.gz"
      print "}"; done=1; next }
    { print }' "$work/grub.cfg" > "$stage/boot/grub/grub.cfg"
  grep -q "^include innova.cfg" "$stage/isolinux/menu.cfg" || die "menu.cfg tuzilishi o'zgargan"
  grep -q "Innova PBX" "$stage/boot/grub/grub.cfg" || die "grub.cfg tuzilishi o'zgargan"
}

osirrox_extract() {
  local dir=$1; shift
  local f
  for f in "$@"; do
    xorriso -osirrox on -indev "$SRC" -extract "$f" "$dir/$(basename "$f")" >/dev/null 2>&1
    chmod u+w "$dir/$(basename "$f")"
  done
}

update_md5() {
  local stage=$1 work=$2
  step "md5sum.txt"
  osirrox_extract "$work" /md5sum.txt
  local changed
  changed=$(cd "$stage" && find . -type f | sort)
  {
    grep -v -F -f <(echo "$changed" | sed 's|^\./||') "$work/md5sum.txt" || true
    (cd "$stage" && echo "$changed" | xargs md5sum)
  } > "$stage/md5sum.txt"
}

repack() {
  local stage=$1
  step "ISO yozilmoqda: $OUT"
  rm -f "$OUT"
  xorriso -indev "$SRC" -outdev "$OUT" -volid "INNOVA_PBX" -boot_image any replay \
    -map "$stage" / -chmod_r a+r,a-w / -- -commit >/dev/null 2>&1 || die "xorriso"
  sha256sum "$OUT" | tee "$OUT.sha256"
  du -h "$OUT"
}

main() {
  parse_args "$@"
  verify_source
  TMP=$(mktemp -d)
  trap 'rm -rf "$TMP"' EXIT
  mkdir -p "$TMP/stage/innova" "$TMP/work"
  build_images "$TMP/stage"
  download_debs "$TMP/stage"
  stage_files "$TMP/stage"
  patch_boot_menus "$TMP/stage" "$TMP/work"
  update_md5 "$TMP/stage" "$TMP/work"
  repack "$TMP/stage"
}

main "$@"
