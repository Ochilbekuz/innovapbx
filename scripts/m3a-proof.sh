#!/usr/bin/env bash
# Innova PBX — M3a proof (replica/m3a-contract.md §5): brauzer softfoni, HAQIQIY Chromium bilan.
#   1. web darvozasi: / 200, /api/v1/system/health 401 JSON, /internal/x 404, /sip-ws ticketsiz/buzuq 401, ticket bilan 101 sip.
#   2. 101, 103 webrtc (operator A, B brauzerda) -> chip registered + ws kontaktlar; C (102, oddiy SIP) -> chip yo'q, 409.
#   3. Brauzer<->brauzer: A -> 103, B javob; ikkala tomonda packetsSent/Received > 50 (DTLS-SRTP); CDR ANSWERED, billsec >= 2.
#   4. Brauzer -> SIP UAS (102) va SIP -> brauzer (102 -> 101), CDR ANSWERED.
#   5. Mute (qarshi tomonda audio energiya o'smaydi), hold (Asterisk MOH), DTMF (IVR 1 -> 102), blind transfer (B -> 102).
#   6. Navbat (a'zo 103): trunkdan kiruvchi -> B javob -> GET /live da agent busy.
#   7. TTL=5 s ticket eskirgach 401; WS orqali noto'g'ri parol x10 -> nginx IP ip_bans'da YO'Q, A hamon registered.
#   8. Admin 101 da webrtc=false -> /me/softphone 409, A chipi <= 60 s ichida yo'qoladi.
#   (+) `web/scripts/m3a-real-check.mjs` skrinshotlari (light+dark).
#
# Foydalanish:
#   scripts/m3a-proof.sh            # joriy `innova-m0` stack (M3a qoldiqlari bo'lsa — exit 2)
#   scripts/m3a-proof.sh --fresh    # avval `docker compose down -v` + build + up -d
# Talab: node + playwright (web/node_modules), Chromium: CHROME_PATH (sukut — playwright keshidagi).
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"
SIPP_DIR="$ROOT_DIR/tests/sipp"
LIB_DIR="$ROOT_DIR/scripts/lib"
API_BASE="${API_BASE:-http://127.0.0.1:8710/api/v1}"
WEB_HTTP="${M3A_BASE:-http://127.0.0.1:8711}"
WS_BASE="ws://${WEB_HTTP#http://}"
PROJECT="innova-m0"
NET="${PROJECT}_innova-net"
PY_IMAGE="python:3.12-slim"
PG=innova-m0-postgres-1
AST=innova-m0-asterisk-1
WEBCONT=innova-m0-web-1
export M3A_CTL_PORT="${M3A_CTL_PORT:-8799}"
CTL="http://127.0.0.1:$M3A_CTL_PORT"
export CHROME_PATH="${CHROME_PATH:-$HOME/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome}"
declare -A IP=([102]="172.21.0.180" [trunk]="172.21.0.181")
OP_PW="M3aProof!2026a"   # operatorlarning yangi (o'zgartirilgan) paroli
DID_QUEUE="712000303"
IVR_NUM="550"; QUEUE_NUM="560"

# shellcheck source=lib/m2a_common.sh
source "$LIB_DIR/m2a_common.sh"
# shellcheck source=lib/m3a_common.sh
source "$LIB_DIR/m3a_common.sh"

ADMIN_PASSWORD="${PROOF_ADMIN_PASSWORD:-$(grep -E '^PROOF_ADMIN_PASSWORD=' "$DEPLOY_DIR/.env" | cut -d= -f2-)}"
[[ -n "$ADMIN_PASSWORD" ]] || { echo "PROOF_ADMIN_PASSWORD deploy/.env da yo'q"; exit 2; }
[[ -x "$CHROME_PATH" ]] || { echo "Chromium topilmadi: CHROME_PATH=$CHROME_PATH"; exit 2; }
[[ -d "$ROOT_DIR/web/node_modules/playwright" ]] || { echo "web/node_modules/playwright yo'q (npm ci)"; exit 2; }

CONTAINERS=(m3a-proof-102 m3a-proof-trunk)
BROWSER_PID=""
cleanup() {
  curl -s -m 5 "$CTL/quit" >/dev/null 2>&1 || true
  [[ -n "$BROWSER_PID" ]] && kill "$BROWSER_PID" >/dev/null 2>&1 || true
  docker rm -f "${CONTAINERS[@]}" >/dev/null 2>&1 || true
  if [[ "${TTL_CHANGED:-0}" == "1" ]]; then (cd "$DEPLOY_DIR" && docker compose up -d api >/dev/null 2>&1) || true; fi
}
trap cleanup EXIT
cleanup

if [[ "${1:-}" == "--fresh" ]]; then
  echo "--- --fresh: stack qayta quriladi ---"
  export SIP_GUARD_INTERVAL_S="${SIP_GUARD_INTERVAL_S:-2}"
  (cd "$DEPLOY_DIR" && docker compose down -v) || true
  (cd "$DEPLOY_DIR" && docker compose build) || { fail "docker compose build"; exit 1; }
  (cd "$DEPLOY_DIR" && docker compose up -d) || { fail "docker compose up"; exit 1; }
  echo "Konteynerlar tayyor bo'lishini kutish..."
  wait_api
fi

NGINX_IP=$(docker inspect -f "{{(index .NetworkSettings.Networks \"$NET\").IPAddress}}" "$WEBCONT")
[[ -n "$NGINX_IP" ]] || { echo "web konteyneri ($WEBCONT) topilmadi"; exit 2; }

echo "=== setup/login ==="
login "$ADMIN_PASSWORD" || { fail "login"; exit 1; }
LEFTOVER=$(jget "$(jbody "$(api GET "/extensions?q=M3a")")" total 2>/dev/null)
if [[ -n "$LEFTOVER" && "$LEFTOVER" != "0" ]]; then
  echo "Stekda oldingi M3a isbot qoldiqlari bor ($LEFTOVER ext) — 'scripts/m3a-proof.sh --fresh' bilan ishga tushiring."
  exit 2
fi

# ---------------------------------------------------------------- resurslar
echo "=== resurslar ==="
declare -A EXT_ID SECRET
for spec in 101:true 102:false 103:true; do
  n=${spec%%:*}
  j=$(jbody "$(api POST /extensions "{\"number\":\"$n\",\"name\":\"M3a$n\",\"webrtc\":${spec#*:}}")")
  EXT_ID[$n]=$(jget "$j" item id); SECRET[$n]=$(jget "$j" sip password)
done
check "$( [[ -n "${EXT_ID[101]}" && -n "${EXT_ID[102]}" && -n "${EXT_ID[103]}" ]]; echo $?)" \
  "POST /extensions 101,103 (webrtc) + 102 (oddiy SIP)" "${EXT_ID[*]}"

declare -A TOKEN
for spec in A:101 B:103 C:102; do
  who=${spec%%:*}; n=${spec#*:}
  UJ=$(api POST /users "{\"username\":\"m3a_$who\",\"full_name\":\"M3a $who\",\"role\":\"operator\",\"extension_id\":\"${EXT_ID[$n]}\",\"password\":\"M3aTmp!2026x\"}")
  t=$(login_as "m3a_$who" 'M3aTmp!2026x')
  api_as "$t" POST /auth/change-password "{\"current\":\"M3aTmp!2026x\",\"new\":\"$OP_PW\"}" >/dev/null
  TOKEN[$who]=$(login_as "m3a_$who" "$OP_PW")
  check "$( [[ "$(jcode "$UJ")" == "201" && -n "${TOKEN[$who]}" ]]; echo $?)" "operator m3a_$who ($n) yaratildi, parol almashtirildi" "$UJ"
done

target_of() { # kind label|raqam -> call_targets id (label: "102 · M3a102")
  jbody "$(api GET "/targets?kind=$1&q=$2")" | python3 -c "
import json,sys
q=sys.argv[1]
print(next((i['id'] for i in json.load(sys.stdin)['items']
            if q in (i['label'], i['number']) or i['label'].endswith(' · ' + q)), ''))" "$2"
}
HANGUP_T=$(jget "$(jbody "$(api GET "/targets?kind=hangup")")" items 0 id)
AUDIO_ID=$(jget "$(jbody "$(api GET /audio)")" items 0 id)
X102_T=$(target_of extension 102)
IVR_J=$(api POST /ivrs "{\"name\":\"M3aIvr\",\"number\":\"$IVR_NUM\",\"greeting_audio_id\":\"$AUDIO_ID\",\"timeout_seconds\":15,\"repeats\":0,\"options\":[{\"digit\":\"1\",\"target_id\":\"$X102_T\"}],\"timeout_target_id\":\"$HANGUP_T\",\"invalid_target_id\":\"$HANGUP_T\"}")
check "$( [[ "$(jcode "$IVR_J")" == "201" ]]; echo $?)" "POST /ivrs M3aIvr ($IVR_NUM, 1 -> 102)" "$IVR_J"
Q_J=$(api POST /queues "{\"name\":\"M3aQueue\",\"number\":\"$QUEUE_NUM\",\"strategy\":\"ringall\",\"members\":[{\"extension_id\":\"${EXT_ID[103]}\"}],\"timeout_target_id\":\"$HANGUP_T\"}")
check "$( [[ "$(jcode "$Q_J")" == "201" ]]; echo $?)" "POST /queues M3aQueue (a'zo 103)" "$Q_J"
T_J=$(api POST /trunks "{\"name\":\"M3aTrunk\",\"host\":\"${IP[trunk]}\",\"port\":5060,\"match\":[\"${IP[trunk]}/32\"],\"codecs\":[\"ulaw\"],\"max_channels\":5,\"enabled\":true}")
R_J=$(api POST /inbound-routes "{\"name\":\"M3aDid\",\"did\":\"$DID_QUEUE\",\"target_id\":\"$(target_of queue M3aQueue)\",\"enabled\":true}")
check "$( [[ "$(jcode "$T_J")" == "201" && "$(jcode "$R_J")" == "201" ]]; echo $?)" "trunk M3aTrunk + DID $DID_QUEUE -> navbat" "$T_J / $R_J"

for c in 102 trunk; do
  docker run -d --name "m3a-proof-$c" --network "$NET" --ip "${IP[$c]}" "$PY_IMAGE" sleep infinity >/dev/null
  for f in outbound_invite.py vm_caller.py m2a_phone.py; do docker cp "$SIPP_DIR/$f" "m3a-proof-$c:/tmp/$f"; done
done
mode() { docker exec "m3a-proof-$1" sh -c "echo '$2' > /tmp/mode"; }
plog() { docker exec "m3a-proof-$1" cat /tmp/phone.log 2>/dev/null; }
invites() { plog "$1" | grep -c '^INVITE '; }
count_of() { plog "$1" | grep -c "^$2"; }
invites_gt() { (( $(invites "$1") > $2 )); }
count_gt() { (( $(count_of "$1" "$2") > $3 )); }
mode 102 answer
docker exec -d m3a-proof-102 sh -c "cd /tmp && python3 m2a_phone.py serve t1-102 '${SECRET[102]}' 5070 12000 /tmp/mode 900 > /tmp/phone.log 2>&1"
wait_until 15 sh -c "docker exec m3a-proof-102 grep -q 'REGISTER_RESULT: OK' /tmp/phone.log" \
  && pass "102 (python UAS) REGISTER -> 200" || fail "102 REGISTER -> $(plog 102)"
CALL_N=0
bg_call() { # konteyner user parol dialed talk_s nom
  CALL_N=$((CALL_N + 1))
  docker exec -d "m3a-proof-$1" sh -c "cd /tmp && python3 m2a_phone.py call '$2' '$3' $((5100 + CALL_N)) $((13000 + CALL_N * 2)) '$4' $5 > /tmp/$6.log 2>&1"
}
call_log() { docker exec "m3a-proof-$1" cat "/tmp/$2.log" 2>/dev/null; }
call_done() { call_log "$1" "$2" | grep -Eq 'BYE_SENT|REMOTE_BYE|INVITE_FINAL: SIP/2.0 [3-6]'; }
no_calls() { [[ -z "$(ast 'core show channels concise')" ]]; }
cdr_last() { # src dst -> "disposition|billsec"
  wait_for_sql "select disposition||'|'||billsec from cdr where src='$1' and dst='$2' order by calldate desc limit 1" 8
}

# ---------------------------------------------------------------- 1. web darvozasi
echo "=== 1. web konteyneri / darvoza ==="
R=$(curl -s -o /dev/null -w '%{http_code} %{content_type}' "$WEB_HTTP/")
check "$( [[ "$R" == "200 text/html"* ]]; echo $?)" "1: GET / -> 200 HTML" "$R"
R=$(curl -s -w ' %{http_code} %{content_type}' "$WEB_HTTP/api/v1/system/health")
check "$( [[ "$R" == *" 401 application/json"* && "$R" == *'"error"'* ]]; echo $?)" "1: /api/v1/system/health proksi -> 401 JSON" "$R"
R=$(curl -s -o /dev/null -w '%{http_code}' "$WEB_HTTP/internal/x")
check "$( [[ "$R" == "404" ]]; echo $?)" "1: /internal/x -> 404 (tashqariga yopiq)" "$R"
R=$(curl -s -o /dev/null -w '%{http_code}' "$WEB_HTTP/internal/softphone/ws-auth?t=x")
check "$( [[ "$R" == "404" ]]; echo $?)" "1: /internal/softphone/ws-auth tashqaridan -> 404" "$R"
R=$(ws_probe "$WS_BASE/sip-ws")
check "$( [[ "$R" == "HTTP 401"* ]]; echo $?)" "1: /sip-ws ticketsiz -> 401" "$R"
R=$(ws_probe "$WS_BASE/sip-ws?t=eyJ1aWQiOiJ4In0.YnJva2Vu")
check "$( [[ "$R" == "HTTP 401"* ]]; echo $?)" "1: /sip-ws buzilgan ticket -> 401" "$R"
SP_A=$(softphone_of "${TOKEN[A]}")
R=$(ws_probe "$WS_BASE/sip-ws?t=$(sp_field "$SP_A" ticket)")
check "$( [[ "$R" == "HTTP 101 sip" ]]; echo $?)" "1: /sip-ws to'g'ri ticket -> 101, Sec-WebSocket-Protocol: sip" "$R"
check "$( [[ "$(jcode "$SP_A")" == "200" && "$(sp_field "$SP_A" sip auth_user)" == "t1-101" ]]; echo $?)" \
  "1: /me/softphone (A) -> 200, auth_user t1-101" "$(jcode "$SP_A")"

# ---------------------------------------------------------------- 2. brauzerda kirish
echo "=== 2. Chromium: operator A (101), B (103), C (102) ==="
(cd "$ROOT_DIR/web" && exec node scripts/m3a-browser.mjs > /tmp/m3a-browser.log 2>&1) &
BROWSER_PID=$!
wait_until 20 curl -s -o /dev/null "$CTL/errors?who=none" || { fail "Chromium boshqaruvchisi ishga tushmadi ($(cat /tmp/m3a-browser.log))"; exit 1; }
for who in A B C; do
  R=$(br "open?who=$who&user=m3a_$who&pass=$OP_PW")
  check "$(bok "$R"; echo $?)" "2: $who brauzerda kirdi (?diag=1)" "$R"
done
wait_until 25 bis A connection registered && wait_until 10 bis B connection registered
check "$( bis A connection registered && bis B connection registered && bis A chip True && bis B chip True; echo $?)" \
  "2: A va B chip -> registered" "A=$(br 'state?who=A') B=$(br 'state?who=B')"
wait_until 10 ws_contact 101 && wait_until 10 ws_contact 103
check "$( ws_contact 101 && ws_contact 103; echo $?)" "2: pjsip show contacts -> t1-101 va t1-103 ws kontakt (Avail)" \
  "nginx=$NGINX_IP $(ast 'pjsip show contacts' | grep -E 't1-10[13]/')"
sleep 2
R=$(softphone_of "${TOKEN[C]}")
check "$( bis C connection unavailable && bis C chip False && [[ "$(jcode "$R")" == "409" ]]; echo $?)" \
  "2: C (102 webrtc emas) -> chip yo'q, /me/softphone 409" "$(br 'state?who=C') / $R"
br "close?who=C" >/dev/null

# ---------------------------------------------------------------- 3. brauzer <-> brauzer
echo "=== 3. brauzer <-> brauzer (DTLS-SRTP media) ==="
talk_ab() { # A 103 ga qo'ng'iroq, B javob beradi; ikkalasi gaplashmoqda
  br "dial?who=A&num=103" >/dev/null
  wait_until 15 bis B phase incoming || return 1
  [[ "$(bget B remoteNumber)" == "101" ]] || return 1
  br "click?who=B&id=answer" >/dev/null
  wait_until 15 bis A phase talking && wait_until 5 bis B phase talking
}
talk_ab; R=$?
check "$R" "3: A -> 103: B'da kiruvchi oyna (101), Javob -> ikkalasi talking" "A=$(br 'state?who=A') B=$(br 'state?who=B')"
INC_TEXT=$(jget "$(br 'text?who=B&id=softphone-timer')" text 2>/dev/null)
sleep 3
wait_until 15 media_flows A B
SA=$(br "stats?who=A"); SB=$(br "stats?who=B")
check "$(media_flows A B; echo $?)" "3: >=3 s dan keyin ikkala tomonda packetsSent/Received > 50" "A=$SA B=$SB"
check "$( [[ "$(jget "$SA" codec)" == "opus" && "$(jget "$SB" codec)" == "opus" ]]; echo $?)" "3: kodek opus (ikkala tomon)" "A=$SA B=$SB"
check "$( [[ "$INC_TEXT" =~ ^[0-9]+:[0-9]{2} ]]; echo $?)" "3: B gaplashish taymeri ko'rinadi" "$INC_TEXT"
br "click?who=A&id=hangup" >/dev/null
wait_until 10 bis B phase '' && wait_until 10 no_calls
CDR=$(cdr_last 101 103)
check "$( [[ "${CDR%%|*}" == "ANSWERED" && "${CDR#*|}" -ge 2 ]]; echo $?)" "3: CDR 101 -> 103 ANSWERED, billsec >= 2" "$CDR"
echo "    media: A=$SA B=$SB"

# ---------------------------------------------------------------- 4. brauzer <-> SIP
echo "=== 4. brauzer <-> oddiy SIP (102) ==="
A0=$(count_of 102 ANSWERED)
br "dial?who=A&num=102" >/dev/null
wait_until 15 count_gt 102 ANSWERED "$A0" && wait_until 10 bis A phase talking
check "$( bis A phase talking; echo $?)" "4: A -> 102: UAS javob berdi, A talking" "$(br 'state?who=A') / $(plog 102 | tail -3)"
sleep 3
S4=$(br "stats?who=A")
check "$( (( $(jget "$S4" packetsSent) > 50 )); echo $?)" "4: A -> 102 media yuborilmoqda (packetsSent > 50)" "$S4"
B0=$(count_of 102 'REQ BYE')
br "click?who=A&id=hangup" >/dev/null
wait_until 10 count_gt 102 'REQ BYE' "$B0"; wait_until 10 no_calls
CDR=$(cdr_last 101 102)
check "$( [[ "${CDR%%|*}" == "ANSWERED" ]]; echo $?)" "4: CDR 101 -> 102 ANSWERED (UAS BYE oldi)" "$CDR"

bg_call 102 t1-102 "${SECRET[102]}" 101 4 c4
wait_until 15 bis A phase incoming
check "$( [[ "$(bget A remoteNumber)" == "102" ]]; echo $?)" "4: 102 -> 101: A'da kiruvchi (102)" "$(br 'state?who=A')"
br "click?who=A&id=answer" >/dev/null
wait_until 20 call_done 102 c4
check "$(call_log 102 c4 | grep -q 'INVITE_FINAL: SIP/2.0 200' && call_log 102 c4 | grep -q BYE_SENT; echo $?)" \
  "4: 102 -> 101: 200 OK, 4 s gaplashib BYE" "$(call_log 102 c4)"
wait_until 10 bis A phase ''; wait_until 10 no_calls
CDR=$(cdr_last 102 101)
check "$( [[ "${CDR%%|*}" == "ANSWERED" ]]; echo $?)" "4: CDR 102 -> 101 ANSWERED" "$CDR"

# ---------------------------------------------------------------- 5. mute / hold / DTMF / transfer
echo "=== 5. mute, hold, DTMF, blind transfer ==="
talk_ab && wait_until 15 media_flows A B
check "$(media_flows A B; echo $?)" "5: A <-> B gaplashmoqda, media oqmoqda" "A=$(br 'stats?who=A') B=$(br 'stats?who=B')"
br "click?who=A&id=mute" >/dev/null; sleep 1
E1=$(stat_of B audioEnergy); sleep 3; E2=$(stat_of B audioEnergy)
check "$( bis A muted True && [[ "$(stat_of A micEnabled)" == "False" ]] && ! float_gt "$(python3 -c "print($E2-$E1)")" 0.0005; echo $?)" \
  "5: mute -> A mikrofon treki o'chiq, B'da kiruvchi energiya o'smaydi" "E1=$E1 E2=$E2"
br "click?who=A&id=mute" >/dev/null; sleep 3
E3=$(stat_of B audioEnergy)
check "$( bis A muted False && float_gt "$(python3 -c "print($E3-$E2)")" 0.01; echo $?)" "5: unmute -> B energiyasi yana o'sadi" "E2=$E2 E3=$E3"

M0=$(moh_lines "Started music on hold"); U0=$(moh_lines "Stopped music on hold")
br "click?who=A&id=hold" >/dev/null
wait_until 10 moh_gt "Started music on hold" "$M0"
check "$( bis A phase hold && (( $(moh_lines 'Started music on hold') > M0 )); echo $?)" \
  "5: hold -> re-INVITE, Asterisk B kanaliga MOH boshladi" "$(docker logs "$AST" 2>&1 | grep 'music on hold' | tail -1)"
br "click?who=A&id=hold" >/dev/null
wait_until 10 moh_gt "Stopped music on hold" "$U0"
check "$( bis A phase talking && (( $(moh_lines 'Stopped music on hold') > U0 )); echo $?)" "5: unhold -> MOH to'xtadi, talking" "$(br 'state?who=A')"

mode 102 ring
I0=$(invites 102)
R=$(br "transfer?who=B&num=102")
wait_until 15 invites_gt 102 "$I0"
check "$( bok "$R" && invites_gt 102 "$I0"; echo $?)" "5: B -> 102 blind transfer (REFER) -> 102 jiringlaydi" \
  "$R / $(plog 102 | grep '^INVITE ' | tail -1)"
wait_until 10 bis B phase ''
check "$( bis B phase '' && bis A phase talking; echo $?)" "5: transferdan keyin B bo'shadi, A ulanishda qoldi" \
  "A=$(br 'state?who=A') B=$(br 'state?who=B')"
br "click?who=A&id=hangup" >/dev/null
wait_until 10 no_calls

I0=$(invites 102)
br "dial?who=A&num=$IVR_NUM" >/dev/null
wait_until 15 bis A phase talking; sleep 2
br "dtmf?who=A&d=1" >/dev/null
wait_until 15 invites_gt 102 "$I0"
check "$( invites_gt 102 "$I0"; echo $?)" "5: DTMF (RFC 4733): A -> IVR $IVR_NUM, '1' -> 102 ga yetdi" "$(plog 102 | grep '^INVITE ' | tail -1)"
br "click?who=A&id=hangup" >/dev/null
wait_until 10 no_calls
mode 102 answer

# ---------------------------------------------------------------- 6. navbat
echo "=== 6. navbat: trunk -> M3aQueue -> B ==="
bg_call trunk trunk - "$DID_QUEUE" 8 c6
wait_until 20 bis B phase incoming
check "$( bis B phase incoming; echo $?)" "6: trunk DID -> navbat -> B'da kiruvchi oyna" "$(br 'state?who=B') / $(call_log trunk c6)"
br "click?who=B&id=answer" >/dev/null
wait_until 10 bis B phase talking
agent_busy() {
  jbody "$(api GET /live)" | python3 -c "
import json,sys
d=json.load(sys.stdin)
st=[a['state'] for q in d['queues'] if q['name']=='M3aQueue' for a in q['agents'] if a['extension']=='103']
sys.exit(0 if st==['busy'] else 1)"
}
wait_until 10 agent_busy
check "$(agent_busy; echo $?)" "6: B javob berdi -> GET /live: agent 103 busy" "$(jbody "$(api GET /live)" | head -c 600)"
wait_until 20 call_done trunk c6
check "$(call_log trunk c6 | grep -q 'INVITE_FINAL: SIP/2.0 200'; echo $?)" "6: trunk qo'ng'irog'i javob oldi" "$(call_log trunk c6)"
wait_until 10 bis B phase ''; wait_until 10 no_calls

# ---------------------------------------------------------------- 7. darvoza va guard
echo "=== 7. ticket TTL va WS guard ==="
EV0=$(sql "select count(*) from security_events where kind='ws_auth_failed'")
R=$(ws_register "$(softphone_of "${TOKEN[A]}")" "notog'ri-parol" 10)
BAD=$(grep -cE '^REGISTER (401|403)$' <<<"$R")
check "$( [[ "$R" == "HTTP 101 sip"* && "$BAD" == "10" ]]; echo $?)" "7: WS orqali noto'g'ri parol x10 -> 10 ta rad" "$R"
sleep "$(( ${SIP_GUARD_INTERVAL_S:-5} * 3 ))"
EV1=$(sql "select count(*) from security_events where kind='ws_auth_failed'")
BANS=$(sql "select count(*) from ip_bans where ip = cast('$NGINX_IP' as inet) and lifted_at is null")
check "$( [[ "$BANS" == "0" ]] && (( EV1 > EV0 )); echo $?)" "7: nginx IP ($NGINX_IP) ip_bans'da YO'Q, ws_auth_failed izi bor" \
  "bans=$BANS events $EV0 -> $EV1"
check "$( bis A connection registered && ws_contact 101; echo $?)" "7: hujumdan keyin A hamon registered" "$(br 'state?who=A')"

TTL_CHANGED=1
(cd "$DEPLOY_DIR" && SOFTPHONE_TICKET_TTL_S=5 docker compose up -d api >/dev/null 2>&1); sleep 2; wait_api
SP7=$(softphone_of "${TOKEN[A]}")
R1=$(ws_probe "$WS_BASE/sip-ws?t=$(sp_field "$SP7" ticket)")
sleep 7
R2=$(ws_probe "$WS_BASE/sip-ws?t=$(sp_field "$SP7" ticket)")
check "$( [[ "$R1" == "HTTP 101 sip" && "$R2" == "HTTP 401"* ]]; echo $?)" "7: TTL=5 s: yangi ticket 101, 7 s dan keyin 401" "$R1 / $R2"
(cd "$DEPLOY_DIR" && docker compose up -d api >/dev/null 2>&1); sleep 2; wait_api; TTL_CHANGED=0
check "$( bis A connection registered; echo $?)" "7: api qayta ishga tushgandan keyin ham ochiq WS (A) registered" "$(br 'state?who=A')"

# ---------------------------------------------------------------- (+) skrinshotlar
echo "=== skrinshotlar (m3a-real-check.mjs) ==="
br "close?who=A" >/dev/null; br "close?who=B" >/dev/null
SHOT_START=$(date +%s)
SHOT_OUT=$(cd "$ROOT_DIR/web" && M3A_A_USER=m3a_A M3A_B_USER=m3a_B M3A_PASS="$OP_PW" M3A_B_NUMBER=103 \
  node scripts/m3a-real-check.mjs 2>&1)
FRESH_SHOTS=0
for f in "$ROOT_DIR"/replica/clone-screens/m3a-*.png; do
  [[ -f "$f" && $(stat -c %Y "$f") -ge $SHOT_START ]] && FRESH_SHOTS=$((FRESH_SHOTS + 1))
done
check "$( (( FRESH_SHOTS >= 8 )); echo $?)" "skrinshotlar: chip/panel/kiruvchi/gaplashmoqda x light/dark ($FRESH_SHOTS ta)" "$SHOT_OUT"
wait_until 10 no_calls

# ---------------------------------------------------------------- 8. webrtc o'chirildi
echo "=== 8. admin 101 da webrtc=false ==="
R=$(br "open?who=A&user=m3a_A&pass=$OP_PW")
wait_until 25 bis A connection registered
check "$( bis A connection registered; echo $?)" "8: A qayta kirdi -> registered" "$(br 'state?who=A')"
UPD=$(jbody "$(api GET "/extensions?q=101")" | python3 -c "
import json,sys
print(next(i['updated_at'] for i in json.load(sys.stdin)['items'] if i['number']=='101'))")
R=$(api PATCH "/extensions/${EXT_ID[101]}" "{\"webrtc\":false,\"updated_at\":\"$UPD\"}")
T0=$(date +%s)
check "$( [[ "$(jcode "$R")" == "200" ]]; echo $?)" "8: PATCH 101 webrtc=false -> 200" "$R"
R=$(softphone_of "${TOKEN[A]}")
check "$( [[ "$(jcode "$R")" == "409" && "$(jget "$(jbody "$R")" error code)" == "webrtc_disabled" ]]; echo $?)" \
  "8: /me/softphone -> 409 webrtc_disabled" "$R"
wait_until 65 bis A chip False
DT=$(( $(date +%s) - T0 ))
check "$( bis A chip False && (( DT <= 60 )); echo $?)" "8: A chipi yo'qoldi (${DT} s <= 60 s)" "$(br 'state?who=A')"
wait_until 10 no_ws_contact 101
check "$(no_ws_contact 101; echo $?)" "8: t1-101 ws kontakti olib tashlandi (unregister)" \
  "$(ast 'pjsip show contacts' | grep t1-101)"

ERRS=$(br "errors?who=A")
echo "    brauzer konsol xatolari (A): $ERRS"
echo "=== NATIJA: PASS=$PASS FAIL=$FAIL ==="
[[ "$FAIL" -eq 0 ]]
