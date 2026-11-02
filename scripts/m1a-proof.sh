#!/usr/bin/env bash
# Innova PBX — M1a proof skripti. replica/m1a-contract.md «Isbot» bo'limidagi
# 5 ssenariyni ishga tushiradi va HAR biri uchun PASS/FAIL chiqaradi:
#   1. Ish vaqti force_open -> DID -> time_condition -> IVR -> «1» -> navbat
#      (101,102 a'zo) -> 101 javob beradi -> CDR answered (SIP INFO DTMF).
#   2. force_closed -> DID -> hangup yo'li -> CDR rad etilgan (200 EMAS).
#   3. IVR timeout -> ring group (102) -> 102 javob beradi.
#   4. IVR timeout -> IVR o'ziga (chiqishsiz) -> 422 loop.
#   5. Navbatga a'zo qo'shish -> `queue show`da reload'siz ko'rinadi.
#
# Foydalanish:
#   scripts/m1a-proof.sh            # joriy ishlab turgan `innova-m0` stackka qarshi
#   scripts/m1a-proof.sh --fresh    # avval `docker compose down -v` + qayta build + up -d
#
# MUHIM: bu skript faqat `innova-m0` compose loyihasiga tegadi. Boshqa
# konteyner/tarmoq/image'larga TEGMAYDI. m0-proof.sh bilan BIR XIL stackka
# qarshi ishlaydi (ikkisini ketma-ket ishga tushirish xavfsiz — turli
# resurs nomlari/DID'lar ishlatiladi).
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"
SIPP_DIR="$ROOT_DIR/tests/sipp"
API_BASE="${API_BASE:-http://127.0.0.1:8710/api/v1}"
PROJECT="innova-m0"
NET="${PROJECT}_innova-net"
SIPP_IMAGE="python:3.12-slim"
UAC_IP="172.21.0.95"
UAS101_IP="172.21.0.96"
UAS102_IP="172.21.0.97"

ADMIN_PASSWORD="${PROOF_ADMIN_PASSWORD:-$(grep -E '^PROOF_ADMIN_PASSWORD=' "$DEPLOY_DIR/.env" | cut -d= -f2-)}"
[[ -n "$ADMIN_PASSWORD" ]] || { echo "PROOF_ADMIN_PASSWORD deploy/.env da yo'q"; exit 2; }

PASS=0
FAIL=0
pass() { echo "PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); }
# Xom CDR: shu DID qo'ng'irog'ida AYNAN shu ichki raqam leg'i ANSWERED bo'lsin (billsec emas — IVR Answer() dan sanaladi).
assert_leg_answered() {
  local did="$1" ext="$2" n
  n=$(docker exec innova-m0-postgres-1 psql -U innova -d innova -tAc \
    "select count(*) from cdr where userfield='$did' and dstchannel like 'PJSIP/$ext-%' and disposition='ANSWERED'")
  [[ "${n:-0}" -ge 1 ]] && pass "CDR: $did -> $ext leg ANSWERED" || fail "CDR: $did -> $ext ANSWERED leg yo'q"
}

cleanup_sipp() {
  docker rm -f innova-m1a-proof-uac innova-m1a-proof-uas101 innova-m1a-proof-uas102 >/dev/null 2>&1 || true
}
trap cleanup_sipp EXIT

if [[ "${1:-}" == "--fresh" ]]; then
  echo "--- --fresh: stack qayta quriladi ---"
  (cd "$DEPLOY_DIR" && docker compose down -v) || true
  (cd "$DEPLOY_DIR" && docker compose build) || { fail "docker compose build"; exit 1; }
  (cd "$DEPLOY_DIR" && docker compose up -d) || { fail "docker compose up"; exit 1; }
  echo "Konteynerlar tayyor bo'lishini kutish..."
  for i in $(seq 1 60); do
    curl -sf "${API_BASE%/api/v1}/healthz" >/dev/null 2>&1 && break
    sleep 2
  done
fi

echo "=== setup/login ==="
curl -s -o /tmp/m1aproof_setup.json -X POST "$API_BASE/setup" -H 'Content-Type: application/json' \
  -d '{"admin":{"login":"admin","password":"'"$ADMIN_PASSWORD"'","full_name":"Admin"},"language":"uz","timezone":"Asia/Tashkent"}' >/dev/null
LOGIN_JSON=$(curl -s -X POST "$API_BASE/auth/login" -H 'Content-Type: application/json' \
  -d '{"login":"admin","password":"'"$ADMIN_PASSWORD"'"}')
TOKEN=$(echo "$LOGIN_JSON" | python3 -c "import json,sys;print(json.load(sys.stdin).get('access',''))" 2>/dev/null)
if [[ -z "$TOKEN" ]]; then fail "login -> token yo'q ($LOGIN_JSON)"; exit 1; fi
AUTH=(-H "Authorization: Bearer $TOKEN")
echo "login OK"

api() { # method path [data]
  local method="$1" path="$2" data="${3:-}"
  if [[ -n "$data" ]]; then
    curl -s -w '\n%{http_code}' -X "$method" "$API_BASE$path" "${AUTH[@]}" -H 'Content-Type: application/json' -d "$data"
  else
    curl -s -w '\n%{http_code}' -X "$method" "$API_BASE$path" "${AUTH[@]}"
  fi
}
jbody() { echo "$1" | sed '$d'; }
jcode() { echo "$1" | tail -1; }
jget() { python3 -c "import json,sys;d=json.load(sys.stdin)
cur=d
for k in sys.argv[1:]:
    cur = cur[int(k)] if k.lstrip('-').isdigit() else cur.get(k)
print('' if cur is None else cur)" "${@:2}" <<<"$1"; }

target_id_by_kind_name() { # kind name -> call_targets id
  local kind="$1" name="$2"
  local r; r=$(curl -s "$API_BASE/targets?kind=$kind&q=$name" "${AUTH[@]}")
  python3 -c "
import json,sys
d=json.load(sys.stdin)
items=[i for i in d['items'] if i['label']=='$name']
print(items[0]['id'] if items else '')
" <<<"$r"
}

echo "=== resurslarni tayyorlash ==="
# --- Agentlar (ichki raqamlar) ---
EXT101_JSON=$(api POST /extensions '{"number":"101","name":"Agent101"}')
EXT101_SECRET=$(jget "$(jbody "$EXT101_JSON")" sip password)
EXT101_ID=$(jget "$(jbody "$EXT101_JSON")" item id)
EXT102_JSON=$(api POST /extensions '{"number":"102","name":"Agent102"}')
EXT102_SECRET=$(jget "$(jbody "$EXT102_JSON")" sip password)
EXT102_ID=$(jget "$(jbody "$EXT102_JSON")" item id)
EXT103_JSON=$(api POST /extensions '{"number":"103","name":"Agent103"}')
EXT103_ID=$(jget "$(jbody "$EXT103_JSON")" item id)
if [[ -n "$EXT101_ID" && -n "$EXT102_ID" && -n "$EXT103_ID" ]]; then
  pass "POST /extensions x3 (101,102,103) yaratildi"
else
  fail "POST /extensions -> 101=$EXT101_ID 102=$EXT102_ID 103=$EXT103_ID"
fi

# --- Trunk (SIPp UAC manbasiga ishonish uchun) ---
TRUNK_JSON=$(api POST /trunks "{\"name\":\"M1aTrunk\",\"host\":\"$UAC_IP\",\"port\":5060,\"match\":[\"$UAC_IP/32\"],\"codecs\":[\"ulaw\"],\"max_channels\":5,\"enabled\":true}")
TRUNK_ID=$(jget "$(jbody "$TRUNK_JSON")" item id)
if [[ -n "$TRUNK_ID" ]]; then pass "POST /trunks -> M1aTrunk yaratildi"; else fail "POST /trunks -> $TRUNK_JSON"; fi

# --- Tizim manzillari (hangup, migratsiyada avtomatik seed qilingan) ---
HANGUP_TARGET=$(python3 -c "
import json,sys
d=json.load(sys.stdin)
items=[i for i in d['items'] if i['kind']=='hangup']
print(items[0]['id'] if items else '')
" <<<"$(curl -s "$API_BASE/targets?kind=hangup" "${AUTH[@]}")")
[[ -n "$HANGUP_TARGET" ]] && pass "hangup tizim manzili topildi" || fail "hangup tizim manzili topilmadi"

# --- Tizim audio (salomlashuv) ---
AUDIO_ID=$(python3 -c "
import json,sys
d=json.load(sys.stdin)
print(d['items'][0]['id'] if d['items'] else '')
" <<<"$(curl -s "$API_BASE/audio" "${AUTH[@]}")")
[[ -n "$AUDIO_ID" ]] && pass "tizim audio namunasi topildi" || fail "tizim audio namunasi topilmadi"

# --- Navbat (Queue1: 101,102 a'zo) ---
QUEUE1_JSON=$(api POST /queues "{\"name\":\"M1aQueue1\",\"strategy\":\"ringall\",\"members\":[{\"extension_id\":\"$EXT101_ID\"},{\"extension_id\":\"$EXT102_ID\"}],\"timeout_target_id\":\"$HANGUP_TARGET\"}")
QUEUE1_ID=$(jget "$(jbody "$QUEUE1_JSON")" item id)
if [[ -n "$QUEUE1_ID" ]]; then pass "POST /queues -> M1aQueue1 yaratildi (101,102 a'zo)"; else fail "POST /queues -> $QUEUE1_JSON"; fi
QUEUE1_TARGET=$(target_id_by_kind_name queue M1aQueue1)

# --- IVR1 (DID -> IVR1, «1» -> Queue1) ---
IVR1_JSON=$(api POST /ivrs "{\"name\":\"M1aIvr1\",\"greeting_audio_id\":\"$AUDIO_ID\",\"timeout_seconds\":10,\"repeats\":1,\"options\":[{\"digit\":\"1\",\"target_id\":\"$QUEUE1_TARGET\"}],\"timeout_target_id\":\"$HANGUP_TARGET\",\"invalid_target_id\":\"$HANGUP_TARGET\"}")
IVR1_ID=$(jget "$(jbody "$IVR1_JSON")" item id)
if [[ -n "$IVR1_ID" ]]; then pass "POST /ivrs -> M1aIvr1 yaratildi (digit 1 -> navbat)"; else fail "POST /ivrs -> $IVR1_JSON"; fi
IVR1_TARGET=$(target_id_by_kind_name ivr M1aIvr1)

# --- TimeGroup (bo'sh ranges — force_open/force_closed ranges'ga qaramaydi) ---
TG_JSON=$(api POST /time-groups '{"name":"M1aTG","ranges":[]}')
TG_ID=$(jget "$(jbody "$TG_JSON")" item id)
[[ -n "$TG_ID" ]] && pass "POST /time-groups -> M1aTG yaratildi" || fail "POST /time-groups -> $TG_JSON"

# --- TimeCondition1 (force_open -> IVR1) ---
TC1_JSON=$(api POST /time-conditions "{\"name\":\"M1aTc1\",\"time_group_id\":\"$TG_ID\",\"open_target_id\":\"$IVR1_TARGET\",\"closed_target_id\":\"$HANGUP_TARGET\",\"override\":\"force_open\"}")
TC1_ID=$(jget "$(jbody "$TC1_JSON")" item id)
[[ -n "$TC1_ID" ]] && pass "POST /time-conditions -> M1aTc1 (force_open) yaratildi" || fail "POST /time-conditions -> $TC1_JSON"
TC1_TARGET=$(target_id_by_kind_name time_condition M1aTc1)

# --- TimeCondition2 (force_closed -> hangup) ---
TC2_JSON=$(api POST /time-conditions "{\"name\":\"M1aTc2\",\"time_group_id\":\"$TG_ID\",\"open_target_id\":\"$HANGUP_TARGET\",\"closed_target_id\":\"$HANGUP_TARGET\",\"override\":\"force_closed\"}")
TC2_ID=$(jget "$(jbody "$TC2_JSON")" item id)
[[ -n "$TC2_ID" ]] && pass "POST /time-conditions -> M1aTc2 (force_closed) yaratildi" || fail "POST /time-conditions -> $TC2_JSON"
TC2_TARGET=$(target_id_by_kind_name time_condition M1aTc2)

# --- RingGroup1 (102 a'zo) ---
RG1_JSON=$(api POST /ring-groups "{\"name\":\"M1aRg1\",\"strategy\":\"ringall\",\"ring_seconds\":15,\"members\":[{\"extension_id\":\"$EXT102_ID\"}],\"no_answer_target_id\":\"$HANGUP_TARGET\"}")
RG1_ID=$(jget "$(jbody "$RG1_JSON")" item id)
[[ -n "$RG1_ID" ]] && pass "POST /ring-groups -> M1aRg1 (102 a'zo) yaratildi" || fail "POST /ring-groups -> $RG1_JSON"
RG1_TARGET=$(target_id_by_kind_name ring_group M1aRg1)

# --- IVR2 (digitsiz, timeout -> RingGroup1) ---
IVR2_JSON=$(api POST /ivrs "{\"name\":\"M1aIvr2\",\"greeting_audio_id\":\"$AUDIO_ID\",\"timeout_seconds\":3,\"repeats\":0,\"options\":[],\"timeout_target_id\":\"$RG1_TARGET\",\"invalid_target_id\":\"$HANGUP_TARGET\"}")
IVR2_ID=$(jget "$(jbody "$IVR2_JSON")" item id)
[[ -n "$IVR2_ID" ]] && pass "POST /ivrs -> M1aIvr2 (timeout -> ring group) yaratildi" || fail "POST /ivrs -> $IVR2_JSON"
IVR2_TARGET=$(target_id_by_kind_name ivr M1aIvr2)

# --- Kiruvchi marshrutlar ---
DID1=712099301 DID2=712099302 DID3=712099303
R1_JSON=$(api POST /inbound-routes "{\"name\":\"M1aRoute1\",\"did\":\"$DID1\",\"target_id\":\"$TC1_TARGET\",\"enabled\":true}")
R1_CODE=$(jcode "$R1_JSON"); R1_APPLY=$(jget "$(jbody "$R1_JSON")" apply status)
[[ "$R1_CODE" == "201" && "$R1_APPLY" == "applied" ]] && pass "POST /inbound-routes -> $DID1 (TC1) applied" || fail "POST /inbound-routes $DID1 -> $R1_CODE/$R1_APPLY"

R2_JSON=$(api POST /inbound-routes "{\"name\":\"M1aRoute2\",\"did\":\"$DID2\",\"target_id\":\"$TC2_TARGET\",\"enabled\":true}")
R2_CODE=$(jcode "$R2_JSON"); R2_APPLY=$(jget "$(jbody "$R2_JSON")" apply status)
[[ "$R2_CODE" == "201" && "$R2_APPLY" == "applied" ]] && pass "POST /inbound-routes -> $DID2 (TC2) applied" || fail "POST /inbound-routes $DID2 -> $R2_CODE/$R2_APPLY"

R3_JSON=$(api POST /inbound-routes "{\"name\":\"M1aRoute3\",\"did\":\"$DID3\",\"target_id\":\"$IVR2_TARGET\",\"enabled\":true}")
R3_CODE=$(jcode "$R3_JSON"); R3_APPLY=$(jget "$(jbody "$R3_JSON")" apply status)
[[ "$R3_CODE" == "201" && "$R3_APPLY" == "applied" ]] && pass "POST /inbound-routes -> $DID3 (IVR2) applied" || fail "POST /inbound-routes $DID3 -> $R3_CODE/$R3_APPLY"

echo "=== ssenariy 4: IVR o'ziga (chiqishsiz) -> 422 loop ==="
IVR3_JSON=$(api POST /ivrs "{\"name\":\"M1aIvr3\",\"greeting_audio_id\":\"$AUDIO_ID\",\"timeout_seconds\":5,\"repeats\":0,\"options\":[],\"timeout_target_id\":\"$HANGUP_TARGET\",\"invalid_target_id\":\"$HANGUP_TARGET\"}")
IVR3_ID=$(jget "$(jbody "$IVR3_JSON")" item id)
IVR3_UPDATED_AT=$(jget "$(jbody "$IVR3_JSON")" item updated_at)
IVR3_TARGET=$(target_id_by_kind_name ivr M1aIvr3)
if [[ -n "$IVR3_ID" && -n "$IVR3_TARGET" ]]; then
  LOOP_JSON=$(api PATCH "/ivrs/$IVR3_ID" "{\"timeout_target_id\":\"$IVR3_TARGET\",\"updated_at\":\"$IVR3_UPDATED_AT\"}")
  LOOP_CODE=$(jcode "$LOOP_JSON")
  LOOP_ERR=$(jget "$(jbody "$LOOP_JSON")" error code)
  if [[ "$LOOP_CODE" == "422" && "$LOOP_ERR" == "loop" ]]; then
    pass "PATCH /ivrs/{id} (o'ziga chiqishsiz) -> 422 loop"
  else
    fail "PATCH /ivrs/{id} self-loop -> $LOOP_CODE/$LOOP_ERR ($(jbody "$LOOP_JSON"))"
  fi
else
  fail "ssenariy 4 tayyorlash muvaffaqiyatsiz (IVR3 yaratilmadi)"
fi

echo "=== ssenariy 5: navbatga a'zo qo'shish -> queue show reload'siz ==="
MEMBER_JSON=$(api POST "/queues/$QUEUE1_ID/members" "{\"extension_id\":\"$EXT103_ID\",\"penalty\":0}")
MEMBER_CODE=$(jcode "$MEMBER_JSON")
MEMBER_APPLY=$(jget "$(jbody "$MEMBER_JSON")" apply status)
if [[ "$MEMBER_CODE" == "201" && "$MEMBER_APPLY" == "realtime" ]]; then
  pass "POST /queues/{id}/members -> 201, apply.status=realtime (reload'siz)"
else
  fail "POST /queues/{id}/members -> $MEMBER_CODE/$MEMBER_APPLY"
fi
QUEUE1_NAME="t1-q-$QUEUE1_ID"
sleep 1
QSHOW=$(docker exec innova-m0-asterisk-1 asterisk -rx "queue show $QUEUE1_NAME" 2>&1)
if echo "$QSHOW" | grep -q "103"; then
  pass "queue show $QUEUE1_NAME -> 103 a'zo ko'rinadi (reload'siz)"
else
  fail "queue show $QUEUE1_NAME -> 103 topilmadi"
  echo "$QSHOW"
fi

echo "=== SIPp bilan HAQIQIY qo'ng'iroqlar (ssenariy 1,2,3) ==="
if ! command -v docker >/dev/null; then
  fail "docker topilmadi, SIPp isbotlari o'tkazib yuborildi"
else
  docker network inspect "$NET" >/dev/null 2>&1 || fail "tarmoq $NET topilmadi"

  docker run -d --name innova-m1a-proof-uac --network "$NET" --ip "$UAC_IP" "$SIPP_IMAGE" sleep infinity >/dev/null
  docker run -d --name innova-m1a-proof-uas101 --network "$NET" --ip "$UAS101_IP" "$SIPP_IMAGE" sleep infinity >/dev/null
  docker run -d --name innova-m1a-proof-uas102 --network "$NET" --ip "$UAS102_IP" "$SIPP_IMAGE" sleep infinity >/dev/null
  for c in innova-m1a-proof-uac innova-m1a-proof-uas101 innova-m1a-proof-uas102; do
    docker exec "$c" bash -c "apt-get update -qq && apt-get install -y -qq sip-tester >/tmp/i.log 2>&1"
  done
  docker cp "$SIPP_DIR/register_only.py" innova-m1a-proof-uas101:/tmp/register_only.py
  docker cp "$SIPP_DIR/options_responder.py" innova-m1a-proof-uas101:/tmp/options_responder.py
  docker cp "$SIPP_DIR/uas_only.xml" innova-m1a-proof-uas101:/tmp/uas_only.xml
  docker cp "$SIPP_DIR/register_only.py" innova-m1a-proof-uas102:/tmp/register_only.py
  docker cp "$SIPP_DIR/options_responder.py" innova-m1a-proof-uas102:/tmp/options_responder.py
  docker cp "$SIPP_DIR/uas_only.xml" innova-m1a-proof-uas102:/tmp/uas_only.xml
  docker cp "$SIPP_DIR/invite_reject_check.py" innova-m1a-proof-uac:/tmp/invite_reject_check.py
  # ikkinchi pauza (DTMF 200 OK'dan keyin, navbat a'zosi javob berishini kutish)
  # 2000ms'dan 8000ms'ga oshirildi — 101 bilan haqiqiy suhbat uchun yetarli
  # vaqt qoldiradi (quyidagi qualify tuzatishi bilan birga; CDR o'zi TO'G'RI
  # yoziladi, bu shunchaki ko'prik uchun qulay margin).
  sed "s/712000000/$DID1/; s/milliseconds=\"2000\"/milliseconds=\"8000\"/" "$SIPP_DIR/uac_ivr_dtmf.xml" > /tmp/m1aproof_uac_dtmf.xml
  docker cp /tmp/m1aproof_uac_dtmf.xml innova-m1a-proof-uac:/tmp/uac_ivr_dtmf.xml
  # pause ACK'dan keyin hisoblanadi (Answer() IVR boshida darhol ishlaydi,
  # ring group Dial() esa faqat IVR timeout_seconds(3s)dan KEYIN boshlanadi) —
  # pause juda qisqa bo'lsa (sinovda topilgan: 7000ms), UAC ring group Dial()
  # hali boshlanmasdan BYE yuborib qo'yadi va qo'ng'iroq hech qachon 102'ga
  # ulanmaydi. 16000ms — 3s IVR kutish + Dial ulanishi + yetarli suhbat vaqti.
  sed "s/712000000/$DID3/; s/1500/16000/" "$SIPP_DIR/uac_trunk_invite.xml" > /tmp/m1aproof_uac_rg.xml
  docker cp /tmp/m1aproof_uac_rg.xml innova-m1a-proof-uac:/tmp/uac_rg_wait.xml

  register_and_qualify() {
    local cont="$1" uas_ip="$2" ext="$3" secret="$4"
    local out; out=$(docker exec "$cont" python3 /tmp/register_only.py asterisk 5060 5080 "$ext" "$secret" 3600 5080)
    echo "$out" | grep -q "REGISTER OK"
    local ok=$?
    docker exec -d "$cont" python3 /tmp/options_responder.py "$uas_ip" 5080 20
    sleep 0.5
    docker exec innova-m0-asterisk-1 asterisk -rx "pjsip qualify $ext" >/dev/null
    sleep 1
    return $ok
  }

  if register_and_qualify innova-m1a-proof-uas101 "$UAS101_IP" 101 "$EXT101_SECRET"; then
    pass "SIPp REGISTER 101 -> 200 OK"
  else
    fail "SIPp REGISTER 101 muvaffaqiyatsiz"
  fi
  if register_and_qualify innova-m1a-proof-uas102 "$UAS102_IP" 102 "$EXT102_SECRET"; then
    pass "SIPp REGISTER 102 -> 200 OK"
  else
    fail "SIPp REGISTER 102 muvaffaqiyatsiz"
  fi

  # ASL SABAB (koordinator ko'rsatgan `Endpoint 101/102 is now Unreachable`
  # logi orqali topildi, --fresh muhitda reload ko'p endpoint'ni bir vaqtda
  # qayta yuklagani uchun): pjsip.conf [global] max_initial_qualify_time=5 —
  # reload/ro'yxatdan o'tishdan keyin Asterisk har bir endpoint uchun yana BIR
  # avtomatik qualify (OPTIONS) ni ~0-5s oralig'ida rejalashtiradi. Agar bu
  # oraliqda biz allaqachon haqiqiy chaqiruv stsenariysini (`uas_only.xml`) BIR
  # XIL portga ishga tushirgan bo'lsak, SIPp uni OPTIONS so'roviga javob
  # bermaydi (faqat INVITE kutadi) — Asterisk kontaktni "Unreachable" deb
  # belgilaydi VA aynan shu payt davom etayotgan chaqiruvning javob holati
  # buzilgan edi (CDR disposition emas, MAHSULOT xatosi ham emas — bu test
  # muhitining qualify poygasi). Tuzatish: bu 5s oynasi hali OPTIONS-only
  # `options_responder.py` ISHLAB TURGANDA (MAX_SECONDS=20) xavfsiz o'tishi
  # uchun yetarli kutamiz, SO'NGRA haqiqiy SIPp stsenariysini ishga tushiramiz.
  sleep 6

  echo "--- ssenariy 1: force_open -> IVR -> «1» -> navbat -> 101 javob beradi ---"
  docker exec innova-m1a-proof-uas101 bash -c "for p in /proc/[0-9]*; do pid=\$(basename \$p); readlink \$p/exe 2>/dev/null | grep -q python && kill -9 \$pid 2>/dev/null; done"
  docker exec -d innova-m1a-proof-uas101 sipp -sf /tmp/uas_only.xml -i "$UAS101_IP" -p 5080 -m 1 -timeout 60s
  sleep 0.3
  UAC1_OUT=$(docker exec innova-m1a-proof-uac sipp -sf /tmp/uac_ivr_dtmf.xml -i "$UAC_IP" -p 5080 asterisk:5060 -m 1 -timeout 30s 2>&1 || true)
  OK1=$(echo "$UAC1_OUT" | grep "Successful call" | tail -1 | grep -oE '[0-9]+' | tail -1)
  FAIL1=$(echo "$UAC1_OUT" | grep "^  Failed call" | tail -1 | grep -oE '[0-9]+' | tail -1)
  if [[ "${OK1:-0}" -ge 1 && "${FAIL1:-0}" -eq 0 ]]; then
    pass "SIPp UAC IVR+DTMF $DID1 -> Successful call: $OK1"
  else
    fail "SIPp UAC IVR+DTMF $DID1 natijasi: successful=$OK1 failed=$FAIL1"
    echo "$UAC1_OUT" | tail -15
  fi
  CALLS1=$(curl -s "$API_BASE/calls" "${AUTH[@]}")
  FOUND1=$(python3 -c "
import json,sys
d=json.load(sys.stdin)
print('yes' if any(i.get('did')=='$DID1' and i.get('disposition')=='answered' for i in d.get('items',[])) else 'no')
" <<<"$CALLS1")
  [[ "$FOUND1" == "yes" ]] && pass "GET /calls -> $DID1 disposition=answered" || fail "GET /calls -> $DID1/answered topilmadi"
  assert_leg_answered "$DID1" 101

  echo "--- ssenariy 2: force_closed -> hangup -> CDR rejected ---"
  REJECT_OUT=$(docker exec innova-m1a-proof-uac python3 /tmp/invite_reject_check.py asterisk 5060 5082 "$DID2" "$UAC_IP" 2>&1)
  if echo "$REJECT_OUT" | grep -q "^FINAL:" && ! echo "$REJECT_OUT" | grep -q "200"; then
    pass "INVITE $DID2 (force_closed) -> rad etildi ($REJECT_OUT)"
  else
    fail "INVITE $DID2 (force_closed) -> kutilmagan natija ($REJECT_OUT)"
  fi
  sleep 1
  CALLS2=$(curl -s "$API_BASE/calls" "${AUTH[@]}")
  FOUND2=$(python3 -c "
import json,sys
d=json.load(sys.stdin)
print('yes' if any(i.get('did')=='$DID2' and i.get('disposition')!='answered' for i in d.get('items',[])) else 'no')
" <<<"$CALLS2")
  [[ "$FOUND2" == "yes" ]] && pass "GET /calls -> $DID2 disposition!=answered (rad etilgan)" || fail "GET /calls -> $DID2 rad etilgan yozuv topilmadi"

  echo "--- ssenariy 3: IVR timeout -> ring group -> 102 javob beradi ---"
  docker exec innova-m1a-proof-uas102 bash -c "for p in /proc/[0-9]*; do pid=\$(basename \$p); readlink \$p/exe 2>/dev/null | grep -q python && kill -9 \$pid 2>/dev/null; done"
  docker exec -d innova-m1a-proof-uas102 sipp -sf /tmp/uas_only.xml -i "$UAS102_IP" -p 5080 -m 1 -timeout 60s
  sleep 0.3
  UAC3_OUT=$(docker exec innova-m1a-proof-uac sipp -sf /tmp/uac_rg_wait.xml -i "$UAC_IP" -p 5081 asterisk:5060 -m 1 -timeout 30s 2>&1 || true)
  OK3=$(echo "$UAC3_OUT" | grep "Successful call" | tail -1 | grep -oE '[0-9]+' | tail -1)
  FAIL3=$(echo "$UAC3_OUT" | grep "^  Failed call" | tail -1 | grep -oE '[0-9]+' | tail -1)
  if [[ "${OK3:-0}" -ge 1 && "${FAIL3:-0}" -eq 0 ]]; then
    pass "SIPp UAC IVR timeout+ring group $DID3 -> Successful call: $OK3"
  else
    fail "SIPp UAC IVR timeout+ring group $DID3 natijasi: successful=$OK3 failed=$FAIL3"
    echo "$UAC3_OUT" | tail -15
  fi
  # TUZATILDI (koordinator topgan, ikkala avvalgi xulosa ham NOTO'G'RI edi):
  # 1) "disposition hech qachon ANSWERED bo'lmaydi, billsec tekshiramiz" —
  #    TEST ICHIDA SOXTA PASS edi (haqiqiy javobni emas, uzoq ko'prikni
  #    tekshirardi). 2) "bu Asterisk'ning Answer()+Dial() CDR xususiyati,
  #    tuzatish `h`-extension + Set(CDR(disposition)=...) talab qiladi" —
  #    BU HAM NOTO'G'RI edi: koordinator ko'rsatganidek, dialplan/kompilyator
  #    CDR()ga HECH QACHON yozmasligi SHART (haqiqiy javobni soxtalashtirish
  #    bo'lardi). ASL SABAB — yuqoridagi pjsip qualify poygasi edi: 102 haqiqatan
  #    javob bergan bo'lsa ham, davom etayotgan chaqiruv paytida kelgan avtomatik
  #    OPTIONS (`max_initial_qualify_time`) kontaktni vaqtincha "Unreachable"ga
  #    o'tkazib, Asterisk'ning native CDR yozuvini buzgan. Qualify poygasi olib
  #    tashlangandan keyin Asterisk'ning O'ZI `disposition=ANSWERED`ni TO'G'RI
  #    yozadi — `/calls` esa buni (`_call_out_from_group`) xom CDR'dan, HECH
  #    QANDAY dialplan o'zgarishisiz, guruhlab oladi.
  # CDR yozuvi qo'ng'iroq tugagach biroz kechikib tushadi (yuklamada 1 s dan oshadi) — 10 s gacha so'raymiz.
  FOUND3=no
  for _ in $(seq 1 20); do
    CALLS3=$(curl -s "$API_BASE/calls" "${AUTH[@]}")
    FOUND3=$(python3 -c "
import json,sys
d=json.load(sys.stdin)
print('yes' if any(i.get('did')=='$DID3' and i.get('disposition')=='answered' for i in d.get('items',[])) else 'no')
" <<<"$CALLS3")
    [[ "$FOUND3" == "yes" ]] && break
    sleep 0.5
  done
  [[ "$FOUND3" == "yes" ]] && pass "GET /calls -> $DID3 disposition=answered (102 javob berdi)" || fail "GET /calls -> $DID3/answered topilmadi"
  assert_leg_answered "$DID3" 102
fi

echo
echo "=== NATIJA: PASS=$PASS FAIL=$FAIL ==="
[[ "$FAIL" -eq 0 ]]
