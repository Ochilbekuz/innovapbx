#!/usr/bin/env bash
# Innova PBX — M2c proof skripti. replica/m2c-contract.md bo'lim 7'dagi
# ssenariylardan MENIKI bo'lganlari (§1 sozlamalar, §3 toll-fraud, §4
# ogohlantirishlar):
#   1. Sozlamalar: GET standartlar; PATCH qisman; 422 chegaralar; 409 stale;
#      operator -> 403.
#   2-4. SIP hujum himoyasi (S33, §2) — BOSHQA agent ishi, MENIKI EMAS.
#      `scripts/lib/m2c_sipguard_scenario.sh` bo'lsa — shu yerda ishga tushadi.
#   5. Toll-fraud: ext_max_per_hour=2 -> 2 OK, 3-si rad (trunkka INVITE
#      KELMAYDI), bloklangan, Telegram, hodisa; unblock -> 4,5-si OK, 6-si
#      yana rad (BIR XIL kalit, dedup oynasida -> §8'da "suppressed" sifatida
#      tekshiriladi). Xalqaro ext_international_per_day=1 -> 2-xalqaro rad.
#      API to'xtatilgan: mahalliy OK (fail-open), xalqaro rad (fail-closed);
#      API qaytadi.
#   6. Bir vaqtdagi limit (max_concurrent_outbound=1, §1'da PATCH qilingan):
#      ikki parallel chiquvchi -> ikkinchisi rad, `concurrent_limit` hodisasi
#      + ogohlantirish (bu safar o'chiq tur sifatida -> §8'da "disabled").
#   7. Trunk monitoring (§5) — BOSHQA agent ishi, MENIKI EMAS.
#      `scripts/lib/m2c_trunkmon_scenario.sh` bo'lsa — shu yerda ishga tushadi.
#   8. Ogohlantirishlar: dedup (suppressed, ssenariy 5'dagi takror blok),
#      o'chiq tur (disabled, ssenariy 6'dagi concurrent_limit), `/settings/
#      alerts/test`, tarix (`GET /alerts`), token javob/audit/alert_log'da yo'q.
#
# Foydalanish:
#   scripts/m2c-proof.sh            # joriy `innova-m0` stackka qarshi (M2c qoldiqlari bo'lsa — exit 2)
#   scripts/m2c-proof.sh --fresh    # avval `docker compose down -v` + qayta build + up -d
#
# MUHIM: faqat `innova-m0` compose loyihasiga tegadi; o'z konteynerlarini (m2c-proof-*) oxirida o'chiradi.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"
SIPP_DIR="$ROOT_DIR/tests/sipp"
LIB_DIR="$ROOT_DIR/scripts/lib"
API_BASE="${API_BASE:-http://127.0.0.1:8710/api/v1}"
PROJECT="innova-m0"
NET="${PROJECT}_innova-net"
SIPP_IMAGE="python:3.12-slim"
PG=innova-m0-postgres-1
AST=innova-m0-asterisk-1
APICONT=innova-m0-api-1

EXT_IP="172.21.0.200"    # chiquvchi test-UA (barcha ichki raqamlar shu konteynerdan teradi)
TRUNK_IP="172.21.0.201"  # yagona trunk-UAS (bitta INVITE'dan keyin o'zi chiqadi — qayta ishga tushiriladi)
TG_IP="172.21.0.202"     # soxta Telegram

# shellcheck source=lib/m2a_common.sh
source "$LIB_DIR/m2a_common.sh"
# shellcheck source=lib/m2c_common.sh
TG_CONT=m2c-proof-tg
TG_LOG=/tmp/tg.log
source "$LIB_DIR/m2c_common.sh"

ADMIN_PASSWORD="${PROOF_ADMIN_PASSWORD:-$(grep -E '^PROOF_ADMIN_PASSWORD=' "$DEPLOY_DIR/.env" | cut -d= -f2-)}"
[[ -n "$ADMIN_PASSWORD" ]] || { echo "PROOF_ADMIN_PASSWORD deploy/.env da yo'q"; exit 2; }

CONTAINERS=(m2c-proof-ext m2c-proof-trunk m2c-proof-tg)
cleanup() {
  docker rm -f "${CONTAINERS[@]}" >/dev/null 2>&1 || true
  [[ "${API_STOPPED:-0}" == "1" ]] && docker start "$APICONT" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

if [[ "${1:-}" == "--fresh" ]]; then
  echo "--- --fresh: stack qayta quriladi ---"
  # Isbot tezligi uchun fon vazifa aylanishlarini qisqartiramiz (§2/§5) —
  # `docker-compose.yml`dagi `${VAR:-sukut}` qolipi, sukut qiymatlar O'ZGARMAYDI
  # (production'da bu ikkisi eksport qilinmasa 5s/30s qoladi).
  export SIP_GUARD_INTERVAL_S="${SIP_GUARD_INTERVAL_S:-2}"
  export TRUNK_MONITOR_INTERVAL_S="${TRUNK_MONITOR_INTERVAL_S:-3}"
  (cd "$DEPLOY_DIR" && docker compose down -v) || true
  (cd "$DEPLOY_DIR" && docker compose build) || { fail "docker compose build"; exit 1; }
  (cd "$DEPLOY_DIR" && docker compose up -d) || { fail "docker compose up"; exit 1; }
  echo "Konteynerlar tayyor bo'lishini kutish..."
  wait_api
fi

echo "=== setup/login ==="
login "$ADMIN_PASSWORD" || { fail "login"; exit 1; }
echo "login OK"

LEFTOVER=$(jget "$(jbody "$(api GET "/extensions?q=M2c")")" total 2>/dev/null)
if [[ -n "$LEFTOVER" && "$LEFTOVER" != "0" ]]; then
  echo "Stekda oldingi M2c isbot qoldiqlari bor ($LEFTOVER ext) — 'scripts/m2c-proof.sh --fresh' bilan ishga tushiring."
  exit 2
fi

# ---------------------------------------------------------------- resurslar
echo "=== resurslarni tayyorlash ==="
declare -A EXT_ID SECRET
for n in 201 202 203 204 205; do
  j=$(jbody "$(api POST /extensions "{\"number\":\"$n\",\"name\":\"M2c$n\"}")")
  EXT_ID[$n]=$(jget "$j" item id); SECRET[$n]=$(jget "$j" sip password)
done
check "$( [[ -n "${EXT_ID[201]}" && -n "${EXT_ID[202]}" && -n "${EXT_ID[203]}" && -n "${EXT_ID[204]}" && -n "${EXT_ID[205]}" ]]; echo $?)" \
  "POST /extensions -> 201..205 yaratildi" "${EXT_ID[*]}"

TRUNK_JSON=$(api POST /trunks "{\"name\":\"M2cTrunk\",\"host\":\"$TRUNK_IP\",\"port\":5060,\"match\":[\"$TRUNK_IP/32\"],\"codecs\":[\"ulaw\"],\"max_channels\":5,\"enabled\":true}")
TRUNK_ID=$(jget "$(jbody "$TRUNK_JSON")" item id)
[[ -n "$TRUNK_ID" ]] && pass "POST /trunks -> M2cTrunk yaratildi" || fail "POST /trunks -> $TRUNK_JSON"

LOCALROUTE_JSON=$(api POST /outbound-routes "{\"name\":\"M2cLocalRoute\",\"priority\":1,\"patterns\":[{\"strip_prefix\":\"0\",\"pattern\":\"XXXXXXXXX\",\"add_prefix\":\"998\"}],\"trunk_ids\":[\"$TRUNK_ID\"],\"international\":false}")
LOCALROUTE_ID=$(jget "$(jbody "$LOCALROUTE_JSON")" item id)
[[ -n "$LOCALROUTE_ID" ]] && pass "POST /outbound-routes -> M2cLocalRoute yaratildi" || fail "POST /outbound-routes LocalRoute -> $LOCALROUTE_JSON"

INTLROUTE_JSON=$(api POST /outbound-routes "{\"name\":\"M2cIntlRoute\",\"priority\":2,\"patterns\":[{\"pattern\":\"00.\"}],\"trunk_ids\":[\"$TRUNK_ID\"],\"international\":true}")
INTLROUTE_ID=$(jget "$(jbody "$INTLROUTE_JSON")" item id)
[[ -n "$INTLROUTE_ID" ]] && pass "POST /outbound-routes -> M2cIntlRoute (international=true) yaratildi" || fail "POST /outbound-routes IntlRoute -> $INTLROUTE_JSON"

OP_J=$(api POST /users '{"username":"m2coperator","full_name":"M2c Operator","role":"operator","password":"M2cOperatorPassAbc9"}')
OP_ID=$(jget "$(jbody "$OP_J")" item id)
[[ -n "$OP_ID" ]] && pass "POST /users -> m2coperator (role=operator) yaratildi" || fail "POST /users operator -> $OP_J"

# --- SIP infratuzilma: bitta test-UA + bitta trunk-UAS + soxta Telegram ---
docker network inspect "$NET" >/dev/null 2>&1 || fail "tarmoq $NET topilmadi"
docker run -d --name m2c-proof-ext --network "$NET" --ip "$EXT_IP" "$SIPP_IMAGE" sleep infinity >/dev/null
docker run -d --name m2c-proof-trunk --network "$NET" --ip "$TRUNK_IP" "$SIPP_IMAGE" sleep infinity >/dev/null
docker run -d --name "$TG_CONT" --network "$NET" --ip "$TG_IP" "$SIPP_IMAGE" sleep infinity >/dev/null
docker cp "$SIPP_DIR/outbound_invite.py" m2c-proof-ext:/tmp/outbound_invite.py
docker cp "$SIPP_DIR/uas_log_and_answer.py" m2c-proof-trunk:/tmp/uas_log_and_answer.py
docker cp "$SIPP_DIR/fake_telegram.py" "$TG_CONT:/tmp/fake_telegram.py"
docker exec -d "$TG_CONT" python3 /tmp/fake_telegram.py 0.0.0.0 8081 "$TG_LOG"

TG_TOKEN="m2c-tg-secret-$(date +%s)"
NOTIFY_J=$(api PATCH /settings/notify "{\"telegram_token\":\"$TG_TOKEN\",\"telegram_api_base\":\"http://$TG_IP:8081\"}")
check "$( [[ "$(jcode "$NOTIFY_J")" == "200" && "$(jget "$(jbody "$NOTIFY_J")" has_telegram_token)" == "True" ]]; echo $?)" \
  "PATCH /settings/notify -> telegram token/api_base sozlandi" "$NOTIFY_J"

ALERTS_SETUP_J=$(api PATCH /settings/alerts '{"chat_ids":["555"],"updated_at":"1970-01-01T00:00:00Z"}')
ALERTS_UPDATED_AT=$(jget "$(jbody "$ALERTS_SETUP_J")" updated_at)
if [[ -z "$ALERTS_UPDATED_AT" ]]; then
  # `updated_at` noto'g'ri bo'lsa (0016 seed qiymati boshqacha) — avval GET bilan HAQIQIYsini olamiz.
  ALERTS_UPDATED_AT=$(jget "$(jbody "$(api GET /settings/alerts)")" updated_at)
  ALERTS_SETUP_J=$(api PATCH /settings/alerts "{\"chat_ids\":[\"555\"],\"updated_at\":\"$ALERTS_UPDATED_AT\"}")
  ALERTS_UPDATED_AT=$(jget "$(jbody "$ALERTS_SETUP_J")" updated_at)
fi
check "$( [[ "$(jget "$(jbody "$ALERTS_SETUP_J")" chat_ids 0)" == "555" ]]; echo $?)" \
  "PATCH /settings/alerts -> chat_ids=[555]" "$ALERTS_SETUP_J"

call_out() { # username secret dialed hold_ms -> stdout: outbound_invite.py natijasi
  LPORT=$((LPORT + 1))
  docker exec m2c-proof-ext python3 /tmp/outbound_invite.py asterisk 5060 "$LPORT" "$1" "$2" "$3" \
    --hold-ms "${4:-300}" --no-register 2>&1
}
LPORT=5300

echo "=== ssenariy 1: Sozlamalar (GET/PATCH/422/409/403) ==="
S1_GET=$(api GET /security/settings)
S1_BODY=$(jbody "$S1_GET")
check "$( [[ "$(jget "$S1_BODY" sip_guard max_failures)" == "5" && "$(jget "$S1_BODY" toll_fraud max_concurrent_outbound)" == "0" \
  && "$(jget "$S1_BODY" toll_fraud ext_max_per_hour)" == "60" && "$(jget "$S1_BODY" toll_fraud ext_international_per_day)" == "20" ]]; echo $?)" \
  "1: GET /security/settings -> standart qiymatlar" "$S1_BODY"
U0=$(jget "$S1_BODY" updated_at)

S1_PATCH1=$(api PATCH /security/settings "{\"toll_fraud\":{\"max_concurrent_outbound\":1},\"updated_at\":\"$U0\"}")
S1_PATCH1_BODY=$(jbody "$S1_PATCH1")
check "$( [[ "$(jget "$S1_PATCH1_BODY" item toll_fraud max_concurrent_outbound)" == "1" && "$(jget "$S1_PATCH1_BODY" apply status)" == "applied" ]]; echo $?)" \
  "1: PATCH toll_fraud.max_concurrent_outbound=1 -> apply.status=applied (dialplan qayta kompilyatsiya)" "$S1_PATCH1_BODY"
U1=$(jget "$S1_PATCH1_BODY" item updated_at)

S1_422=$(api PATCH /security/settings "{\"sip_guard\":{\"max_failures\":2},\"updated_at\":\"$U1\"}")
check "$( [[ "$(jcode "$S1_422")" == "422" && "$(jget "$(jbody "$S1_422")" error field)" == "sip_guard.max_failures" ]]; echo $?)" \
  "1: PATCH sip_guard.max_failures=2 (< 3) -> 422 field=sip_guard.max_failures" "$S1_422"

# QAT'IY o'tmishdagi literal sana ishlatiladi ($U0 EMAS) — `check_not_stale`
# (`app/core/optimistic.py`) SONIYA aniqligida solishtiradi (`naive_utc`,
# mikrosoniyalarni kesib tashlaydi); tez skript bir soniya ichida bir nechta
# PATCH qilsa, $U0 va joriy DB qiymati BIR XIL soniyaga tushib, 409 soxta
# ravishda CHIQMASLIGI mumkin edi (jonli isbotda topilgan) — o'tmish literal
# bu muammodan butunlay xoli.
S1_409=$(api PATCH /security/settings '{"toll_fraud":{"ext_max_per_hour":2},"updated_at":"2020-01-01T00:00:00Z"}')
check "$( [[ "$(jcode "$S1_409")" == "409" ]]; echo $?)" \
  "1: PATCH eskirgan updated_at (2020-01-01) -> 409 stale" "$S1_409"

S1_PATCH2=$(api PATCH /security/settings "{\"toll_fraud\":{\"ext_max_per_hour\":2,\"ext_international_per_day\":1},\"updated_at\":\"$U1\"}")
S1_PATCH2_BODY=$(jbody "$S1_PATCH2")
check "$( [[ "$(jget "$S1_PATCH2_BODY" item toll_fraud ext_max_per_hour)" == "2" && "$(jget "$S1_PATCH2_BODY" item toll_fraud ext_international_per_day)" == "1" \
  && "$(jget "$S1_PATCH2_BODY" apply status)" == "unchanged" ]]; echo $?)" \
  "1: PATCH ext_max_per_hour=2/ext_international_per_day=1 -> apply.status=unchanged (concurrent o'zgarmadi)" "$S1_PATCH2_BODY"

OP_TOKEN=$(login_as m2coperator M2cOperatorPassAbc9)
OP_403=$(api_as "$OP_TOKEN" GET /security/settings)
check "$( [[ "$(jcode "$OP_403")" == "403" ]]; echo $?)" "1: operator -> GET /security/settings 403" "$OP_403"

echo "=== ssenariy 2-4: SIP hujum himoyasi (§2) ==="
if [[ -f "$LIB_DIR/m2c_sipguard_scenario.sh" ]]; then
  # shellcheck source=/dev/null
  source "$LIB_DIR/m2c_sipguard_scenario.sh"
else
  echo "SKIP: 2-4 — boshqa agent ishi (scripts/lib/m2c_sipguard_scenario.sh topilmadi)"
fi

echo "=== HAQIQIY SIP: ssenariy 5 (toll-fraud ichki raqam limitlari) ==="
if ! command -v docker >/dev/null; then
  fail "docker topilmadi, SIP isbotlari o'tkazib yuborildi"
else
  echo "--- 5a: ext_max_per_hour=2 (201) ---"
  uas_ready m2c-proof-trunk uas_log_and_answer.py "$TRUNK_IP" "$TRUNK_ID" 5
  C1=$(call_out 201 "${SECRET[201]}" 0901234567 300)
  check "$(echo "$C1" | grep -q "FINAL: 200"; echo $?)" "5a: 201 -> 0901234567 (1-chi) OK" "$C1"

  uas_ready m2c-proof-trunk uas_log_and_answer.py "$TRUNK_IP" "$TRUNK_ID" 5
  C2=$(call_out 201 "${SECRET[201]}" 0901234567 300)
  check "$(echo "$C2" | grep -q "FINAL: 200"; echo $?)" "5a: 201 -> 0901234567 (2-chi) OK" "$C2"

  # 3-chi: limit (2) yetib bloklanadi — trunkka INVITE UMUMAN bormasligi uchun
  # tinglovchi QAYTA ISHGA TUSHIRILMAYDI (bo'lmasa — SKIP, uning o'zi ham dalil).
  C3=$(call_out 201 "${SECRET[201]}" 0901234567 300)
  if echo "$C3" | grep -q "FINAL: 200"; then fail "5a: 3-chi chaqiruv KUTILMAGANDA 200 qaytardi: $C3"; else pass "5a: 3-chi chaqiruv rad etildi (limit=2) ($C3)"; fi

  TB_J=$(api GET /security/toll-blocks)
  TB_BODY=$(jbody "$TB_J")
  check "$( [[ "$(jget "$TB_BODY" items 0 number)" == "201" && "$(jget "$TB_BODY" items 0 reason)" == "per_hour" ]]; echo $?)" \
    "5a: GET /security/toll-blocks -> 201 bloklangan (per_hour)" "$TB_BODY"

  EV_J=$(api "GET" "/security/events?kind=toll_blocked&limit=100")
  check "$(echo "$(jbody "$EV_J")" | python3 -c "
import json,sys
d=json.load(sys.stdin)
sys.exit(0 if any(i['extension']=='201' and i['details'].get('reason')=='per_hour' for i in d['items']) else 1)"; echo $?)" \
    "5a: GET /security/events kind=toll_blocked -> 201/per_hour bor" "$(jbody "$EV_J")"

  # `kind` Telegram'ning o'ziga yuborilmaydi — faqat DEKODLANGAN matndan
  # ("chiquvchi bloklandi" + raqam) ajratiladi (`tg_count_decoded`/`m2c_common.sh`).
  wait_until 10 tg_is_decoded "201 chiquvchi bloklandi" 1
  check "$(tg_is_decoded "201 chiquvchi bloklandi" 1; echo $?)" \
    "5a: soxta Telegram'ga 201 uchun toll_blocked xabari keldi (1 marta)" "$(tg_count_decoded "201 chiquvchi bloklandi")"
  TOLL_TEXT=$(tg_text_of_decoded "201 chiquvchi bloklandi")
  check "$( [[ -n "$TOLL_TEXT" ]]; echo $?)" "5a: Telegram matni o'qildi" "$TOLL_TEXT"

  echo "--- 5b: unblock -> 4,5-si OK, 6-si yana rad (dedup §8 uchun) ---"
  UNBLOCK_J=$(api POST "/security/toll-blocks/${EXT_ID[201]}/unblock")
  check "$( [[ "$(jcode "$UNBLOCK_J")" == "200" && "$(jget "$(jbody "$UNBLOCK_J")" item number)" == "201" ]]; echo $?)" \
    "5b: POST /security/toll-blocks/201/unblock -> 200" "$UNBLOCK_J"

  uas_ready m2c-proof-trunk uas_log_and_answer.py "$TRUNK_IP" "$TRUNK_ID" 5
  C4=$(call_out 201 "${SECRET[201]}" 0901234567 300)
  check "$(echo "$C4" | grep -q "FINAL: 200"; echo $?)" "5b: 201 -> 0901234567 (4-chi, unblock'dan keyin) OK" "$C4"

  uas_ready m2c-proof-trunk uas_log_and_answer.py "$TRUNK_IP" "$TRUNK_ID" 5
  C5=$(call_out 201 "${SECRET[201]}" 0901234567 300)
  check "$(echo "$C5" | grep -q "FINAL: 200"; echo $?)" "5b: 201 -> 0901234567 (5-chi) OK" "$C5"

  C6=$(call_out 201 "${SECRET[201]}" 0901234567 300)
  if echo "$C6" | grep -q "FINAL: 200"; then fail "5b: 6-chi chaqiruv KUTILMAGANDA 200 qaytardi: $C6"; else pass "5b: 6-chi chaqiruv yana rad etildi (limit=2, yangi oyna) ($C6)"; fi

  echo "--- 5c: xalqaro ext_international_per_day=1 (202) ---"
  uas_ready m2c-proof-trunk uas_log_and_answer.py "$TRUNK_IP" "$TRUNK_ID" 5
  CI1=$(call_out 202 "${SECRET[202]}" 0044201234567 300)
  check "$(echo "$CI1" | grep -q "FINAL: 200"; echo $?)" "5c: 202 -> 0044201234567 (1-xalqaro) OK" "$CI1"

  CI2=$(call_out 202 "${SECRET[202]}" 0044209876543 300)
  if echo "$CI2" | grep -q "FINAL: 200"; then fail "5c: 2-xalqaro chaqiruv KUTILMAGANDA 200 qaytardi: $CI2"; else pass "5c: 2-xalqaro chaqiruv rad etildi (limit=1) ($CI2)"; fi

  EV2_J=$(api "GET" "/security/events?kind=toll_blocked&limit=100")
  check "$(echo "$(jbody "$EV2_J")" | python3 -c "
import json,sys
d=json.load(sys.stdin)
sys.exit(0 if any(i['extension']=='202' and i['details'].get('reason')=='international_per_day' for i in d['items']) else 1)"; echo $?)" \
    "5c: GET /security/events -> 202/international_per_day bor" "$(jbody "$EV2_J")"

  echo "--- 5d: API to'xtatilgan — mahalliy OK (fail-open), xalqaro rad (fail-closed) ---"
  docker stop "$APICONT" >/dev/null 2>&1
  API_STOPPED=1
  sleep 1
  uas_ready m2c-proof-trunk uas_log_and_answer.py "$TRUNK_IP" "$TRUNK_ID" 5
  CD1=$(call_out 205 "${SECRET[205]}" 0901234568 300)
  check "$(echo "$CD1" | grep -q "FINAL: 200"; echo $?)" "5d: API o'chiq, 205 mahalliy -> fail-open, OK" "$CD1"

  CD2=$(call_out 205 "${SECRET[205]}" 0044208765432 300)
  if echo "$CD2" | grep -q "FINAL: 200"; then fail "5d: API o'chiq, xalqaro KUTILMAGANDA 200 qaytardi: $CD2"; else pass "5d: API o'chiq, 205 xalqaro -> fail-closed, rad ($CD2)"; fi

  docker start "$APICONT" >/dev/null 2>&1
  API_STOPPED=0
  wait_api && pass "5d: API qayta ishga tushdi (healthz)" || fail "5d: API qaytmadi"
fi

echo "=== HAQIQIY SIP: ssenariy 6 (bir vaqtdagi chiquvchi limit=1) ==="
if command -v docker >/dev/null; then
  # §8 "o'chiq tur" (disabled) tekshiruvi uchun ATAYLAB OLDINDAN o'chiramiz —
  # concurrent_limit hodisasi/ogohlantirishi KEYINROQ "disabled" holatda
  # yozilishi kerak.
  AL_EVENTS_J=$(api PATCH /settings/alerts "{\"events\":{\"concurrent_limit\":false},\"updated_at\":\"$(jget "$(jbody "$(api GET /settings/alerts)")" updated_at)\"}")
  check "$( [[ "$(jget "$(jbody "$AL_EVENTS_J")" events concurrent_limit)" == "False" ]]; echo $?)" \
    "6: PATCH /settings/alerts events.concurrent_limit=false (§8 'disabled' tayyorlash)" "$AL_EVENTS_J"

  uas_ready m2c-proof-trunk uas_log_and_answer.py "$TRUNK_IP" "$TRUNK_ID" 8
  docker exec -d m2c-proof-ext sh -c \
    "python3 -u /tmp/outbound_invite.py asterisk 5060 5399 203 '${SECRET[203]}' 0901234571 --hold-ms 3000 --no-register > /tmp/callA.log 2>&1"
  sleep 1.3
  CB=$(call_out 204 "${SECRET[204]}" 0901234572 300)
  if echo "$CB" | grep -q "FINAL: 200"; then fail "6: ikkinchi (parallel) chaqiruv KUTILMAGANDA 200 qaytardi: $CB"; else pass "6: ikkinchi (parallel) chaqiruv rad etildi (max_concurrent_outbound=1) ($CB)"; fi

  i=0
  while (( i < 50 )); do
    CA=$(docker exec m2c-proof-ext cat /tmp/callA.log 2>/dev/null)
    # ANCHOR SHART: "INVITE_FINAL: ..." qatori HAM "FINAL:" naqshiga mos
    # keladi (substring) -- javob kelgach LEKIN hali hold/bye tugamasdan
    # tsikl ERTA chiqib ketardi (jonli isbotda topilgan). Faqat qator
    # BOSHIDAGI "FINAL:" (outbound_invite.py'ning HAQIQIY yakuniy qatori).
    echo "$CA" | grep -q "^FINAL:" && break
    sleep 0.1; i=$((i + 1))
  done
  check "$(echo "$CA" | grep -q "^FINAL: 200"; echo $?)" "6: birinchi (ilgari boshlangan) chaqiruv OK bo'lib qoldi" "$CA"

  CEV_J=$(api "GET" "/security/events?kind=concurrent_limit&limit=10")
  check "$(echo "$(jbody "$CEV_J")" | python3 -c "
import json,sys
d=json.load(sys.stdin)
sys.exit(0 if any(i['details'].get('max_concurrent_outbound')==1 for i in d['items']) else 1)"; echo $?)" \
    "6: GET /security/events kind=concurrent_limit -> hodisa yozilgan" "$(jbody "$CEV_J")"
else
  fail "docker topilmadi, ssenariy 6 o'tkazib yuborildi"
fi

echo "=== ssenariy 7: trunk monitoringi (§5) ==="
if [[ -f "$LIB_DIR/m2c_trunkmon_scenario.sh" ]]; then
  # shellcheck source=/dev/null
  source "$LIB_DIR/m2c_trunkmon_scenario.sh"
else
  echo "SKIP: 7 — boshqa agent ishi (scripts/lib/m2c_trunkmon_scenario.sh topilmadi)"
fi

echo "=== ssenariy 8: ogohlantirishlar (dedup/disabled/test/tarix/token) ==="
# Test-alertidan OLDIN: JAMI 5 marta Telegram'ga sendMessage ketgan bo'lishi
# kerak — ssenariy 2'dagi ip_banned (1, "sent") + 201 (5a, 1-blok, "sent") +
# 202 (5c, xalqaro blok, "sent") + ssenariy 7'dagi trunk_down/trunk_up (2,
# ikkisi ham "sent"); 201'ning 2-bloki dedup bilan "suppressed" (Telegram'ga
# umuman murojaat qilinmaydi), 6-ssenariydagi concurrent_limit esa "disabled"
# (shu sabab ham yubormaydi) — ikkisi ham quyidagi hisobga KIRMAYDI.
wait_until 15 tg_is sendMessage 5
check "$(tg_is sendMessage 5; echo $?)" "8: test-alertdan oldin JAMI 5 marta sendMessage (dedup/disabled yubormagan)" "$(tg_count sendMessage)"

AL_LIST_J=$(api "GET" "/alerts?limit=50")
AL_LIST_BODY=$(jbody "$AL_LIST_J")
check "$(echo "$AL_LIST_BODY" | python3 -c "
import json,sys
d=json.load(sys.stdin)
tb = [i for i in d['items'] if i['kind']=='toll_blocked' and i['key']=='201']
sys.exit(0 if any(i['status']=='sent' for i in tb) and any(i['status']=='suppressed' for i in tb) else 1)"; echo $?)" \
  "8: GET /alerts -> 201 uchun BIR 'sent' VA BIR 'suppressed' (dedup) bor" "$AL_LIST_BODY"

check "$(echo "$AL_LIST_BODY" | python3 -c "
import json,sys
d=json.load(sys.stdin)
sys.exit(0 if any(i['kind']=='concurrent_limit' and i['status']=='disabled' for i in d['items']) else 1)"; echo $?)" \
  "8: GET /alerts -> concurrent_limit 'disabled' holatda (hodisa turi o'chiq edi)" "$AL_LIST_BODY"

AT_J=$(api POST /settings/alerts/test)
check "$( [[ "$(jcode "$AT_J")" == "200" && "$(jget "$(jbody "$AT_J")" sent)" == "1" ]]; echo $?)" \
  "8: POST /settings/alerts/test -> 200 sent=1" "$AT_J"
wait_until 10 tg_is sendMessage 6
check "$(tg_is sendMessage 6; echo $?)" "8: /settings/alerts/test -> Telegram'ga 6-chi sendMessage ketdi" "$(tg_count sendMessage)"
TEST_TEXT=$(tg_text_of "sendMessage")
check "$( [[ -n "$TEST_TEXT" ]]; echo $?)" "8: oxirgi sendMessage matni o'qildi (test xabari)" "$TEST_TEXT"

AL_LIST2_J=$(api "GET" "/alerts?kind=test&limit=5")
check "$(echo "$(jbody "$AL_LIST2_J")" | python3 -c "
import json,sys
d=json.load(sys.stdin)
sys.exit(0 if any(i['status']=='sent' for i in d['items']) else 1)"; echo $?)" \
  "8: GET /alerts?kind=test -> sent" "$(jbody "$AL_LIST2_J")"

# --- token hech qayerda ko'rinmasligi (javob/audit/alert_log) ---
# ASOSIY xavf — `PATCH /settings/notify` (tokenni O'ZI qabul qiladigan
# chaqiruv): audit yozuvida token "***" bilan almashtirilishi SHART
# (contract §0). DIQQAT: `/audit?action=...` `record_audit`ga berilgan
# "entity.fe'l" shaklidagi XOM qiymat bilan emas, balki `normalize_action()`
# (`app/services/audit.py`) orqali TORAYTIRILGAN umumiy fe'l bilan ("update"
# va hok.) saqlanadi — shu sabab `entity=` bo'yicha filtrlaymiz (haqiqiy
# query parametr), `action=` XOM qiymat bilan HECH QACHON mos kelmaydi.
NO_LEAK_AL=$(api GET "/alerts?limit=200")
NO_LEAK_SETTINGS=$(api GET /settings/alerts)
NO_LEAK_NOTIFY=$(api GET /settings/notify)
AUDIT_ALERTS_J=$(api GET "/audit?entity=alert_settings&size=20")
AUDIT_NOTIFY_J=$(api GET "/audit?entity=notify_settings&size=20")
check "$(echo "$(jbody "$AUDIT_NOTIFY_J")" | python3 -c "
import json,sys
d=json.load(sys.stdin)
sys.exit(0 if any(i.get('diff', {}).get('telegram_token') == '***' for i in d.get('items', [])) else 1)"; echo $?)" \
  "8: audit entity=notify_settings -> diff.telegram_token='***' (asl token YO'Q)" "$(jbody "$AUDIT_NOTIFY_J")"
check "$( ! grep -q "$TG_TOKEN" <<<"$NO_LEAK_AL$NO_LEAK_SETTINGS$NO_LEAK_NOTIFY$AUDIT_ALERTS_J$AUDIT_NOTIFY_J"; echo $?)" \
  "8: Telegram token GET /alerts, /settings/alerts, /settings/notify, audit'da YO'Q" "---"
DB_LEAK=$(sql "select count(*) from notify_settings where telegram_token_enc like '%$TG_TOKEN%'")
check "$( [[ "$DB_LEAK" == "0" ]]; echo $?)" "8: token bazada ochiq (plaintext) saqlanmagan" "$DB_LEAK"

echo "=== NATIJA: PASS=$PASS FAIL=$FAIL ==="
[[ "$FAIL" -eq 0 ]]
