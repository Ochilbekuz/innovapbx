#!/bin/sh
# d-i `preseed/late_command` — o'rnatuvchi muhitida (busybox sh), /target = yangi tizim.
# Docker + lokal paketlar, Innova fayllari, firewall, first-boot servisi. Internet SHART EMAS.
set -e

SRC=/cdrom/innova
DST=/target/opt/innova
log() { echo "innova: $*"; logger -t innova "$*" 2>/dev/null || true; }

log "fayllar nusxalanmoqda"
mkdir -p "$DST/bin" "$DST/debs"
cp -a "$SRC/deploy" "$SRC/VERSION" "$DST/"
cp "$SRC/debs/"* "$DST/debs/"
cp "$SRC/images.tar.zst" "$DST/"
cp "$SRC/files/innova-start.sh" "$DST/bin/innova-start"
chmod 0755 "$DST/bin/innova-start"
chmod 0700 "$DST"

log "lokal ombordan paketlar o'rnatilmoqda"
echo "deb [trusted=yes] file:/opt/innova/debs ./" > "$DST/debs.list"
APT_LOCAL="-o Dir::Etc::sourcelist=/opt/innova/debs.list -o Dir::Etc::sourceparts=- -o APT::Get::List-Cleanup=0"
in-target sh -c "apt-get $APT_LOCAL update"
in-target sh -c "DEBIAN_FRONTEND=noninteractive apt-get $APT_LOCAL install -y --no-install-recommends $(cat "$SRC/packages.txt")"
in-target sh -c "command -v docker && command -v dockerd" >/dev/null || { log "docker CLI o'rnatilmadi"; exit 1; }
rm -rf "$DST/debs" "$DST/debs.list"
in-target apt-get clean

log "apt manbalari (keyingi yangilanishlar uchun internet ombori)"
cat > /target/etc/apt/sources.list <<'EOF'
deb http://deb.debian.org/debian trixie main contrib non-free-firmware
deb http://deb.debian.org/debian trixie-updates main contrib non-free-firmware
deb http://security.debian.org/debian-security trixie-security main contrib non-free-firmware
EOF

mkdir -p /target/etc/docker
cat > /target/etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": {"max-size": "20m", "max-file": "5"},
  "live-restore": false
}
EOF

cp "$SRC/files/nftables.conf" /target/etc/nftables.conf
mkdir -p /target/etc/innova
cat > /target/etc/innova/ports.nft <<'EOF'
# Innova PBX — netd avtomatik yaratadi, qo'lda tahrir qilinmasin.
define INNOVA_SSH_PORTS = { 22 }
EOF
cp "$SRC/files/issue" /target/etc/issue
cp "$SRC/files/innova-pbx.service" /target/etc/systemd/system/innova-pbx.service

log "paneldan yangilash agenti"
mkdir -p /target/usr/local/sbin
cp "$SRC/files/innova-update.sh" /target/usr/local/sbin/innova-update
chmod 0755 /target/usr/local/sbin/innova-update
for u in innova-update-agent.path innova-update-agent.service \
         innova-update-check.timer innova-update-check.service; do
  cp "$SRC/files/$u" "/target/etc/systemd/system/$u"
done
# Eslatma: ISO o'rnatuvida $DST/SOURCE yo'q (git klon emas) — agent "no_source" qaytaradi, bu normal.

in-target systemctl enable nftables.service docker.service ssh.service innova-pbx.service \
  innova-update-agent.path innova-update-check.timer
log "tayyor — qayta yuklangandan keyin Innova PBX birinchi ishga tushadi"
