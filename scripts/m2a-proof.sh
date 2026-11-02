#!/usr/bin/env bash
# Innova PBX — M2a proof skripti (replica/m2a-contract.md §6):
#   1. DND (API) -> 201 ga 486; 201 `*76` -> dnd=false; yana qo'ng'iroq -> 201 javob beradi.
#   2. `*72203` -> 201 ga qo'ng'iroq 203 da; `*73` -> yana 201. Tashqi yo'naltirish -> trunk UAS INVITE oladi;
#      `outbound_allowed=false` ext'ning tashqi yo'naltirishi trunkka CHIQMAYDI.
#   3. forward_busy: 201 band (486) -> 203 ga o'tadi.
#   4. Qora ro'yxat — KEYINGI agent (`scripts/lib/m2a_blacklist_scenario.sh`, bo'lsa ishlaydi).
#   5. Pickup: 202 -> 201 jiringlayapti, 203 (bir guruh) `*8` -> 202 bilan ulanadi; `**201` ham.
#   6. Blind transfer: 202<->201, 201 `##203` (SIP INFO DTMF) -> 202 va 203 ulanadi.
#   7. Park: 201 `##700` -> GET /parking 1 ta; 203 `701` -> ulanadi; parked bo'shaydi.
#   8. Konferensiya — KEYINGI agent (`scripts/lib/m2a_conference_scenario.sh`, bo'lsa ishlaydi).
#   9. Xususiyat kodi dnd_toggle -> `*77` (apply): `*77` ishlaydi, `*76` yo'q; prefiks to'qnashuvi 409.
#
# Foydalanish:
#   scripts/m2a-proof.sh            # joriy `innova-m0` stackka qarshi (M2a qoldiqlari bo'lsa — exit 2)
#   scripts/m2a-proof.sh --fresh    # avval `docker compose down -v` + qayta build + up -d
#
# MUHIM: faqat `innova-m0` compose loyihasiga tegadi; o'z konteynerlarini (m2a-proof-*) oxirida o'chiradi.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"
SIPP_DIR="$ROOT_DIR/tests/sipp"
LIB_DIR="$ROOT_DIR/scripts/lib"
API_BASE="${API_BASE:-http://127.0.0.1:8710/api/v1}"
PROJECT="innova-m0"
NET="${PROJECT}_innova-net"
PY_IMAGE="python:3.12-slim"
PG=innova-m0-postgres-1
AST=innova-m0-asterisk-1

declare -A IP=([201]="172.21.0.170" [202]="172.21.0.171" [203]="172.21.0.172" [trunk]="172.21.0.173")
EXT_NUMBER="998901112233"   # tashqi yo'naltirish raqami (marshrut 998XXXXXXXXX -> M2aTrunk)

# shellcheck source=lib/m2a_common.sh
source "$LIB_DIR/m2a_common.sh"

ADMIN_PASSWORD="${PROOF_ADMIN_PASSWORD:-$(grep -E '^PROOF_ADMIN_PASSWORD=' "$DEPLOY_DIR/.env" | cut -d= -f2-)}"
[[ -n "$ADMIN_PASSWORD" ]] || { echo "PROOF_ADMIN_PASSWORD deploy/.env da yo'q"; exit 2; }

CONTAINERS=(m2a-proof-201 m2a-proof-202 m2a-proof-203 m2a-proof-trunk)
cleanup() { docker rm -f "${CONTAINERS[@]}" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

if [[ "${1:-}" == "--fresh" ]]; then
  echo "--- --fresh: stack qayta quriladi ---"
  (cd "$DEPLOY_DIR" && docker compose down -v) || true
  (cd "$DEPLOY_DIR" && docker compose build) || { fail "docker compose build"; exit 1; }
  (cd "$DEPLOY_DIR" && docker compose up -d) || { fail "docker compose up"; exit 1; }
  echo "Konteynerlar tayyor bo'lishini kutish..."
  wait_api
fi

echo "=== setup/login ==="
login "$ADMIN_PASSWORD" || { fail "login"; exit 1; }
echo "login OK"

LEFTOVER=$(jget "$(jbody "$(api GET "/extensions?q=M2a")")" total 2>/dev/null)
if [[ -n "$LEFTOVER" && "$LEFTOVER" != "0" ]]; then
  echo "Stekda oldingi M2a isbot qoldiqlari bor ($LEFTOVER ext) — 'scripts/m2a-proof.sh --fresh' bilan ishga tushiring."
  exit 2
fi

# ---------------------------------------------------------------- resurslar
echo "=== resurslar ==="
declare -A EXT_ID SECRET
for n in 201 202 203; do
  j=$(jbody "$(api POST /extensions "{\"number\":\"$n\",\"name\":\"M2a$n\"}")")
  EXT_ID[$n]=$(jget "$j" item id); SECRET[$n]=$(jget "$j" sip password)
done
[[ -n "${EXT_ID[201]}" && -n "${EXT_ID[202]}" && -n "${EXT_ID[203]}" ]] \
  && pass "POST /extensions -> 201, 202, 203" || fail "extensions -> ${EXT_ID[*]}"
TRUNK=$(jbody "$(api POST /trunks "{\"name\":\"M2aTrunk\",\"host\":\"${IP[trunk]}\",\"port\":5060,\"match\":[\"${IP[trunk]}/32\"],\"codecs\":[\"ulaw\"],\"max_channels\":5,\"enabled\":true}")")
TRUNK_ID=$(jget "$TRUNK" item id)
ROUTE=$(api POST /outbound-routes "{\"name\":\"M2aRoute\",\"priority\":1,\"patterns\":[{\"pattern\":\"998XXXXXXXXX\"}],\"trunk_ids\":[\"$TRUNK_ID\"],\"international\":false}")
check "$( [[ -n "$TRUNK_ID" && "$(jcode "$ROUTE")" == "201" ]]; echo $?)" "trunk M2aTrunk + marshrut 998XXXXXXXXX" "$TRUNK / $ROUTE"

RESERVED=$(api POST /extensions '{"number":"701","name":"M2aReserved"}')
check "$( [[ "$(jcode "$RESERVED")" == "409" && "$(jget "$(jbody "$RESERVED")" error code)" == "number_taken" ]] && grep -q '"reserved"' <<<"$RESERVED"; echo $?)" \
  "POST /extensions 701 -> 409 number_taken (reserved)" "$RESERVED"
check "$(ast "parking show t1-park" | grep -q "701-720"; echo $?)" "Asterisk: park lot t1-park (701-720)" "$(ast "parking show t1-park")"
FEAT=$(ast "features show" | awk '/^(Blind|Attended) Transfer/{printf "%s=%s ", $1, $NF}')
check "$( [[ "$FEAT" == "Blind=## Attended=*2 " ]]; echo $?)" "features.conf: blind ##, attended *2 (joriy)" "$FEAT"

echo "=== telefonlar ==="
for c in 201 202 203 trunk; do
  docker run -d --name "m2a-proof-$c" --network "$NET" --ip "${IP[$c]}" "$PY_IMAGE" sleep infinity >/dev/null
  for f in outbound_invite.py vm_caller.py m2a_phone.py; do docker cp "$SIPP_DIR/$f" "m2a-proof-$c:/tmp/$f"; done
done
for n in 201 202 203; do
  docker exec -d "m2a-proof-$n" sh -c "cd /tmp && python3 m2a_phone.py serve $n '${SECRET[$n]}' 5070 12000 /tmp/mode 520 > /tmp/phone.log 2>&1"
done
docker exec m2a-proof-trunk sh -c "echo busy > /tmp/mode"
docker exec -d m2a-proof-trunk sh -c "cd /tmp && python3 m2a_phone.py serve trunk - 5060 12000 /tmp/mode 520 > /tmp/phone.log 2>&1"
registered() { for n in 201 202 203; do docker exec "m2a-proof-$n" grep -q 'REGISTER_RESULT: OK' /tmp/phone.log 2>/dev/null || return 1; done; }
wait_until 15 registered && pass "201, 202, 203 REGISTER -> 200 OK" || fail "REGISTER -> $(docker exec m2a-proof-201 cat /tmp/phone.log)"

mode() { docker exec "m2a-proof-$1" sh -c "echo '$2' > /tmp/mode"; }
plog() { docker exec "m2a-proof-$1" cat /tmp/phone.log 2>/dev/null; }
invites() { plog "$1" | grep -c '^INVITE '; }
last_invite() { plog "$1" | grep '^INVITE ' | tail -1; }
count_of() { plog "$1" | grep -c "^$2"; }
CALL_N=0
place_call() { # ext dialed talk_s [dtmf] -> $OUT (sinxron)
  CALL_N=$((CALL_N + 1))
  OUT=$(docker exec "m2a-proof-$1" sh -c "cd /tmp && python3 m2a_phone.py call $1 '${SECRET[$1]}' $((5100 + CALL_N)) $((13000 + CALL_N * 2)) '$2' $3 '${4:-}'" 2>&1)
}
place_call_bg() { # nom ext dialed talk_s [dtmf] -> /tmp/<nom>.log (fon)
  CALL_N=$((CALL_N + 1))
  docker exec -d "m2a-proof-$2" sh -c "cd /tmp && python3 m2a_phone.py call $2 '${SECRET[$2]}' $((5100 + CALL_N)) $((13000 + CALL_N * 2)) '$3' $4 '${5:-}' > /tmp/$1.log 2>&1"
}
call_log() { docker exec "m2a-proof-$1" cat "/tmp/$2.log" 2>/dev/null; }
call_done() { call_log "$1" "$2" | grep -Eq 'BYE_SENT|REMOTE_BYE|INVITE_FINAL: SIP/2.0 [3-6]'; }
final_of() { sed -n 's/^INVITE_FINAL: SIP\/2.0 \([0-9]*\).*/\1/p' <<<"$1"; }
ext_item() { # raqam -> GET /extensions dagi item JSON
  jbody "$(api GET "/extensions?q=$1")" | python3 -c "
import json,sys
print(json.dumps(next(i for i in json.load(sys.stdin)['items'] if i['number']==sys.argv[1])))" "$1"
}
ext_field() { jget "$(ext_item "$1")" "$2"; }
ext_patch() { # raqam json_qismi -> $PATCH_OUT
  local stamp
  stamp=$(ext_field "$1" updated_at)
  PATCH_OUT=$(api PATCH "/extensions/${EXT_ID[$1]}" "{${2},\"updated_at\":\"$stamp\"}")
}

# ---------------------------------------------------------------- 1
echo "--- 1. DND ---"
ext_patch 201 '"dnd":true'
check "$( [[ "$(jcode "$PATCH_OUT")" == "200" && "$(jget "$(jbody "$PATCH_OUT")" apply status)" == "applied" && -z "$(jget "$(jbody "$PATCH_OUT")" apply revision)" && "$(jget "$(jbody "$PATCH_OUT")" item dnd)" == "True" ]]; echo $?)" \
  "1: PATCH dnd=true -> apply=applied, revision=null (realtime)" "$PATCH_OUT"
check "$( [[ "$(sql "select dnd from asterisk_ext_state where endpoint='201'")" == "t" ]]; echo $?)" "1: asterisk_ext_state 201 dnd=t"
B201=$(invites 201)
place_call 202 201 1
check "$( [[ "$(final_of "$OUT")" == "486" && "$(invites 201)" == "$B201" ]]; echo $?)" "1: DND -> 202 -> 201: 486 Busy, 201 jiringlamadi" "$OUT"
place_call 201 '*76' 6
check "$( [[ "$(final_of "$OUT")" == "200" && "$(ext_field 201 dnd)" == "False" ]]; echo $?)" "1: 201 *76 -> GET /extensions dnd=false" "$OUT / dnd=$(ext_field 201 dnd)"
mode 201 answer
place_call 202 201 1
check "$( [[ "$(final_of "$OUT")" == "200" && "$(invites 201)" == "$((B201 + 1))" ]]; echo $?)" "1: DND o'chgach 202 -> 201 javob berdi" "$OUT"

# ---------------------------------------------------------------- 2
echo "--- 2. forward_always ---"
place_call 201 '*72203' 6
check "$( [[ "$(final_of "$OUT")" == "200" && "$(ext_field 201 forward_always)" == "203" ]]; echo $?)" "2: 201 *72203 -> forward_always=203" "$OUT / $(ext_field 201 forward_always)"
mode 203 answer; B201=$(invites 201); B203=$(invites 203)
place_call 202 201 1
check "$( [[ "$(final_of "$OUT")" == "200" && "$(invites 203)" == "$((B203 + 1))" && "$(invites 201)" == "$B201" ]] && grep -q "from=202" <<<"$(last_invite 203)"; echo $?)" \
  "2: 202 -> 201 -> 203 da jiringladi (201 emas)" "$OUT / $(last_invite 203)"
place_call 201 '*73' 5
check "$( [[ "$(final_of "$OUT")" == "200" && -z "$(ext_field 201 forward_always)" ]]; echo $?)" "2: 201 *73 -> forward_always=null" "$OUT"
place_call 202 201 1
check "$( [[ "$(invites 201)" == "$((B201 + 1))" ]]; echo $?)" "2: *73 dan keyin 202 -> 201 (yana 201)" "$OUT"
ext_patch 201 "\"forward_always\":\"$EXT_NUMBER\""
BT=$(invites trunk)
place_call 202 201 1
check "$( [[ "$(jget "$(jbody "$PATCH_OUT")" apply status)" == "applied" && "$(invites trunk)" == "$((BT + 1))" ]] && grep -q "ruri=sip:$EXT_NUMBER@" <<<"$(last_invite trunk)"; echo $?)" \
  "2: tashqi yo'naltirish ($EXT_NUMBER) -> trunk UAS INVITE oldi" "$OUT / $(last_invite trunk)"
ext_patch 201 '"outbound_allowed":false'
BT=$(invites trunk)
place_call 202 201 1
check "$( [[ "$(jcode "$PATCH_OUT")" == "200" && "$(invites trunk)" == "$BT" && "$(final_of "$OUT")" != "200" ]]; echo $?)" \
  "2: outbound_allowed=false -> yo'naltirish trunkka CHIQMADI ($(final_of "$OUT"))" "$OUT / $(last_invite trunk)"
ext_patch 201 '"outbound_allowed":true,"forward_always":null'
check "$( [[ -z "$(jget "$(jbody "$PATCH_OUT")" item forward_always)" ]]; echo $?)" "2: forward_always=null (tozalash)" "$PATCH_OUT"

# ---------------------------------------------------------------- 3
echo "--- 3. forward_busy ---"
mode 201 busy; mode 203 busy
ext_patch 201 '"forward_busy":"203"'
B201=$(invites 201); B203=$(invites 203)
place_call 202 201 1
check "$( [[ "$(invites 201)" == "$((B201 + 1))" && "$(invites 203)" == "$((B203 + 1))" ]] && grep -q "from=202" <<<"$(last_invite 203)"; echo $?)" \
  "3: 201 band (486) -> 203 ga o'tdi" "$OUT / $(last_invite 203)"
ext_patch 201 '"forward_busy":null'

# ---------------------------------------------------------------- 4
echo "--- 4. qora ro'yxat ---"
if [[ -f "$LIB_DIR/m2a_blacklist_scenario.sh" ]]; then
  # shellcheck source=/dev/null
  source "$LIB_DIR/m2a_blacklist_scenario.sh"
else
  echo "SKIP: 4 — keyingi agent (scripts/lib/m2a_blacklist_scenario.sh)"
fi

# ---------------------------------------------------------------- 5
echo "--- 5. pickup ---"
ext_patch 201 '"pickup_group":"sales"'; ext_patch 203 '"pickup_group":"sales"'
check "$( [[ "$(sql "select named_call_group||'/'||named_pickup_group from ps_endpoints where id='203'")" == "t1-sales/t1-sales" ]]; echo $?)" \
  "5: ps_endpoints 203 named_call/pickup_group = t1-sales"
mode 201 ring
pickup_case() { # nom terilgan_kod
  local b201 bc
  b201=$(invites 201); bc=$(count_of 201 "REQ CANCEL")
  place_call_bg "$1a" 202 201 6
  wait_until 10 sh -c "[ \$(docker exec m2a-proof-201 grep -c '^INVITE ' /tmp/phone.log) -gt $b201 ]"
  place_call_bg "$1b" 203 "$2" 4
  wait_until 10 bridged 202 203 && pass "5: $2 -> 203 javob berdi va 202 bilan ulandi (bridge)" \
    || fail "5: $2 -> bridge 202/203 yo'q ($(ast 'core show channels concise'))"
  wait_until 15 call_done 202 "$1a"
  check "$(grep -q 'INVITE_FINAL: SIP/2.0 200' <<<"$(call_log 202 "$1a")" && grep -q 'INVITE_FINAL: SIP/2.0 200' <<<"$(call_log 203 "$1b")" && [[ "$(count_of 201 "REQ CANCEL")" -gt "$bc" ]]; echo $?)" \
    "5: $2: 202 va 203 -> 200 OK, 201 ga CANCEL" "$(call_log 202 "$1a") / $(call_log 203 "$1b")"
}
pickup_case p8 '*8'
pickup_case pd '**201'

# ---------------------------------------------------------------- 6
echo "--- 6. blind transfer ##203 ---"
mode 201 'answer:##,,203'; mode 203 answer
B203=$(invites 203); BB=$(count_of 201 "REQ BYE")
place_call_bg x6 202 201 16
wait_until 10 sh -c "docker exec m2a-proof-201 grep -c XFER_SENT /tmp/phone.log | grep -qv '^0$'"
wait_until 15 bridged 202 203 && pass "6: 201 ##203 -> 202 va 203 ulandi (bridge)" \
  || fail "6: ##203 -> bridge 202/203 yo'q ($(plog 201 | tail -5); $(ast 'core show channels concise'))"
check "$( [[ "$(invites 203)" == "$((B203 + 1))" && "$(count_of 201 "REQ BYE")" -gt "$BB" ]] && grep -q "from=202" <<<"$(last_invite 203)"; echo $?)" \
  "6: 203 INVITE (from=202), 201 chaqiruvdan chiqdi (BYE)" "$(last_invite 203)"
wait_until 20 call_done 202 x6

# ---------------------------------------------------------------- 7
echo "--- 7. park ##700 ---"
mode 201 'answer:##,,700'
parked_n() { jbody "$(api GET /parking)" | python3 -c "import json,sys;print(len(json.load(sys.stdin)['parked']))"; }
parked_is() { [[ "$(parked_n)" == "$1" ]]; }
place_call_bg x7 202 201 40
wait_until 15 parked_is 1
PARK=$(jbody "$(api GET /parking)")
check "$(python3 -c "
import json,sys
d=json.load(sys.stdin); p=d['parked']
ok = d['lot']=='700' and d['slots']=='701-720' and d['timeout_s']==60 and len(p)==1 \
     and p[0]['slot']=='701' and p[0]['callerid']=='202' and p[0]['parked_by']=='201' and p[0]['since']
sys.exit(0 if ok else 1)" <<<"$PARK"; echo $?)" "7: ##700 -> GET /parking: 701 (callerid 202, parked_by 201)" "$PARK"
place_call_bg r7 203 701 4
wait_until 10 bridged 202 203 && pass "7: 203 701 -> 202 bilan ulandi" || fail "7: 701 -> bridge yo'q ($(ast 'core show channels concise'))"
check "$(wait_until 5 parked_is 0; echo $?)" "7: GET /parking parked bo'shadi" "$(jbody "$(api GET /parking)")"
wait_until 15 call_done 202 x7

# ---------------------------------------------------------------- 8
echo "--- 8. konferensiya ---"
if [[ -f "$LIB_DIR/m2a_conference_scenario.sh" ]]; then
  # shellcheck source=/dev/null
  source "$LIB_DIR/m2a_conference_scenario.sh"
else
  echo "SKIP: 8 — keyingi agent (scripts/lib/m2a_conference_scenario.sh)"
fi

# ---------------------------------------------------------------- 9
echo "--- 9. xususiyat kodlari ---"
FC=$(jbody "$(api GET /feature-codes)")
check "$(python3 -c "
import json,sys
items=json.load(sys.stdin)['items']
order=['voicemail','voicemail_other','dnd_toggle','cf_always_on','cf_always_off','cf_busy_on','cf_busy_off','pickup_group','pickup_direct','park','echo_test','speaking_clock','queue_login','queue_pause','followme_toggle']
sys.exit(0 if [i['feature'] for i in items]==order and items[2]=={'feature':'dnd_toggle','code':'*76','default_code':'*76','enabled':True} else 1)" <<<"$FC"; echo $?)" \
  "9: GET /feature-codes -> 15 ta, kontrakt tartibida (M2b: +queue_login/+queue_pause, M5b: +followme_toggle)" "$FC"
FCP=$(api PATCH /feature-codes/dnd_toggle '{"code":"*77"}')
check "$( [[ "$(jcode "$FCP")" == "200" && "$(jget "$(jbody "$FCP")" item code)" == "*77" && "$(jget "$(jbody "$FCP")" apply status)" == "applied" ]]; echo $?)" \
  "9: PATCH dnd_toggle *77 -> apply=applied" "$FCP"
place_call 201 '*77' 5
check "$( [[ "$(final_of "$OUT")" == "200" && "$(ext_field 201 dnd)" == "True" ]]; echo $?)" "9: 201 *77 -> dnd=true" "$OUT"
place_call 201 '*76' 3
check "$( [[ "$(final_of "$OUT")" != "200" && "$(ext_field 201 dnd)" == "True" ]]; echo $?)" "9: *76 endi ishlamaydi ($(final_of "$OUT")), dnd o'zgarmadi" "$OUT"
FCX=$(api PATCH /feature-codes/echo_test '{"code":"*7"}')
check "$( [[ "$(jcode "$FCX")" == "409" && "$(jget "$(jbody "$FCX")" error code)" == "code_taken" ]]; echo $?)" "9: echo_test *7 (prefiks *77/*72) -> 409 code_taken" "$FCX"
FCB=$(api PATCH /feature-codes/echo_test '{"code":"43"}')
check "$( [[ "$(jcode "$FCB")" == "422" && "$(jget "$(jbody "$FCB")" error code)" == "bad_code" ]]; echo $?)" "9: kod '43' -> 422 bad_code" "$FCB"
FCR=$(api POST /feature-codes/dnd_toggle/reset)
check "$( [[ "$(jcode "$FCR")" == "200" && "$(jget "$(jbody "$FCR")" item code)" == "*76" ]]; echo $?)" "9: reset -> *76" "$FCR"
place_call 201 '*76' 5
check "$( [[ "$(final_of "$OUT")" == "200" && "$(ext_field 201 dnd)" == "False" ]]; echo $?)" "9: reset'dan keyin *76 -> dnd=false" "$OUT"

echo "=== NATIJA: PASS=$PASS FAIL=$FAIL ==="
[[ "$FAIL" -eq 0 ]]
