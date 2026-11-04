#!/usr/bin/env bash
# M11 jonli isbot — paneldan yangilash (replica/m11-update-contract.md).
#
#   scripts/m11-proof.sh [--fresh]   # --fresh: avval api/web obrazlarini yig'adi
#
# Haqiqiy: dev stek API'si (konteyner), haqiqiy systemd `PathExists` unit + xizmat,
# haqiqiy `innova-update --agent`, haqiqiy pg_dump (dev baza). Soxta: GitHub o'rniga
# lokal bare origin, `install.sh` o'rniga skript (sekin ishlaydi va API+web
# konteynerlarini QAYTA ISHGA TUSHIRADI — agent bunga chidashini ko'rsatadi).
# Oxirida unitlar o'chiriladi, API asl compose bilan qayta yaratiladi.
set -uo pipefail
ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
DEPLOY_DIR="$ROOT_DIR/deploy"
LIB_DIR="$ROOT_DIR/scripts/lib"
PROJECT="innova-m0"
API_BASE="http://127.0.0.1:8710/api/v1"
PG="$PROJECT-postgres-1" AST="$PROJECT-asterisk-1"
PASS=0 FAIL=0
# shellcheck source=lib/m2a_common.sh
source "$LIB_DIR/m2a_common.sh"

P=/tmp/innova-m11-proof
UNIT=innova-m11proof-agent
ADMIN_PASSWORD=$(grep -E '^PROOF_ADMIN_PASSWORD=' "$DEPLOY_DIR/.env" | cut -d= -f2-)
OVERRIDE=$P/compose.override.yml

compose() { (cd "$DEPLOY_DIR" && docker compose -p "$PROJECT" "$@"); }

cleanup() {
  systemctl stop "$UNIT.path" "$UNIT.service" 2>/dev/null
  rm -f "/etc/systemd/system/$UNIT.path" "/etc/systemd/system/$UNIT.service"
  systemctl daemon-reload
  systemctl reset-failed "$UNIT.path" "$UNIT.service" 2>/dev/null
  flock /tmp/innova-stack.lock -c "cd '$DEPLOY_DIR' && docker compose -p '$PROJECT' up -d --no-deps api web" >/dev/null 2>&1
  rm -rf "$P"
}
trap cleanup EXIT

st() { jget "$(jbody "$(api GET /system/update)")" "$1"; }

setup_host() {
  rm -rf "$P" && mkdir -p "$P/upd/req" "$P/opt/deploy" "$P/opt/backups"
  export GIT_AUTHOR_NAME=proof GIT_AUTHOR_EMAIL=p@p GIT_COMMITTER_NAME=proof GIT_COMMITTER_EMAIL=p@p
  git init -q -b main "$P/work"
  cat > "$P/work/install.sh" <<'EOF'
#!/usr/bin/env bash
# soxta install.sh: obraz yig'ish o'rnida sekin bosqichlar + API/web qayta ishga tushadi
echo "==> obrazlar yig'ilmoqda (soxta) $*"; sleep 3
echo "==> ishga tushirilmoqda"; docker restart innova-m0-api-1 innova-m0-web-1 >/dev/null
sleep 2; cp "$(dirname "$0")/VERSION" "$INNOVA_DEST/VERSION"; echo "==> tayyor"
EOF
  chmod +x "$P/work/install.sh"
  echo 1.0.12 > "$P/work/VERSION"
  printf '# O%szgarishlar tarixi\n\n## 1.0.12 — 2026-11-03\n\n- eski\n' "'" > "$P/work/CHANGELOG.md"
  git -C "$P/work" add -A && git -C "$P/work" commit -qm 1.0.12
  git clone -q --bare "$P/work" "$P/origin.git"
  git clone -q "$P/origin.git" "$P/src"
  echo 1.0.12 > "$P/opt/VERSION"
  echo "$P/src" > "$P/opt/SOURCE"
  grep -E '^(POSTGRES_USER|POSTGRES_DB)=' "$DEPLOY_DIR/.env" > "$P/opt/deploy/.env"
  echo WEB_HOST_PORT=8711 >> "$P/opt/deploy/.env"
}

publish_release() { # versiya — origin'ga yangi versiya
  echo "$1" > "$P/work/VERSION"
  printf '# O%szgarishlar tarixi\n\n## %s — 2026-11-04\n\n- **Paneldan yangilash** (`/settings/update`)\n- <script>alert(1)</script> matn bo%slib qolsin\n\n## 1.0.12 — 2026-11-03\n\n- eski\n' \
    "'" "$1" "'" > "$P/work/CHANGELOG.md"
  git -C "$P/work" commit -qam "$1" && git -C "$P/work" push -q "$P/origin.git" main
}

setup_units() {
  # H1d `PrivateTmp=yes` — isbot papkasi $P /tmp ostida, xizmat uni ko'rishi uchun faqat shu yerda o'chiriladi.
  sed -e "s#/var/lib/innova/update/req/request#$P/upd/req/request#" -e "s#innova-update-agent.service#$UNIT.service#" \
    "$ROOT_DIR/iso/files/innova-update-agent.path" > "/etc/systemd/system/$UNIT.path"
  sed -e "s#ExecStart=/usr/local/sbin/innova-update#ExecStart=/bin/bash $ROOT_DIR/iso/files/innova-update.sh#" \
      -e "s#/var/lib/innova/update/req/request#$P/upd/req/request#" \
      -e "s#^PrivateTmp=yes#PrivateTmp=no#" \
      -e "s#^Type=oneshot#Type=oneshot\nEnvironment=INNOVA_DEST=$P/opt INNOVA_UPDATE_DIR=$P/upd INNOVA_UPDATE_LOCK=$P/lock#" \
    "$ROOT_DIR/iso/files/innova-update-agent.service" > "/etc/systemd/system/$UNIT.service"
  systemctl daemon-reload && systemctl start "$UNIT.path"
}

start_api_with_update_dir() {
  cat > "$OVERRIDE" <<EOF
services:
  api:
    environment:
      INNOVA_VERSION: "1.0.12"
    volumes:
      # H1c: appliance bilan bir xil — papka :ro, API faqat req/ ga yozadi.
      - $P/upd:/var/lib/innova/update:ro
      - $P/upd/req:/var/lib/innova/update/req
EOF
  flock /tmp/innova-stack.lock -c "cd '$DEPLOY_DIR' && docker compose -p '$PROJECT' -f docker-compose.yml -f '$OVERRIDE' up -d --no-deps api" >/dev/null
  wait_api
}

[ "${1:-}" != "--fresh" ] || flock /tmp/innova-stack.lock -c "cd '$DEPLOY_DIR' && docker compose -p '$PROJECT' build api web" >/dev/null \
  || { fail "build"; exit 1; }

echo "=== 0. agent yo'q (asl dev compose) ==="
wait_api; login "$ADMIN_PASSWORD" || { fail login; exit 1; }
check "$([ "$(st agent)" = False ] || [ "$(st agent)" = false ]; echo $?)" "agent=false (papka mount qilinmagan)"
R=$(api POST /system/update/check); check "$([ "$(jcode "$R")" = 503 ]; echo $?)" "check → 503 update_agent_missing" "$R"

echo "=== 1. host + systemd unit + API mount ==="
setup_host; setup_units; start_api_with_update_dir; login "$ADMIN_PASSWORD"
check "$([[ "$(st agent)" == [Tt]rue ]]; echo $?)" "agent=true"
check "$([ "$(st current)" = 1.0.12 ]; echo $?)" "current=1.0.12 (INNOVA_VERSION env)"

echo "=== 2. Tekshirish — yangi versiya yo'q ==="
R=$(api POST /system/update/check); check "$([ "$(jcode "$R")" = 202 ]; echo $?)" "check → 202" "$R"
wait_until 20 bash -c "[ ! -e '$P/upd/req/request' ] && grep -q '^state=idle' '$P/upd/status' 2>/dev/null"
check "$([ -n "$(st checked_at)" ] && [ "$(st latest)" = 1.0.12 ]; echo $?)" "agent tekshirdi: checked_at bor, latest=1.0.12" "$(cat "$P/upd/status" 2>&1)"
check "$([ "$(st available)" = False ] || [ "$(st available)" = false ]; echo $?)" "available=false" "$(cat "$P/upd/status")"
R=$(api POST /system/update/start '{"version":"1.0.13"}'); check "$([ "$(jcode "$R")" = 409 ]; echo $?)" "start → 409 update_not_available" "$R"

echo "=== 3. origin'da 1.0.13 → Tekshirish ==="
publish_release 1.0.13
api POST /system/update/check >/dev/null
wait_until 20 bash -c "grep -q '^available=1' '$P/upd/status'"
check "$([ "$(st latest)" = 1.0.13 ]; echo $?)" "latest=1.0.13"
CL=$(jbody "$(api GET /system/update)")
check "$(python3 -c "import json,sys;c=json.loads(sys.argv[1])['changelog'];sys.exit(not(len(c)==1 and c[0]['version']=='1.0.13'))" "$CL"; echo $?)" \
  "changelog faqat 1.0.13 bo'limi" "$CL"
R=$(api POST /system/update/start '{"version":"1.0.99"}'); check "$([ "$(jcode "$R")" = 409 ]; echo $?)" "eskirgan versiya → 409 mismatch" "$R"
R=$(api POST /system/update/start '{"version":"1.0.13;rm -rf /"}'); check "$([ "$(jcode "$R")" = 422 ]; echo $?)" "injeksiya versiya → 422" "$R"

echo "=== 4. Yangilash (API o'rtada qayta ishga tushadi) ==="
R=$(api POST /system/update/start '{"version":"1.0.13"}'); check "$([ "$(jcode "$R")" = 202 ]; echo $?)" "start → 202" "$R"
R=$(api POST /system/update/check); check "$([ "$(jcode "$R")" = 409 ]; echo $?)" "band paytida check → 409 update_busy" "$R"
API_START=$(docker inspect -f '{{.State.StartedAt}}' "$PROJECT-api-1")
wait_until 120 bash -c "grep -q '^state=done' '$P/upd/status'"
check "$([ "$(docker inspect -f '{{.State.StartedAt}}' "$PROJECT-api-1")" != "$API_START" ]; echo $?)" "API konteyneri yangilash paytida qayta ishga tushdi"
wait_api; login "$ADMIN_PASSWORD"
check "$([ "$(st state)" = done ]; echo $?)" "state=done" "$(cat "$P/upd/status")"
check "$([ "$(st current)" = 1.0.13 ]; echo $?)" "current=1.0.13"
check "$([ "$(cat "$P/opt/VERSION")" = 1.0.13 ] && [ "$(git -C "$P/src" show HEAD:VERSION)" = 1.0.13 ]; echo $?)" "host: VERSION va git 1.0.13"
B=$(sed -n 's/^backup=//p' "$P/upd/status")
check "$([ -n "$B" ] && zcat "$P/opt/backups/$B" | grep -c 'PostgreSQL database dump' >/dev/null; echo $?)" "haqiqiy pg_dump zaxirasi: $B"
LOG=$(jbody "$(api GET '/system/update/log?offset=0')")
check "$(python3 -c "import json,sys;t=json.loads(sys.argv[1])['text'];sys.exit(not('ishga tushirilmoqda' in t and 'yangilandi' in t and '\x1b' not in t))" "$LOG"; echo $?)" \
  "log: install bosqichlari + yakun, ANSI yo'q"
check "$(grep -q $'\t1.0.12\t1.0.13\tok' "$P/upd/history"; echo $?)" "history: 1.0.12 → 1.0.13 ok"
check "$(systemctl is-failed -q "$UNIT.path"; [ $? -ne 0 ]; echo $?)" "path unit hamon faol (start-limit yo'q)"

echo "=== 5. agent so'rovdan oldin yiqilsa — request o'chadi, path unit tirik ==="
chmod 000 "$P/opt/VERSION"; mv "$P/src/.git" "$P/src/.git.off"   # no_source → die (request o'chirilgandan keyin)
api POST /system/update/check >/dev/null
wait_until 20 bash -c "grep -q '^error=no_source' '$P/upd/status'"
check "$([ "$(st error)" = no_source ]; echo $?)" "manba yo'q → failed/no_source" "$(cat "$P/upd/status")"
mv "$P/src/.git.off" "$P/src/.git"; chmod 644 "$P/opt/VERSION"
sed -i "s#^ExecStart=.*#ExecStart=/bin/false#" "/etc/systemd/system/$UNIT.service"; systemctl daemon-reload
LEFT=0
for _ in 1 2 3 4 5 6 7 8; do
  echo check > "$P/upd/req/request"
  wait_until 5 bash -c "[ ! -e '$P/upd/req/request' ]" || LEFT=$((LEFT + 1))
done
check "$([ "$LEFT" = 0 ]; echo $?)" "8 ta ketma-ket yiqilish: so'rov har safar o'chdi (ExecStopPost)"
check "$(systemctl is-active -q "$UNIT.path"; echo $?)" "start-limit yo'q: path unit hamon faol"

echo "=== 6. audit ==="
check "$([ "$(sql "select count(*) from audit_log where entity='system_update' and action='update' and diff->>'to'='1.0.13'")" -ge 1 ]; echo $?)" "audit system.update.start"

echo "M11: $PASS o'tdi, $FAIL xato"
[ "$FAIL" = 0 ]
