#!/usr/bin/env bash
# Innova PBX — M0 proof skripti. replica/m0-contract.md va replica/architecture.md
# bo'yicha to'liq a-d isbot zanjirini ishga tushiradi va HAR bir qadam uchun
# PASS/FAIL chiqaradi:
#   (a) API sog'lik + setup/login
#   (b) CRUD + apply pipeline (extension/trunk/inbound-route)
#   (c) Optimistik qulf/409 in_use ziddiyat yo'llari
#   (d) SIPp bilan HAQIQIY qo'ng'iroq: trunk INVITE -> dialplan -> ichki raqam
#       javob beradi -> CDR `/calls`da ko'rinadi
#
# Foydalanish:
#   scripts/m0-proof.sh            # joriy ishlab turgan `innova-m0` stackka qarshi
#   scripts/m0-proof.sh --fresh    # avval `docker compose down -v` + qayta build + up -d
#
# MUHIM: bu skript faqat `innova-m0` compose loyihasiga tegadi (deploy/docker-compose.yml,
# `name: innova-m0`). Boshqa konteyner/tarmoq/image'larga TEGMAYDI.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"
SIPP_DIR="$ROOT_DIR/tests/sipp"
API_BASE="${API_BASE:-http://127.0.0.1:8710/api/v1}"
PROJECT="innova-m0"
NET="${PROJECT}_innova-net"
SIPP_IMAGE="python:3.12-slim"
UAC_IP="172.21.0.90"
UAS_IP="172.21.0.91"

ADMIN_PASSWORD="${PROOF_ADMIN_PASSWORD:-$(grep -E '^PROOF_ADMIN_PASSWORD=' "$DEPLOY_DIR/.env" | cut -d= -f2-)}"
[[ -n "$ADMIN_PASSWORD" ]] || { echo "PROOF_ADMIN_PASSWORD deploy/.env da yo'q"; exit 2; }

PASS=0
FAIL=0

pass() { echo "PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); }

cleanup_sipp() {
  docker rm -f innova-m0-proof-uac innova-m0-proof-uas >/dev/null 2>&1 || true
}
trap cleanup_sipp EXIT

if [[ "${1:-}" == "--fresh" ]]; then
  echo "--- --fresh: stack qayta quriladi ---"
  (cd "$DEPLOY_DIR" && docker compose down -v) || true
  (cd "$DEPLOY_DIR" && docker compose build) || { fail "docker compose build"; exit 1; }
  (cd "$DEPLOY_DIR" && docker compose up -d) || { fail "docker compose up"; exit 1; }
  echo "Konteynerlar tayyor bo'lishini kutish (API sog'lik tekshiruvi orqali)..."
  for i in $(seq 1 60); do
    curl -sf "$API_BASE/../healthz" >/dev/null 2>&1 && break
    sleep 2
  done
fi

echo "=== (a) API sog'lik + setup/login ==="
HEALTH_CODE=$(curl -s -o /dev/null -w '%{http_code}' "${API_BASE%/api/v1}/healthz" 2>/dev/null || true)
if [[ "$HEALTH_CODE" == "200" ]]; then pass "GET /healthz -> 200"; else fail "GET /healthz -> $HEALTH_CODE"; fi

# 1.0.4: panel HTTP'da ham, HTTPS'da ham (softfon mikrofoni) ochiladi.
for i in $(seq 1 40); do
  HTTPS_CODE=$(curl -sk -o /dev/null -w '%{http_code}' "https://127.0.0.1:${WEB_HTTPS_PORT:-8712}/")
  [[ "$HTTPS_CODE" == "200" ]] && break; sleep 1
done
HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${WEB_HOST_PORT:-8711}/")
if [[ "$HTTPS_CODE" == "200" && "$HTTP_CODE" == "200" ]]; then pass "Panel: http -> 200, https -> 200"
else fail "Panel: http -> $HTTP_CODE, https -> $HTTPS_CODE"; fi

# 1.0.4: o'rnatish kodi — `deploy/.env`da bo'lsa yuboramiz, bo'lmasa bo'sh (settings.setup_code
# bo'sh bo'lsa server tekshirmaydi, bu stack uchun orqaga moslik).
SETUP_CODE_VAL=$(grep -E '^SETUP_CODE=' "$DEPLOY_DIR/.env" 2>/dev/null | cut -d= -f2-)
if [[ -n "$SETUP_CODE_VAL" ]]; then
  WRONG_HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API_BASE/setup" -H 'Content-Type: application/json' \
    -d '{"admin":{"login":"hacker","password":"'"$ADMIN_PASSWORD"'","full_name":"X"},"language":"uz","timezone":"Asia/Tashkent","code":"notogri"}')
  # 403 — kod noto'g'ri; 409 — stek allaqachon sozlangan (--fresh siz).
  if [[ "$WRONG_HTTP_CODE" == "403" || "$WRONG_HTTP_CODE" == "409" ]]; then pass "POST /setup noto'g'ri kod bilan -> $WRONG_HTTP_CODE (admin yaratilmadi)"
  else fail "POST /setup noto'g'ri kod bilan -> $WRONG_HTTP_CODE (403 kutilgan)"; fi
fi
SETUP_HTTP_CODE=$(curl -s -o /tmp/m0proof_setup.json -w '%{http_code}' -X POST "$API_BASE/setup" \
  -H 'Content-Type: application/json' \
  -d '{"admin":{"login":"admin","password":"'"$ADMIN_PASSWORD"'","full_name":"Admin"},"language":"uz","timezone":"Asia/Tashkent","code":"'"$SETUP_CODE_VAL"'"}')
if [[ "$SETUP_HTTP_CODE" == "200" ]]; then
  pass "POST /setup -> 200 (birinchi marta)"
elif [[ "$SETUP_HTTP_CODE" == "409" ]]; then
  pass "POST /setup -> 409 setup_done (allaqachon o'rnatilgan, kutilgan)"
else
  fail "POST /setup -> $SETUP_HTTP_CODE"
fi

LOGIN_JSON=$(curl -s -X POST "$API_BASE/auth/login" -H 'Content-Type: application/json' \
  -d '{"login":"admin","password":"'"$ADMIN_PASSWORD"'"}')
TOKEN=$(echo "$LOGIN_JSON" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('access',''))" 2>/dev/null)
if [[ -n "$TOKEN" ]]; then pass "POST /auth/login -> access token olindi"; else fail "POST /auth/login -> token yo'q ($LOGIN_JSON)"; exit 1; fi

AUTH=(-H "Authorization: Bearer $TOKEN")

echo "=== (b) CRUD + apply pipeline ==="
EXT_JSON=$(curl -s -X POST "$API_BASE/extensions" "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d '{"number":"201","name":"Proof Ext"}')
EXT_ID=$(echo "$EXT_JSON" | python3 -c "import json,sys;print(json.load(sys.stdin).get('item',{}).get('id',''))" 2>/dev/null)
EXT_SECRET=$(echo "$EXT_JSON" | python3 -c "import json,sys;print(json.load(sys.stdin).get('sip',{}).get('password',''))" 2>/dev/null)
if [[ -n "$EXT_ID" ]]; then pass "POST /extensions -> ichki raqam yaratildi ($EXT_ID)"; else fail "POST /extensions -> $EXT_JSON"; fi

TRUNK_JSON=$(curl -s -X POST "$API_BASE/trunks" "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d "{\"name\":\"Proof Trunk\",\"host\":\"$UAC_IP\",\"port\":5060,\"match\":[\"$UAC_IP/32\"],\"codecs\":[\"ulaw\"],\"max_channels\":5,\"enabled\":true}")
TRUNK_ID=$(echo "$TRUNK_JSON" | python3 -c "import json,sys;print(json.load(sys.stdin).get('item',{}).get('id',''))" 2>/dev/null)
if [[ -n "$TRUNK_ID" ]]; then pass "POST /trunks -> trunk yaratildi ($TRUNK_ID)"; else fail "POST /trunks -> $TRUNK_JSON"; fi

TARGET_JSON=$(curl -s "$API_BASE/targets?kind=extension" "${AUTH[@]}")
TARGET_ID=$(echo "$TARGET_JSON" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print([i['id'] for i in d['items'] if i['number']=='201'][0])
" 2>/dev/null)

ROUTE_JSON=$(curl -s -w '\n%{http_code}' -X POST "$API_BASE/inbound-routes" "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d "{\"name\":\"Proof DID\",\"did\":\"712099001\",\"cid\":\"\",\"target_id\":\"$TARGET_ID\",\"enabled\":true}")
ROUTE_CODE=$(echo "$ROUTE_JSON" | tail -1)
ROUTE_BODY=$(echo "$ROUTE_JSON" | sed '$d')
APPLY_STATUS=$(echo "$ROUTE_BODY" | python3 -c "import json,sys;print(json.load(sys.stdin).get('apply',{}).get('status',''))" 2>/dev/null)
if [[ "$ROUTE_CODE" == "201" && "$APPLY_STATUS" == "applied" ]]; then
  pass "POST /inbound-routes -> 201, apply.status=applied (dialplan qo'llandi)"
else
  fail "POST /inbound-routes -> $ROUTE_CODE apply=$APPLY_STATUS ($ROUTE_BODY)"
fi

OLD_SECRET="$EXT_SECRET"
RELOAD_BEFORE=$(docker exec innova-m0-asterisk-1 asterisk -rx "core show uptime seconds" | awk '/Last reload/{print $3}')
ROTATE_JSON=$(curl -s -w '\n%{http_code}' -X POST "$API_BASE/extensions/$EXT_ID/rotate-secret" "${AUTH[@]}")
ROTATE_CODE=$(echo "$ROTATE_JSON" | tail -1)
ROTATE_BODY=$(echo "$ROTATE_JSON" | sed '$d')
ROTATE_APPLY=$(echo "$ROTATE_BODY" | python3 -c "import json,sys;print(json.load(sys.stdin).get('apply',{}).get('status',''))" 2>/dev/null)
EXT_SECRET=$(echo "$ROTATE_BODY" | python3 -c "import json,sys;print(json.load(sys.stdin).get('sip',{}).get('password',''))" 2>/dev/null)
if [[ "$ROTATE_CODE" == "200" && "$ROTATE_APPLY" == "realtime" ]]; then
  pass "POST /extensions/{id}/rotate-secret -> 200, apply.status=realtime (reload'siz)"
else
  fail "rotate-secret -> $ROTATE_CODE apply=$ROTATE_APPLY"
fi

echo "=== (c) Ziddiyat yo'llari ==="
EXT_INFO=$(curl -s "$API_BASE/extensions" "${AUTH[@]}")
EXT_UPDATED_AT=$(echo "$EXT_INFO" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print([i['updated_at'] for i in d['items'] if i['id']=='$EXT_ID'][0])
" 2>/dev/null)
DEL_CODE=$(curl -s -o /tmp/m0proof_del.json -w '%{http_code}' -X DELETE "$API_BASE/extensions/$EXT_ID" "${AUTH[@]}")
DEL_ERR=$(python3 -c "import json;print(json.load(open('/tmp/m0proof_del.json')).get('error',{}).get('code',''))" 2>/dev/null)
if [[ "$DEL_CODE" == "409" && "$DEL_ERR" == "in_use" ]]; then
  pass "DELETE /extensions/{id} (ishlatilmoqda) -> 409 in_use"
else
  fail "DELETE /extensions/{id} -> $DEL_CODE $DEL_ERR"
fi

STALE_CODE=$(curl -s -o /dev/null -w '%{http_code}' -X PATCH "$API_BASE/extensions/$EXT_ID" "${AUTH[@]}" \
  -H 'Content-Type: application/json' -d '{"name":"Stale Try","updated_at":"2000-01-01T00:00:00Z"}')
if [[ "$STALE_CODE" == "409" ]]; then
  pass "PATCH /extensions/{id} (eski updated_at) -> 409 (optimistik qulf)"
else
  fail "PATCH /extensions/{id} eski updated_at -> $STALE_CODE (409 kutilgan edi)"
fi

echo "=== (d) SIPp bilan HAQIQIY qo'ng'iroq isboti ==="
if ! command -v docker >/dev/null; then
  fail "docker topilmadi, SIPp isboti o'tkazib yuborildi"
else
  docker network inspect "$NET" >/dev/null 2>&1 || { fail "tarmoq $NET topilmadi"; }

  docker run -d --name innova-m0-proof-uas --network "$NET" --ip "$UAS_IP" "$SIPP_IMAGE" sleep infinity >/dev/null
  docker run -d --name innova-m0-proof-uac --network "$NET" --ip "$UAC_IP" "$SIPP_IMAGE" sleep infinity >/dev/null
  docker exec innova-m0-proof-uas bash -c "apt-get update -qq && apt-get install -y -qq sip-tester >/tmp/i.log 2>&1"
  docker exec innova-m0-proof-uac bash -c "apt-get update -qq && apt-get install -y -qq sip-tester >/tmp/i.log 2>&1"
  docker cp "$SIPP_DIR/register_only.py" innova-m0-proof-uas:/tmp/register_only.py
  docker cp "$SIPP_DIR/options_responder.py" innova-m0-proof-uas:/tmp/options_responder.py
  docker cp "$SIPP_DIR/uas_only.xml" innova-m0-proof-uas:/tmp/uas_only.xml
  # `uac_trunk_invite.xml` ichida DID "712000000" qotirilgan — bu proof
  # o'ziga xos DID (712099001) ishlatgani uchun nusxada almashtiramiz
  # (asl fixture fayl O'ZGARTIRILMAYDI).
  sed 's/712000000/712099001/' "$SIPP_DIR/uac_trunk_invite.xml" > /tmp/m0proof_uac.xml
  docker cp /tmp/m0proof_uac.xml innova-m0-proof-uac:/tmp/uac_trunk_invite.xml

  OLD_OUT=$(docker exec innova-m0-proof-uas python3 /tmp/register_only.py asterisk 5060 5080 "201" "$OLD_SECRET" 3600 5080 2>&1 || true)
  if echo "$OLD_OUT" | grep -q "REGISTER OK"; then fail "eski parol bilan REGISTER o'tib ketdi (rotate kuchga kirmagan)"; else pass "eski parol bilan REGISTER -> rad etildi"; fi
  REG_OUT=$(docker exec innova-m0-proof-uas python3 /tmp/register_only.py asterisk 5060 5080 "201" "$EXT_SECRET" 3600 5080)
  RELOAD_AFTER=$(docker exec innova-m0-asterisk-1 asterisk -rx "core show uptime seconds" | awk '/Last reload/{print $3}')
  if [[ -n "$RELOAD_BEFORE" && -n "$RELOAD_AFTER" && "$RELOAD_AFTER" -ge "$RELOAD_BEFORE" ]]; then pass "rotate-secret Asterisk reload'siz kuchga kirdi (oxirgi reload: $RELOAD_BEFORE s -> $RELOAD_AFTER s oldin)"; else fail "Asterisk reload qilingan ko'rinadi ($RELOAD_BEFORE -> $RELOAD_AFTER)"; fi
  if echo "$REG_OUT" | grep -q "REGISTER OK"; then pass "SIPp REGISTER 201 -> 200 OK"; else fail "SIPp REGISTER -> $REG_OUT"; fi

  docker exec -d innova-m0-proof-uas python3 /tmp/options_responder.py "$UAS_IP" 5080 10
  sleep 0.5
  docker exec innova-m0-asterisk-1 asterisk -rx "pjsip qualify 201" >/dev/null
  sleep 1
  QSTATE=$(docker exec innova-m0-asterisk-1 asterisk -rx "pjsip show contacts" | grep "201" || true)
  if echo "$QSTATE" | grep -q "Avail "; then pass "AOR 201 qualify -> Avail"; else fail "AOR 201 qualify holati: $QSTATE"; fi

  docker exec innova-m0-proof-uas bash -c "for p in /proc/[0-9]*; do pid=\$(basename \$p); readlink \$p/exe 2>/dev/null | grep -q python && kill -9 \$pid 2>/dev/null; done"
  docker exec -d innova-m0-proof-uas sipp -sf /tmp/uas_only.xml -i "$UAS_IP" -p 5080 -m 1 -timeout 600s
  sleep 0.3

  did_before=$(curl -s "$API_BASE/calls" "${AUTH[@]}" | python3 -c "import json,sys;print(json.load(sys.stdin).get('total',0))")
  UAC_OUT=$(docker exec innova-m0-proof-uac sipp -sf /tmp/uac_trunk_invite.xml -i "$UAC_IP" -p 5080 asterisk:5060 -m 1 -timeout 30s 2>&1 || true)
  # SIPp'ning yakuniy statistika ekrani ikki xil ustun formatida chiqishi
  # mumkin ("Successful call: N" yoki jadval ustuni) — shu sabab oxirgi
  # sondan foydalanamiz, qattiq satrni EMAS.
  OK_COUNT=$(echo "$UAC_OUT" | grep "Successful call" | tail -1 | grep -oE '[0-9]+' | tail -1)
  FAIL_COUNT=$(echo "$UAC_OUT" | grep "^  Failed call" | tail -1 | grep -oE '[0-9]+' | tail -1)
  if [[ "${OK_COUNT:-0}" -ge 1 && "${FAIL_COUNT:-0}" -eq 0 ]]; then
    pass "SIPp UAC trunk INVITE 712099001 -> Successful call: $OK_COUNT"
  else
    fail "SIPp UAC trunk INVITE natijasi: successful=$OK_COUNT failed=$FAIL_COUNT (qisman chiqish quyida)"
    echo "$UAC_OUT" | tail -15
  fi

  CALLS_JSON=$(curl -s "$API_BASE/calls" "${AUTH[@]}")
  FOUND=$(echo "$CALLS_JSON" | python3 -c "
import json,sys
d=json.load(sys.stdin)
ok = any(i.get('did')=='712099001' and i.get('disposition')=='answered' for i in d.get('items',[]))
print('yes' if ok else 'no')
" 2>/dev/null)
  if [[ "$FOUND" == "yes" ]]; then
    pass "GET /calls -> 712099001 disposition=answered topildi"
  else
    fail "GET /calls -> 712099001/answered topilmadi"
  fi
fi

echo
echo "=== NATIJA: PASS=$PASS FAIL=$FAIL ==="
[[ "$FAIL" -eq 0 ]]
