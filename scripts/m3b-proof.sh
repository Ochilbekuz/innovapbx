#!/usr/bin/env bash
# Innova PBX — M3b (yadro) proof (replica/m3b-contract.md §7.1–7.4):
#   1. Yozuv: 101 always (trunk -> 101, 6 s) -> call_recordings 1, fayl >= 5 s, /calls recordings, audio 200 (admin, egasi),
#      boshqa operator 403, Range 206, imzoli havola 200 / buzilgan 403 / eskirgan 403; 102 never -> yozuv yo'q;
#      103 on_demand: *1siz yo'q, *1 bilan bor; navbat (104 always) -> bor; chiquvchi 101 -> trunk -> bor; tozalovchi.
#   2. Webhook: ringing -> answered -> ended tartibda, HMAC to'g'ri, ended'da recordings url; ichki (include_internal=false)
#      -> hodisa yo'q; qabul qiluvchi 2 marta 500 -> 3-urinishda 200, X-Innova-Delivery bir xil, jurnalda attempts=3.
#   3. Bardoshlilik: qo'ng'iroq paytida `docker stop api` -> qo'ng'iroq tugaydi -> `docker start api` -> <= 60 s ichida
#      `call.ended` (bir marta).
#   4. API kalit: scope'siz 403, bekor qilingan 401, /calls + kursor + /calls/{id} + yozuv 200, /extensions sirlarsiz,
#      originate -> 101 jiringlaydi -> javob -> trunk UAS `to` raqamli INVITE; CR/LF -> 422; noma'lum raqam -> 422; 429.
#   (+) `scripts/lib/m3b_crm_scenario.sh` bo'lsa — CRM ssenariylari (§7.5–7.6) shu stekda.
#
# Foydalanish:
#   scripts/m3b-proof.sh            # joriy `innova-m0` stack (M3b qoldiqlari bo'lsa — exit 2)
#   scripts/m3b-proof.sh --fresh    # avval `docker compose down -v` + build + up -d (qisqa retry jadvali bilan)
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
APICONT=innova-m0-api-1
declare -A IP=([101]="172.21.0.221" [102]="172.21.0.222" [103]="172.21.0.223" [104]="172.21.0.224"
               [trunk]="172.21.0.225" [wh]="172.21.0.226")
WH_IP="${IP[wh]}"; WH_PORT=9000
OP_PW="M3bProof!2026a"
DID_101="713000101"; DID_102="713000102"; DID_103="713000103"; DID_Q="713000104"; QUEUE_NUM="561"
OUT_NUM="998901234567"; ORIG_TO="+998 90 111-22-33"; ORIG_DIGITS="998901112233"

# shellcheck source=lib/m2a_common.sh
source "$LIB_DIR/m2a_common.sh"
# shellcheck source=lib/m3b_common.sh
source "$LIB_DIR/m3b_common.sh"

ADMIN_PASSWORD="${PROOF_ADMIN_PASSWORD:-$(grep -E '^PROOF_ADMIN_PASSWORD=' "$DEPLOY_DIR/.env" | cut -d= -f2-)}"
[[ -n "$ADMIN_PASSWORD" ]] || { echo "PROOF_ADMIN_PASSWORD deploy/.env da yo'q"; exit 2; }

CONTAINERS=(m3b-proof-101 m3b-proof-102 m3b-proof-103 m3b-proof-104 m3b-proof-trunk m3b-proof-wh)
cleanup() {
  docker rm -f "${CONTAINERS[@]}" >/dev/null 2>&1 || true
  docker start "$APICONT" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

if [[ "${1:-}" == "--fresh" ]]; then
  echo "--- --fresh: stack qayta quriladi ---"
  export INTEGRATION_RETRY_SCHEDULE_S="${INTEGRATION_RETRY_SCHEDULE_S:-2,2,2,2,2,2,2,2}"
  export CALL_EVENTS_SWEEP_INTERVAL_S="${CALL_EVENTS_SWEEP_INTERVAL_S:-5}"
  (cd "$DEPLOY_DIR" && docker compose down -v) || true
  (cd "$DEPLOY_DIR" && docker compose build) || { fail "docker compose build"; exit 1; }
  (cd "$DEPLOY_DIR" && docker compose up -d) || { fail "docker compose up"; exit 1; }
  echo "Konteynerlar tayyor bo'lishini kutish..."
  wait_api
fi

echo "=== setup/login ==="
login "$ADMIN_PASSWORD" || { fail "login"; exit 1; }
LEFTOVER=$(jget "$(jbody "$(api GET "/extensions?q=M3b")")" total 2>/dev/null)
if [[ -n "$LEFTOVER" && "$LEFTOVER" != "0" ]]; then
  echo "Stekda oldingi M3b isbot qoldiqlari bor ($LEFTOVER ext) — 'scripts/m3b-proof.sh --fresh' bilan ishga tushiring."
  exit 2
fi

# ---------------------------------------------------------------- resurslar
echo "=== resurslar ==="
declare -A EXT_ID SECRET
for spec in 101:always 102:never 103:on_demand 104:always; do
  n=${spec%%:*}
  j=$(jbody "$(api POST /extensions "{\"number\":\"$n\",\"name\":\"M3b$n\",\"recording\":\"${spec#*:}\"}")")
  EXT_ID[$n]=$(jget "$j" item id); SECRET[$n]=$(jget "$j" sip password)
  check "$( [[ -n "${EXT_ID[$n]}" && "$(jget "$j" item recording)" == "${spec#*:}" ]]; echo $?)" \
    "POST /extensions $n recording=${spec#*:}" "$j"
done
declare -A TOKEN
for spec in A:101 B:104; do
  who=${spec%%:*}; n=${spec#*:}
  UJ=$(api POST /users "{\"username\":\"m3b_$who\",\"full_name\":\"M3b $who\",\"role\":\"operator\",\"extension_id\":\"${EXT_ID[$n]}\",\"password\":\"M3bTmp!2026x\"}")
  t=$(login_as "m3b_$who" 'M3bTmp!2026x')
  api_as "$t" POST /auth/change-password "{\"current\":\"M3bTmp!2026x\",\"new\":\"$OP_PW\"}" >/dev/null
  TOKEN[$who]=$(login_as "m3b_$who" "$OP_PW")
  check "$( [[ "$(jcode "$UJ")" == "201" && -n "${TOKEN[$who]}" ]]; echo $?)" "operator m3b_$who ($n) yaratildi" "$UJ"
done
target_of() { # kind label|raqam -> call_targets id
  jbody "$(api GET "/targets?kind=$1&q=$2")" | python3 -c "
import json,sys
q=sys.argv[1]
print(next((i['id'] for i in json.load(sys.stdin)['items']
            if q in (i['label'], i['number']) or i['label'].endswith(' · ' + q)), ''))" "$2"
}
HANGUP_T=$(jget "$(jbody "$(api GET "/targets?kind=hangup")")" items 0 id)
Q_J=$(api POST /queues "{\"name\":\"M3bQueue\",\"number\":\"$QUEUE_NUM\",\"strategy\":\"ringall\",\"members\":[{\"extension_id\":\"${EXT_ID[104]}\"}],\"timeout_target_id\":\"$HANGUP_T\"}")
check "$( [[ "$(jcode "$Q_J")" == "201" ]]; echo $?)" "POST /queues M3bQueue (a'zo 104)" "$Q_J"
TRUNK=$(jbody "$(api POST /trunks "{\"name\":\"M3bTrunk\",\"host\":\"${IP[trunk]}\",\"port\":5060,\"match\":[\"${IP[trunk]}/32\"],\"codecs\":[\"ulaw\"],\"max_channels\":10,\"enabled\":true}")")
TRUNK_ID=$(jget "$TRUNK" item id)
ROUTE=$(api POST /outbound-routes "{\"name\":\"M3bRoute\",\"priority\":1,\"patterns\":[{\"pattern\":\"998XXXXXXXXX\"}],\"trunk_ids\":[\"$TRUNK_ID\"],\"international\":false}")
check "$( [[ -n "$TRUNK_ID" && "$(jcode "$ROUTE")" == "201" ]]; echo $?)" "trunk M3bTrunk + marshrut 998XXXXXXXXX" "$TRUNK / $ROUTE"
ROUTES_OK=0
for spec in "$DID_101:extension:101" "$DID_102:extension:102" "$DID_103:extension:103" "$DID_Q:queue:M3bQueue"; do
  IFS=: read -r did kind ref <<<"$spec"
  R=$(api POST /inbound-routes "{\"name\":\"M3bDid$did\",\"did\":\"$did\",\"target_id\":\"$(target_of "$kind" "$ref")\",\"enabled\":true}")
  [[ "$(jcode "$R")" == "201" ]] && ROUTES_OK=$((ROUTES_OK + 1))
done
check "$( [[ "$ROUTES_OK" == "4" ]]; echo $?)" "4 ta DID (101, 102, 103, navbat)" "$ROUTES_OK"
check "$(ast "dialplan show innova-rec" | grep -q 'Gosub(innova-rec-start'; echo $?)" \
  "Asterisk: innova-rec subroutine yuklangan" "$(ast 'dialplan show innova-rec' | head -3)"
check "$(ast "features show" | grep -Eq 'innova-rec +.* \*1'; echo $?)" "features: innova-rec => *1 (applicationmap)" \
  "$(ast 'features show' | grep -i innova)"

# ---------------------------------------------------------------- soxta serverlar va telefonlar
echo "=== soxta webhook va telefonlar ==="
docker run -d --name m3b-proof-wh --network "$NET" --ip "$WH_IP" "$PY_IMAGE" sleep infinity >/dev/null
docker cp "$SIPP_DIR/fake_webhook.py" m3b-proof-wh:/tmp/fake_webhook.py
docker exec -d m3b-proof-wh python3 /tmp/fake_webhook.py 0.0.0.0 "$WH_PORT"
for c in 101 102 103 104 trunk; do
  docker run -d --name "m3b-proof-$c" --network "$NET" --ip "${IP[$c]}" "$PY_IMAGE" sleep infinity >/dev/null
  for f in outbound_invite.py vm_caller.py m2a_phone.py; do docker cp "$SIPP_DIR/$f" "m3b-proof-$c:/tmp/$f"; done
  docker exec "m3b-proof-$c" sh -c "echo answer > /tmp/mode"
done
for n in 101 102 103 104; do
  docker exec -d "m3b-proof-$n" sh -c "cd /tmp && python3 m2a_phone.py serve $n '${SECRET[$n]}' 5070 12000 /tmp/mode 900 > /tmp/phone.log 2>&1"
done
docker exec -d m3b-proof-trunk sh -c "cd /tmp && python3 m2a_phone.py serve trunk - 5060 12000 /tmp/mode 900 > /tmp/phone.log 2>&1"
registered() { for n in 101 102 103 104; do docker exec "m3b-proof-$n" grep -q 'REGISTER_RESULT: OK' /tmp/phone.log 2>/dev/null || return 1; done; }
wait_until 15 registered && pass "101-104 REGISTER -> 200 OK" || fail "REGISTER -> $(docker exec m3b-proof-101 cat /tmp/phone.log)"
wait_until 10 curl -sf -o /dev/null "http://$WH_IP:$WH_PORT/_requests" && pass "soxta webhook ($WH_IP:$WH_PORT) ishlayapti" \
  || fail "soxta webhook ishga tushmadi"

mode() { docker exec "m3b-proof-$1" sh -c "echo '$2' > /tmp/mode"; }
plog() { docker exec "m3b-proof-$1" cat /tmp/phone.log 2>/dev/null; }
invites() { plog "$1" | grep -c '^INVITE '; }
invites_gt() { (( $(invites "$1") > $2 )); }
CALL_N=0
call_bg() { # konteyner user parol dialed talk_s nom -> /tmp/<nom>.log (fon)
  CALL_N=$((CALL_N + 1))
  docker exec -d "m3b-proof-$1" sh -c "cd /tmp && python3 m2a_phone.py call '$2' '$3' $((5100 + CALL_N)) $((13000 + CALL_N * 2)) '$4' $5 > /tmp/$6.log 2>&1"
}
call_log() { docker exec "m3b-proof-$1" cat "/tmp/$2.log" 2>/dev/null; }
call_done() { call_log "$1" "$2" | grep -Eq 'BYE_SENT|REMOTE_BYE|INVITE_FINAL: SIP/2.0 [3-6]'; }
call_answered() { call_log "$1" "$2" | grep -q 'INVITE_FINAL: SIP/2.0 200'; }
no_calls() { [[ -z "$(ast 'core show channels concise')" ]]; }
trunk_call() { # did talk_s nom -> sinxron (tugaguncha), so'ng kanal qolmaguncha
  call_bg trunk trunk - "$1" "$2" "$3"
  wait_until $(( $2 + 20 )) call_done trunk "$3"
  wait_until 10 no_calls
}

# ---------------------------------------------------------------- 2a. webhook obunasi (1-ssenariydan OLDIN)
echo "=== 2. webhook obunasi ==="
SET_J=$(api PATCH /settings/integrations "{\"public_base_url\":\"${API_BASE%/api/v1}\",\"updated_at\":\"$(updated_at_of /settings/integrations)\"}")
check "$( [[ "$(jcode "$SET_J")" == "200" && "$(jget "$(jbody "$SET_J")" public_base_url)" == "${API_BASE%/api/v1}" ]]; echo $?)" \
  "PATCH /settings/integrations public_base_url" "$SET_J"
BAD_J=$(api POST /integrations/webhooks '{"name":"M3bBad","url":"http://127.0.0.1:8000/x","events":["call.ended"]}')
BAD2_J=$(api POST /integrations/webhooks '{"name":"M3bBad","url":"http://169.254.169.254/latest","events":["call.ended"]}')
BAD3_J=$(api POST /integrations/webhooks '{"name":"M3bBad","url":"http://postgres:5432/","events":["call.ended"]}')
check "$(err_is "$BAD_J" 422 url_forbidden && err_is "$BAD2_J" 422 url_forbidden && err_is "$BAD3_J" 422 url_forbidden; echo $?)" \
  "SSRF: 127.0.0.1 / 169.254.169.254 / postgres -> 422 url_forbidden" "$BAD_J / $BAD2_J / $BAD3_J"
WA_J=$(api POST /integrations/webhooks "{\"name\":\"M3bHookA\",\"url\":\"http://$WH_IP:$WH_PORT/a\",\"events\":[\"call.ringing\",\"call.answered\",\"call.ended\"]}")
WA_ID=$(jget "$(jbody "$WA_J")" item id); WA_SECRET=$(jget "$(jbody "$WA_J")" secret)
check "$( [[ "$(jcode "$WA_J")" == "201" && "$WA_SECRET" == whsec_* ]]; echo $?)" \
  "POST /integrations/webhooks (LAN $WH_IP) -> 201, secret bir marta" "$WA_J"
LIST_J=$(jbody "$(api GET /integrations/webhooks)")
check "$( ! grep -q "$WA_SECRET" <<<"$LIST_J" && [[ "$(jget "$LIST_J" items 0 has_secret)" == "True" ]]; echo $?)" \
  "GET /integrations/webhooks -> secret ko'rinmaydi (has_secret)" "$LIST_J"
wh_config /a "$WA_SECRET"

# ---------------------------------------------------------------- 1. yozuvlar
echo "=== 1. yozuvlar ==="
trunk_call "$DID_101" 6 c1
L1=$(linkedid_to_ext 101)
check "$(call_answered trunk c1; echo $?)" "1: trunk -> 101 (always) javob, 6 s" "$(call_log trunk c1 | tail -3)"
wait_until 20 ended_emitted "$L1"
REC1=$(rec_first "$L1"); REC1_ID=${REC1%%|*}
check "$( [[ "$(rec_count "$L1")" == "1" && "$(cut -d'|' -f3 <<<"$REC1")" == "101" ]]; echo $?)" \
  "1: call_recordings -> 1 ta (extension 101)" "L=$L1 rec=$REC1"
REC1_PATH=$(cut -d'|' -f4 <<<"$REC1")
check "$( [[ "$REC1_PATH" =~ ^innova/[0-9]{4}/[0-9]{2}/[0-9]{2}/${L1//./\\.}-[0-9.]+\.wav$ ]]; echo $?)" \
  "1: yo'l innova/YYYY/MM/DD/<linkedid>-<uniqueid>.wav" "$REC1_PATH"
CDRREC=$(sql "select recordingfile from cdr where linkedid='$L1' and recordingfile <> '' limit 1")
check "$( [[ "$CDRREC" == "$REC1_PATH" ]]; echo $?)" "1: CDR(recordingfile) nisbiy yo'l" "$CDRREC"
curl -s -o /tmp/m3b-rec1.wav "${AUTH[@]}" "$API_BASE/recordings/$REC1_ID/audio"
SEC=$(wav_seconds /tmp/m3b-rec1.wav)
check "$(python3 -c "import sys; sys.exit(0 if $SEC >= 5 else 1)"; echo $?)" "1: admin audio 200, WAV davomiyligi >= 5 s" \
  "${SEC}s, duration_s=$(cut -d'|' -f2 <<<"$REC1")"
CALLS_REC=$(jbody "$(api GET "/calls?size=50")" | python3 -c "
import json,sys
L=sys.argv[1]
print(next((len(c['recordings']) for c in json.load(sys.stdin)['items'] if c.get('linkedid')==L), -1))" "$L1")
check "$( [[ "$CALLS_REC" == "1" ]]; echo $?)" "1: GET /calls -> shu qo'ng'iroqda recordings [1]" "$CALLS_REC"
ME_REC=$(jbody "$(api_as "${TOKEN[A]}" GET "/me/calls?size=50")" | python3 -c "
import json,sys
L=sys.argv[1]
print(next((len(c['recordings']) for c in json.load(sys.stdin)['items'] if c.get('linkedid')==L), -1))" "$L1")
check "$( [[ "$ME_REC" == "1" ]]; echo $?)" "1: GET /me/calls (operator 101) -> recordings [1]" "$ME_REC"
C_OWN=$(http_code -H "Authorization: Bearer ${TOKEN[A]}" "$API_BASE/recordings/$REC1_ID/audio")
C_OTHER=$(http_code -H "Authorization: Bearer ${TOKEN[B]}" "$API_BASE/recordings/$REC1_ID/audio")
check "$( [[ "$C_OWN" == "200" && "$C_OTHER" == "403" ]]; echo $?)" "1: audio: operator-egasi 200, boshqa operator 403" \
  "egasi=$C_OWN boshqa=$C_OTHER"
RANGE=$(curl -s -o /dev/null -w '%{http_code} %{size_download}' -H 'Range: bytes=0-99' "${AUTH[@]}" "$API_BASE/recordings/$REC1_ID/audio")
check "$( [[ "$RANGE" == "206 100" ]]; echo $?)" "1: Range: bytes=0-99 -> 206, 100 bayt" "$RANGE"
wait_until 15 wh_has /a "$L1" call.ended
URL1=$(wh_ended_field /a "$L1" "(c['recordings'] or [{}])[0].get('url') or ''")
C_SIGNED=$(http_code "$URL1")
C_TAMPER=$(http_code "${URL1%?}$( [[ "${URL1: -1}" == "0" ]] && echo 1 || echo 0)")
C_EXPIRED=$(http_code "$PUBLIC_BASE/recordings/$REC1_ID$(signed_link "$REC1_ID" $(( $(date +%s) - 10 )))")
C_NOAUTH=$(http_code "$PUBLIC_BASE/recordings/$REC1_ID")
check "$( [[ "$URL1" == "$PUBLIC_BASE/recordings/$REC1_ID?exp="* && "$C_SIGNED" == "200" ]]; echo $?)" \
  "1: webhook ended'dagi imzoli havola -> 200 (autentifikatsiyasiz)" "$URL1 -> $C_SIGNED"
check "$( [[ "$C_TAMPER" == "403" && "$C_EXPIRED" == "403" && "$C_NOAUTH" == "401" ]]; echo $?)" \
  "1: buzilgan imzo 403, eskirgan 403, imzosiz/kalitsiz 401" "tamper=$C_TAMPER expired=$C_EXPIRED noauth=$C_NOAUTH"

trunk_call "$DID_102" 4 c2
L2=$(linkedid_to_ext 102)
wait_until 20 ended_emitted "$L2"
check "$(call_answered trunk c2 && ended_emitted "$L2" && [[ "$(rec_count "$L2")" == "0" ]]; echo $?)" \
  "1: trunk -> 102 (never) javob -> yozuv YO'Q" "L=$L2 recs=$(rec_count "$L2")"

trunk_call "$DID_103" 4 c3a
L3A=$(linkedid_to_ext 103)
wait_until 20 ended_emitted "$L3A"
check "$(call_answered trunk c3a && ended_emitted "$L3A" && [[ "$(rec_count "$L3A")" == "0" ]]; echo $?)" \
  "1: trunk -> 103 (on_demand), *1 bosilmadi -> yozuv YO'Q" "L=$L3A recs=$(rec_count "$L3A")"
mode 103 'answer:*1'
trunk_call "$DID_103" 6 c3b
mode 103 answer
L3B=$(linkedid_to_ext 103)
wait_until 20 ended_emitted "$L3B"
REC3=$(rec_first "$L3B")
check "$( [[ "$(rec_count "$L3B")" == "1" && "$(cut -d'|' -f2 <<<"$REC3")" -ge 2 ]]; echo $?)" \
  "1: trunk -> 103 (on_demand) + *1 (SIP INFO) -> yozuv bor" "L=$L3B rec=$REC3 $(plog 103 | grep -c XFER_SENT)"

trunk_call "$DID_Q" 5 cq
LQ=$(linkedid_to_ext 104)
wait_until 20 ended_emitted "$LQ"; wait_until 20 wh_has /a "$LQ" call.ended
RECQ=$(rec_first "$LQ")
check "$(call_answered trunk cq && [[ "$(rec_count "$LQ")" -ge 1 && "$(cut -d'|' -f3 <<<"$RECQ")" == "104" ]]; echo $?)" \
  "1: trunk -> navbat -> 104 (always) javob -> yozuv bor" "L=$LQ rec=$RECQ"
QDID=$(wh_ended_field /a "$LQ" "(c.get('queue') or {}).get('name','') + '|' + str(c.get('did'))")
check "$( [[ "$QDID" == "M3bQueue|$DID_Q" ]]; echo $?)" "2: navbat qo'ng'irog'i ended: queue.name + did" "$QDID"
QRING=$(wh_query /a "$LQ" "next(((r['body']['call'].get('queue') or {}).get('name','') + '|' + str(r['body']['call'].get('did')) for r in ok if r['event'] == 'call.ringing'), '')")
check "$( [[ "$QRING" == "M3bQueue|$DID_Q" ]]; echo $?)" "2: navbat call.ringing (jonli, AMI VarSet): queue.name + did" "$QRING"

I0=$(invites trunk)
call_bg 101 "101" "${SECRET[101]}" "$OUT_NUM" 5 co
wait_until 25 call_done 101 co; wait_until 10 no_calls
LO=$(linkedid_from_ext_to_trunk 101)
wait_until 20 ended_emitted "$LO"; wait_until 20 wh_has /a "$LO" call.ended
RECO=$(rec_first "$LO")
check "$(invites_gt trunk "$I0" && [[ "$(rec_count "$LO")" == "1" ]]; echo $?)" "1: chiquvchi 101 -> trunk -> yozuv bor" \
  "L=$LO rec=$RECO / $(call_log 101 co | tail -2)"
DIRO=$(wh_ended_field /a "$LO" "c['direction'] + '|' + str(c.get('extension')) + '|' + str(c.get('to'))")
check "$( [[ "$DIRO" == "outbound|101|$OUT_NUM" ]]; echo $?)" "2: chiquvchi ended: direction=outbound, extension=101, to" "$DIRO"

RS_J=$(api PATCH /settings/recording "{\"retention_days\":7,\"updated_at\":\"$(updated_at_of /settings/recording)\"}")
RECO_ID=${RECO%%|*}; RECO_PATH=$(cut -d'|' -f4 <<<"$RECO")
sql "update call_recordings set started_at = now() - interval '10 days' where id='$RECO_ID'" >/dev/null
PURGED=$(run_purge)
GONE=$(docker exec "$AST" sh -c "test -e /var/spool/asterisk/monitor/$RECO_PATH && echo bor || echo yoq")
DEL=$(sql "select deleted_at is not null from call_recordings where id='$RECO_ID'")
STILL=$(rec_count "$L1")
check "$( [[ "$(jcode "$RS_J")" == "200" && "$PURGED" -ge 1 && "$GONE" == "yoq" && "$DEL" == "t" && "$STILL" == "1" ]]; echo $?)" \
  "1: retention 7 kun -> tozalovchi eski faylni o'chirdi (deleted_at), yangisi qoldi" \
  "patch=$(jcode "$RS_J") purged=$PURGED file=$GONE deleted=$DEL L1=$STILL"
api PATCH /settings/recording "{\"retention_days\":365,\"updated_at\":\"$(updated_at_of /settings/recording)\"}" >/dev/null
RECQ_ID=${RECQ%%|*}
C_DEL_OP=$(http_code -X DELETE -H "Authorization: Bearer ${TOKEN[B]}" "$API_BASE/recordings/$RECQ_ID")
C_DEL=$(http_code -X DELETE "${AUTH[@]}" "$API_BASE/recordings/$RECQ_ID")
AUD=$(sql "select count(*) from audit_log where action='delete' and entity='recording' and entity_id='$RECQ_ID'")
check "$( [[ "$C_DEL_OP" == "403" && "$C_DEL" == "204" && "$AUD" == "1" && "$(rec_count "$LQ")" == "0" ]]; echo $?)" \
  "1: DELETE /recordings: operator 403, admin 204 + audit recording.delete" "op=$C_DEL_OP admin=$C_DEL audit=$AUD"

# ---------------------------------------------------------------- 2. webhook
echo "=== 2. webhook ==="
TYPES1=$(wh_types /a "$L1")
check "$( [[ "$TYPES1" == "call.ringing call.answered call.ended" ]]; echo $?)" \
  "2: trunk -> 101: call.ringing -> call.answered -> call.ended (tartib, HMAC to'g'ri)" "$TYPES1 / all=$(wh_count /a "$L1")"
FACTS1=$(wh_ended_field /a "$L1" "'|'.join(str(c.get(k)) for k in ('direction','status','to','answered_by','did')) + '|' + str(c['billsec'] >= 5)")
check "$( [[ "$FACTS1" == "inbound|answered|101|101|$DID_101|True" ]]; echo $?)" \
  "2: ended: inbound, answered, to=101, answered_by=101, did, billsec >= 5" "$FACTS1"
RDID1=$(wh_query /a "$L1" "next((str(r['body']['call'].get('did')) for r in ok if r['event'] == 'call.ringing'), '')")
check "$( [[ "$RDID1" == "$DID_101" ]]; echo $?)" "2: call.ringing (jonli) da did = DID (channelvars'siz, VarSet)" "$RDID1"
CHVARS=$(docker exec "$AST" grep -c '^channelvars' /etc/asterisk/manager.conf)
check "$( [[ "$CHVARS" == "0" ]]; echo $?)" "2: manager.conf da channelvars yo'q (CDR dst buzilmasin; m2a qora ro'yxat)" "$CHVARS"
SIGALL=$(wh_query /a '*' 'all(r["sig_ok"] for r in rs) and len(rs) > 0')
check "$( [[ "$SIGALL" == "True" ]]; echo $?)" "2: barcha so'rovlarda X-Innova-Signature to'g'ri" "$SIGALL"

I0=$(invites 101)
call_bg 104 "104" "${SECRET[104]}" 101 3 ci
wait_until 20 call_done 104 ci; wait_until 10 no_calls
LI=$(linkedid_to_ext 101)
wait_until 20 ended_emitted "$LI"; sleep 3
INTERNAL_EV=$(sql "select count(*) from integration_events where call_id='$LI' and internal")
check "$(invites_gt 101 "$I0" && [[ "$LI" != "$L1" && "$(wh_count /a "$LI")" == "0" && "$INTERNAL_EV" -ge 1 ]]; echo $?)" \
  "2: ichki 104 -> 101 (include_internal=false) -> qabul qiluvchida 0 so'rov" \
  "L=$LI wh=$(wh_count /a "$LI") internal_events=$INTERNAL_EV"

WB_J=$(api POST /integrations/webhooks "{\"name\":\"M3bHookB\",\"url\":\"http://$WH_IP:$WH_PORT/b\",\"events\":[\"call.ended\"]}")
WB_ID=$(jget "$(jbody "$WB_J")" item id)
wh_config /b "$(jget "$(jbody "$WB_J")" secret)" 2
T_J=$(api POST "/integrations/webhooks/$WB_ID/test")
b_delivered() { [[ "$(wh_query /b '*' 'len(ok)')" -ge 1 ]]; }
wait_until 240 b_delivered
B_SEQ=$(wh_query /b '*' '",".join(str(r["status"]) for r in rs) + "|" + str(len({r["delivery"] for r in rs})) + "|" + rs[0]["event"]')
check "$( [[ "$(jcode "$T_J")" == "200" && "$B_SEQ" == "500,500,200|1|test.ping" ]]; echo $?)" \
  "2: qabul qiluvchi 2x500 -> 3-urinishda 200, X-Innova-Delivery bir xil" "test=$T_J seq=$B_SEQ"
DLV=$(jbody "$(api GET "/integrations/webhooks/$WB_ID/deliveries")")
DLV_S=$(jget "$DLV" items 0 status)"|"$(jget "$DLV" items 0 attempts)"|"$(jget "$DLV" items 0 http_status)
check "$( [[ "$DLV_S" == "delivered|3|200" ]]; echo $?)" "2: jurnal: status delivered, attempts=3, oxirgi 200" "$DLV_S"
DLV_ID=$(jget "$DLV" items 0 id)
RP_J=$(api POST "/integrations/deliveries/$DLV_ID/replay")
wait_until 15 sh -c "[ \"\$(curl -s http://$WH_IP:$WH_PORT/_requests?path=/b | python3 -c 'import json,sys;print(len(json.load(sys.stdin)))')\" = 4 ]"
check "$( [[ "$(jcode "$RP_J")" == "200" && "$(wh_count /b '*')" == "4" ]]; echo $?)" "2: replay -> qayta yetkazildi" \
  "$RP_J / $(wh_count /b '*')"
OLD_SECRET=$(jget "$(jbody "$WB_J")" secret)
ROT_J=$(api POST "/integrations/webhooks/$WB_ID/rotate-secret")
check "$( [[ "$(jcode "$ROT_J")" == "200" && "$(jget "$(jbody "$ROT_J")" secret)" == whsec_* && "$(jget "$(jbody "$ROT_J")" secret)" != "$OLD_SECRET" ]]; echo $?)" \
  "2: rotate-secret -> yangi secret" "$(jcode "$ROT_J")"
check "$( [[ "$(jcode "$(api DELETE "/integrations/webhooks/$WB_ID")")" == "204" ]]; echo $?)" "2: DELETE webhook B -> 204"

# ---------------------------------------------------------------- 3. bardoshlilik
echo "=== 3. api to'xtatilganda qo'ng'iroq tugaydi ==="
call_bg trunk trunk - "$DID_101" 10 c3
wait_until 15 call_answered trunk c3
L3=$(wait_for_sql "select linkedid from call_event_state where answered_sent and not ended_sent order by created_at desc limit 1" 10)
wait_until 10 wh_has /a "$L3" call.answered
check "$(wh_has /a "$L3" call.answered; echo $?)" "3: call.answered yetdi, endi docker stop api" "L=$L3 $(wh_types /a "$L3")"
docker stop "$APICONT" >/dev/null
wait_until 25 call_done trunk c3; wait_until 10 no_calls
check "$(call_done trunk c3 && ! wh_has /a "$L3" call.ended; echo $?)" "3: api yo'q paytda qo'ng'iroq tugadi (ended hali yo'q)" \
  "$(call_log trunk c3 | tail -2)"
docker start "$APICONT" >/dev/null
T0=$(date +%s)
wait_until 60 wh_has /a "$L3" call.ended
DT=$(( $(date +%s) - T0 ))
check "$(wh_has /a "$L3" call.ended && (( DT <= 60 )) && [[ "$(wh_query /a "$L3" 'sum(r["event"]=="call.ended" for r in rs)')" == "1" ]]; echo $?)" \
  "3: docker start api -> ${DT} s ichida call.ended (bir marta)" "$(wh_types /a "$L3")"
wait_api

# ---------------------------------------------------------------- 4. API kalitlar
echo "=== 4. API kalitlar va ochiq API ==="
key_of() { jget "$(jbody "$1")" key; }
KF_J=$(api POST /integrations/api-keys '{"name":"M3bFull","scopes":["calls:read","recordings:read","calls:originate","extensions:read"]}')
KE_J=$(api POST /integrations/api-keys '{"name":"M3bExt","scopes":["extensions:read"]}')
KR_J=$(api POST /integrations/api-keys '{"name":"M3bRevoked","scopes":["calls:read"]}')
KL_J=$(api POST /integrations/api-keys '{"name":"M3bLimit","scopes":["extensions:read"]}')
KF=$(key_of "$KF_J"); KE=$(key_of "$KE_J"); KR=$(key_of "$KR_J"); KL=$(key_of "$KL_J")
KF_PREFIX=$(jget "$(jbody "$KF_J")" item prefix)
check "$( [[ "$KF" =~ ^ipk_[A-Za-z0-9]{8}_[A-Za-z0-9]{32}$ && "$(jcode "$KF_J")" == "201" ]]; echo $?)" \
  "4: POST /api-keys -> ipk_<prefix8>_<secret32>" "$KF_J"
HASHED=$(sql "select count(*) from api_keys where key_hash = encode(sha256('$KF'::bytea), 'hex')")
check "$( [[ "$HASHED" == "1" && -z "$(sql "select 1 from api_keys where key_hash = '$KF'")" ]]; echo $?)" \
  "4: bazada faqat sha256" "$HASHED"
BADSCOPE=$(api POST /integrations/api-keys '{"name":"M3bBadScope","scopes":["calls:delete"]}')
check "$( [[ "$(jcode "$BADSCOPE")" == "422" ]]; echo $?)" "4: noma'lum scope -> 422" "$BADSCOPE"
api DELETE "/integrations/api-keys/$(jget "$(jbody "$KR_J")" item id)" >/dev/null
R_SCOPE=$(pub "$KE" GET /calls); R_REV=$(pub "$KR" GET /calls); R_NONE=$(pub "" GET /calls)
check "$(err_is "$R_SCOPE" 403 insufficient_scope; echo $?)" "4: scope'siz kalit -> 403 insufficient_scope" "$R_SCOPE"
check "$(err_is "$R_REV" 401 invalid_api_key && err_is "$R_NONE" 401 invalid_api_key; echo $?)" \
  "4: bekor qilingan / kalitsiz -> 401 invalid_api_key" "$R_REV / $R_NONE"
P1=$(pub "$KF" GET "/calls?limit=2")
CUR=$(jget "$(jbody "$P1")" next_cursor)
P2=$(pub "$KF" GET "/calls?limit=2&cursor=$CUR")
PAGES=$(python3 -c "
import json,sys
a=[c['linkedid'] for c in json.loads(sys.argv[1])['items']]; b=[c['linkedid'] for c in json.loads(sys.argv[2])['items']]
print(len(a), len(b), bool(set(a) & set(b)))" "$(jbody "$P1")" "$(jbody "$P2")")
check "$( [[ "$(jcode "$P1")" == "200" && -n "$CUR" && "$(jcode "$P2")" == "200" && "$PAGES" == "2 2 False" ]]; echo $?)" \
  "4: GET /calls?limit=2 -> 200 + next_cursor, 2-sahifa kesishmaydi" "$PAGES / $(jbody "$P1" | head -c 300)"
PC=$(pub "$KF" GET "/calls/$L1")
check "$( [[ "$(jcode "$PC")" == "200" && "$(jget "$(jbody "$PC")" item linkedid)" == "$L1" && "$(jget "$(jbody "$PC")" item recordings 0 id)" == "$REC1_ID" ]]; echo $?)" \
  "4: GET /calls/{linkedid} -> 200, recordings" "$(jbody "$PC" | head -c 300)"
check "$( [[ "$(http_code -H "Authorization: Bearer $KF" "$PUBLIC_BASE/recordings/$REC1_ID")" == "200" && "$(http_code -H "Authorization: Bearer $KE" "$PUBLIC_BASE/recordings/$REC1_ID")" == "403" ]]; echo $?)" \
  "4: yozuvni kalit bilan yuklash 200 (scope'siz 403)"
PE=$(pub "$KE" GET /extensions)
check "$( [[ "$(jcode "$PE")" == "200" ]] && grep -q '"number":"101"' <<<"$PE" && ! grep -qiE 'password|secret' <<<"$PE"; echo $?)" \
  "4: GET /extensions -> 200, sirlarsiz" "$(jbody "$PE" | head -c 200)"
LAST=$(sql "select last_used_at is not null from api_keys where prefix='$KF_PREFIX'")
check "$( [[ "$LAST" == "t" ]]; echo $?)" "4: last_used_at yangilandi" "$LAST"

O_CRLF=$(pub "$KF" POST /calls/originate '{"extension":"101","to":"99890\r\nAction: Hangup"}')
O_UNK=$(pub "$KF" POST /calls/originate '{"extension":"999","to":"998901112233"}')
O_SCOPE=$(pub "$KE" POST /calls/originate '{"extension":"101","to":"998901112233"}')
check "$(err_is "$O_CRLF" 422 invalid_number; echo $?)" "4: originate to ichida CR/LF -> 422 invalid_number" "$O_CRLF"
check "$(err_is "$O_UNK" 422 unknown_extension && err_is "$O_SCOPE" 403 insufficient_scope; echo $?)" \
  "4: mavjud bo'lmagan raqam -> 422; calls:originate'siz -> 403" "$O_UNK / $O_SCOPE"
I101=$(invites 101); ITR=$(invites trunk)
O_OK=$(pub "$KF" POST /calls/originate "{\"extension\":\"101\",\"to\":\"$ORIG_TO\",\"external_id\":\"crm:42\"}")
REQ_ID=$(jget "$(jbody "$O_OK")" request_id)
check "$( [[ "$(jcode "$O_OK")" == "202" && -n "$REQ_ID" ]]; echo $?)" "4: originate -> 202 {request_id}" "$O_OK"
wait_until 15 invites_gt 101 "$I101" && wait_until 15 invites_gt trunk "$ITR"
TR_INV=$(plog trunk | grep '^INVITE ' | tail -1)
check "$(invites_gt 101 "$I101" && [[ "$TR_INV" == *"ruri=sip:$ORIG_DIGITS@"* ]]; echo $?)" \
  "4: avval 101 jiringladi, javobdan keyin trunk UAS INVITE oldi (to=$ORIG_DIGITS)" "$TR_INV"
wait_until 10 wh_has /a "$REQ_ID" call.answered
ORIGIN=$(wh_query /a "$REQ_ID" '"|".join(sorted({str((r["body"]["call"].get("origin") or {}).get("source")) + ":" + str((r["body"]["call"].get("origin") or {}).get("external_id")) for r in ok}))')
check "$( [[ "$ORIGIN" == "api:crm:42" ]]; echo $?)" "4: hodisalarda call.origin = {source: api, external_id}" "$ORIGIN / $(wh_types /a "$REQ_ID")"
ast "channel request hangup all" >/dev/null; wait_until 10 no_calls
AUD=$(sql "select count(*) from audit_log where entity='call' and diff->>'api_key' is not null and entity_id='$REQ_ID'")
check "$( [[ "$AUD" == "1" ]]; echo $?)" "4: audit api.originate" "$AUD"
wait_until 20 wh_has /a "$REQ_ID" call.ended
check "$(wh_has /a "$REQ_ID" call.ended; echo $?)" "4: originate qo'ng'irog'i call.ended" "$(wh_types /a "$REQ_ID")"

RL=""
for _ in $(seq 1 125); do RL+="$(http_code -H "Authorization: Bearer $KL" "$PUBLIC_BASE/extensions") "; done
check "$( [[ "$(grep -o 200 <<<"$RL" | wc -l)" == "120" && "$(grep -o 429 <<<"$RL" | wc -l)" == "5" ]]; echo $?)" \
  "4: 125 so'rov/daq -> 120 ta 200, keyin 429" "200=$(grep -o 200 <<<"$RL" | wc -l) 429=$(grep -o 429 <<<"$RL" | wc -l)"

# ---------------------------------------------------------------- (+) CRM ssenariylari
if [[ -f "$LIB_DIR/m3b_crm_scenario.sh" ]]; then
  echo "=== CRM ssenariylari (m3b_crm_scenario.sh) ==="
  # shellcheck source=/dev/null
  source "$LIB_DIR/m3b_crm_scenario.sh"
fi

echo "=== NATIJA: PASS=$PASS FAIL=$FAIL ==="
[[ "$FAIL" -eq 0 ]]
