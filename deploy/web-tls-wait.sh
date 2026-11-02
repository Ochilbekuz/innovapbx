#!/bin/sh
# 1.0.4 — `/docker-entrypoint.d/` (nginx:alpine, nginx ishga tushishdan OLDIN bajariladi).
# Haqiqiy SAN (hostname + server IP'lari) bilan sertifikatni `api` yaratadi
# (app/services/web_tls_cert.py, umumiy `certs` hajmi — bu konteynerda FAQAT o'qish).
# nginx o'qiydigan nusxa konteyner ichidagi `/etc/nginx/tls/` da: `api` ulgurmasa ham
# u yerda zaxira o'z-imzoli sertifikat yaratiladi — aks holda `ssl_certificate` fayli
# yo'qligidan nginx BUTUNLAY (80 ham) ishga tushmay qolardi.
set -u

SRC=/etc/innova/certs
DST=/etc/nginx/tls
TRIES=30

mkdir -p "$DST"
i=0
while [ ! -s "$SRC/web.crt" ] || [ ! -s "$SRC/web.key" ]; do
  i=$((i + 1))
  [ "$i" -ge "$TRIES" ] && break
  sleep 1
done

if [ -s "$SRC/web.crt" ] && [ -s "$SRC/web.key" ] && cp "$SRC/web.crt" "$SRC/web.key" "$DST/"; then
  :
else
  echo "[innova-tls] ogohlantirish: api sertifikat yozmadi, vaqtinchalik zaxira yaratilmoqda" >&2
  openssl req -x509 -nodes -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 \
    -days 3650 -subj "/CN=innova-pbx" -keyout "$DST/web.key" -out "$DST/web.crt" 2>/dev/null
fi
chmod 600 "$DST/web.key"
chmod 644 "$DST/web.crt"
