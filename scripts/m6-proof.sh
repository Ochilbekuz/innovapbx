#!/usr/bin/env bash
# M6 isboti (replica/m6-contract.md): kampaniyalar — avtoinformator / avtoterish.
#   1. API: 422 kodlari, name_taken, 409 campaign_empty / stale, noma'lum amal 404.
#   2. Import: sarlavha, takror, xato qator, qora ro'yxat -> skipped BLACKLIST, CSV-formula.
#   3. Avtoinformator (trunk javob beradi): max_concurrent=2 oshmaydi, audio ijro, done + billsec, completed.
#   4. Band: BUSY -> retry -> (next_attempt_at) -> failed; jiringlash: CANCEL -> NOANSWER.
#   5. DTMF «9» -> skipped OPTOUT + campaign_optouts; keyingi kampaniyada import'da skipped OPTOUT.
#   6. DTMF «1» -> operator (201) ga ulanadi, stats.connected=1.
#   7. Oyna tashqarisida terilmaydi; pause/PATCH/start -> teriladi; stop -> qayta start 409; running'da PATCH/DELETE 409.
#   8. Eksport CSV, jurnal campaign.*, dialplan kontekstlari.
# Foydalanish: scripts/m6-proof.sh [--fresh]
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"
SIPP_DIR="$ROOT_DIR/tests/sipp"
LIB_DIR="$ROOT_DIR/scripts/lib"
API_BASE="${API_BASE:-http://127.0.0.1:8710/api/v1}"
API_ROOT="${API_BASE%/api/v1}"
PROJECT="innova-m0"
NET="${PROJECT}_innova-net"
PY_IMAGE="python:3.12-slim"
PG=innova-m0-postgres-1
AST=innova-m0-asterisk-1

declare -A IP=([201]="172.21.0.190" [trunk]="172.21.0.191")
CID="712000000"
BLACK="998900000099"
OPTOUT_NUM="998900000051"

source "$LIB_DIR/m2a_common.sh"
source "$LIB_DIR/m3b_common.sh"

ADMIN_PASSWORD="${PROOF_ADMIN_PASSWORD:-$(grep -E '^PROOF_ADMIN_PASSWORD=' "$DEPLOY_DIR/.env" | cut -d= -f2-)}"
[[ -n "$ADMIN_PASSWORD" ]] || { echo "PROOF_ADMIN_PASSWORD deploy/.env da yo'q"; exit 2; }

CONTAINERS=(m6-proof-201 m6-proof-trunk)
cleanup() { docker rm -f "${CONTAINERS[@]}" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

if [[ "${1:-}" == "--fresh" ]]; then
  echo "--- --fresh: stack qayta quriladi ---"
  (cd "$DEPLOY_DIR" && docker compose -p "$PROJECT" down -v) || true
  (cd "$DEPLOY_DIR" && docker compose -p "$PROJECT" build) || { fail "docker compose build"; exit 1; }
  (cd "$DEPLOY_DIR" && docker compose -p "$PROJECT" up -d) || { fail "docker compose up"; exit 1; }
  wait_api
fi

echo "=== setup/login ==="
login "$ADMIN_PASSWORD" || { fail "login"; exit 1; }
LEFTOVER=$(sql "select count(*) from campaigns")
if [[ "$LEFTOVER" != "0" ]]; then
  echo "Stekda oldingi kampaniyalar bor ($LEFTOVER) — 'scripts/m6-proof.sh --fresh' bilan ishga tushiring."
  exit 2
fi

echo "=== resurslar ==="
J=$(jbody "$(api POST /extensions '{"number":"201","name":"M6Operator","ring_seconds":10}')")
EXT_ID=$(jget "$J" item id); SECRET=$(jget "$J" sip password)
TRUNK_ID=$(jget "$(jbody "$(api POST /trunks "{\"name\":\"M6Trunk\",\"host\":\"${IP[trunk]}\",\"port\":5060,\"match\":[\"${IP[trunk]}/32\"],\"codecs\":[\"ulaw\"],\"max_channels\":5,\"enabled\":true}")")" item id)
ROUTE=$(api POST /outbound-routes "{\"name\":\"M6Route\",\"priority\":1,\"patterns\":[{\"pattern\":\"998XXXXXXXXX\"}],\"trunk_ids\":[\"$TRUNK_ID\"],\"international\":false}")
AUDIO_ID=$(jget "$(jbody "$(api GET /audio)")" items 0 id)
BL=$(api POST /blacklist "{\"number\":\"$BLACK\",\"reason\":\"m6\"}")
check "$( [[ -n "$EXT_ID" && -n "$TRUNK_ID" && -n "$AUDIO_ID" && "$(jcode "$ROUTE")" == "201" && "$(jcode "$BL")" == "201" ]]; echo $?)" \
  "201 + trunk + marshrut 998XXXXXXXXX + tizim audiosi + qora ro'yxat" "$ROUTE / $BL"
check "$(ast "dialplan show t1-campaign-answer" | grep -q "Read(INNOVA_CAMP_KEY"; ast "dialplan show t1-campaign-dial" | grep -q "hangup_handler_push"; echo $?)" \
  "8: Asterisk: t1-campaign-dial / -answer kontekstlari yuklangan"

echo "=== telefonlar ==="
for c in 201 trunk; do
  docker run -d --name "m6-proof-$c" --network "$NET" --ip "${IP[$c]}" "$PY_IMAGE" sleep infinity >/dev/null
  docker cp "$SIPP_DIR/m2a_phone.py" "m6-proof-$c:/tmp/m2a_phone.py"
  for f in outbound_invite.py vm_caller.py; do docker cp "$SIPP_DIR/$f" "m6-proof-$c:/tmp/$f"; done
done
docker exec m6-proof-201 sh -c "echo answer > /tmp/mode"
docker exec -d m6-proof-201 sh -c "cd /tmp && python3 m2a_phone.py serve t1-201 '$SECRET' 5070 12000 /tmp/mode 900 > /tmp/phone.log 2>&1"
docker exec m6-proof-trunk sh -c "echo answer > /tmp/mode"
docker exec -d m6-proof-trunk sh -c "cd /tmp && python3 m2a_phone.py serve trunk - 5060 12000 /tmp/mode 900 > /tmp/phone.log 2>&1"
registered() { docker exec m6-proof-201 grep -q 'REGISTER_RESULT: OK' /tmp/phone.log 2>/dev/null; }
wait_until 15 registered && pass "201 REGISTER -> 200 OK" || fail "REGISTER"

mode() { docker exec m6-proof-trunk sh -c "echo '$1' > /tmp/mode"; }
plog() { docker exec "m6-proof-$1" cat /tmp/phone.log 2>/dev/null; }
invites() { plog "$1" | grep -c '^INVITE '; }
cancels() { plog trunk | grep -c '^REQ CANCEL'; }
ALL_DAY='"window_start":"00:00:00","window_end":"23:59:59","days":[1,2,3,4,5,6,7]'
camp_create() { # json -> $C (javob), $CID_ (id)
  C=$(api POST /campaigns "$1"); CID_=$(jget "$(jbody "$C")" item id 2>/dev/null)
}
camp_import() { IMP=$(api POST "/campaigns/$1/contacts/import" "$(python3 -c 'import json,sys;print(json.dumps({"csv":sys.argv[1]}))' "$2")"); }
camp_do() { api POST "/campaigns/$1/$2"; }
camp_status() { sql "select status from campaigns where id='$1'"; }
cst() { sql "select status||'|'||coalesce(result,'')||'|'||attempts||'|'||coalesce(billsec,0)||'|'||coalesce(key,'') from campaign_contacts where campaign_id='$1' and number='$2'"; }
is_status() { [[ "$(camp_status "$1")" == "$2" ]]; }
contact_is() { [[ "$(cst "$1" "$2" | cut -d'|' -f1)" == "$3" ]]; }
dialing_max() { # id max_s -> kampaniya completed bo'lguncha bir vaqtdagi `dialing` maksimumi
  local m=0 c i
  for (( i = 0; i < $2 * 3; i++ )); do
    c=$(sql "select count(*) from campaign_contacts where campaign_id='$1' and status='dialing'")
    (( c > m )) && m=$c
    is_status "$1" completed && break
    sleep 0.3
  done
  echo "$m"
}

echo "--- 1. API tekshiruvlari ---"
for spec in '{"name":"X","mode":"message"}|campaign_audio_required' \
            '{"name":"X","mode":"connect"}|campaign_target_required' \
            '{"name":"X","mode":"connect","target_number":"299"}|campaign_bad_target' \
            "{\"name\":\"X\",\"mode\":\"message\",\"audio_id\":\"00000000-0000-0000-0000-000000000000\"}|campaign_bad_audio" \
            '{"name":"X","mode":"connect","target_number":"201","dtmf_optout":true}|campaign_dtmf_mode' \
            "{\"name\":\"X\",\"mode\":\"message\",\"audio_id\":\"$AUDIO_ID\",\"window_start\":\"09:00\",\"window_end\":\"09:00\"}|campaign_window" \
            "{\"name\":\"X\",\"mode\":\"message\",\"audio_id\":\"$AUDIO_ID\",\"days\":[8]}|campaign_days"; do
  camp_create "${spec%%|*}"
  check "$(err_is "$C" 422 "${spec##*|}"; echo $?)" "1: POST -> 422 ${spec##*|}" "$C"
done
camp_create '{"name":"X","mode":"message","ring_seconds":5}'
check "$(err_is "$C" 422 validation_error; echo $?)" "1: ring_seconds=5 -> 422 validation_error" "$C"
camp_create "{\"name\":\"M6 Avto\",\"mode\":\"message\",\"audio_id\":\"$AUDIO_ID\",\"callerid\":\"$CID\",\"max_concurrent\":2,\"max_attempts\":1,\"ring_seconds\":15,$ALL_DAY}"
A=$CID_
check "$( [[ "$(jcode "$C")" == "201" && "$(jget "$(jbody "$C")" item status)" == "draft" ]]; echo $?)" "1: POST -> 201 draft" "$C"
camp_create "{\"name\":\"M6 Avto\",\"mode\":\"message\",\"audio_id\":\"$AUDIO_ID\"}"
check "$(err_is "$C" 422 name_taken; echo $?)" "1: nom takrori -> 422 name_taken" "$C"
R=$(camp_do "$A" start)
check "$(err_is "$R" 409 campaign_empty; echo $?)" "1: kontaktsiz start -> 409 campaign_empty" "$R"
R=$(camp_do "$A" restart)
check "$( [[ "$(jcode "$R")" == "404" ]]; echo $?)" "1: noma'lum amal -> 404" "$R"
R=$(api PATCH "/campaigns/$A" '{"max_concurrent":3,"updated_at":"2020-01-01T00:00:00Z"}')
check "$(err_is "$R" 409 stale; echo $?)" "1: eskirgan updated_at -> 409 stale" "$R"

echo "--- 2. import ---"
camp_import "$A" "$(printf 'Telefon;Ism\n998900000001;Ali\n+998 90 000 00 02;=HYPERLINK("x")\n998900000001;Takror\nxato;Vali\n%s;Qora\n998900000003;Uch\n' "$BLACK")"
IJ=$(jbody "$IMP")
check "$( [[ "$(jcode "$IMP")" == "200" && "$(jget "$IJ" added)" == "3" && "$(jget "$IJ" duplicates)" == "1" \
  && "$(jget "$IJ" skipped)" == "1" && "$(jget "$IJ" invalid_count)" == "1" && "$(jget "$IJ" invalid 0 line)" == "5" ]]; echo $?)" \
  "2: import -> added 3, duplicates 1, skipped 1 (qora), invalid 1 (5-qator)" "$IJ"
check "$( [[ "$(cst "$A" "$BLACK")" == "skipped|BLACKLIST|0|0|" ]]; echo $?)" "2: qora ro'yxatdagi raqam -> skipped BLACKLIST" "$(cst "$A" "$BLACK")"

echo "--- 3. avtoinformator: javob, max_concurrent=2 ---"
mode answer
INV0=$(invites trunk)
R=$(camp_do "$A" start)
check "$( [[ "$(jcode "$R")" == "200" && "$(jget "$(jbody "$R")" item status)" == "running" ]]; echo $?)" "3: start -> running" "$R"
MAXD=$(dialing_max "$A" 60)
check "$(is_status "$A" completed; echo $?)" "3: barcha kontakt tugadi -> completed" "$(camp_status "$A")"
check "$( [[ "$MAXD" == "2" ]]; echo $?)" "3: bir vaqtda dialing maksimumi = max_concurrent (2)" "max=$MAXD"
check "$( [[ $(( $(invites trunk) - INV0 )) == 3 ]]; echo $?)" "3: trunk 3 ta INVITE oldi (qora ro'yxat terilmadi)" "$(plog trunk | grep '^INVITE' | tail -3)"
check "$(plog trunk | grep '^INVITE' | tail -3 | grep -q "from=$CID"; echo $?)" "3: CallerID = kampaniya callerid ($CID)" "$(plog trunk | grep '^INVITE' | tail -1)"
S1=$(cst "$A" 998900000001)
check "$( [[ "$S1" == done\|ANSWER\|1\|* && "$(cut -d'|' -f4 <<<"$S1")" -ge 1 ]]; echo $?)" "3: kontakt done ANSWER, billsec >= 1" "$S1"
check "$( [[ "$(sql "select count(*) from campaign_attempts where campaign_id='$A' and dial_status='ANSWER' and ended_at is not null")" == "3" ]]; echo $?)" \
  "3: campaign_attempts: 3 ta ANSWER (hangup handler -> /internal/campaigns/result)"
check "$( [[ "$(plog trunk | grep -c '^REQ BYE')" -ge 3 ]]; echo $?)" "3: audio'dan keyin Asterisk o'zi BYE yubordi" "$(plog trunk | grep -c '^REQ BYE')"
ST=$(jbody "$(api GET "/campaigns/$A")")
check "$( [[ "$(jget "$ST" item stats done)" == "3" && "$(jget "$ST" item stats skipped)" == "1" && "$(jget "$ST" item stats total)" == "4" ]]; echo $?)" \
  "3: stats total 4 / done 3 / skipped 1" "$ST"

echo "--- 4. band -> retry -> failed; jiringlash -> NOANSWER ---"
camp_create "{\"name\":\"M6 Band\",\"mode\":\"message\",\"audio_id\":\"$AUDIO_ID\",\"max_attempts\":2,\"retry_delay_s\":60,\"ring_seconds\":10,$ALL_DAY}"
B=$CID_
camp_import "$B" "998900000011"
mode busy
camp_do "$B" start >/dev/null
wait_until 20 contact_is "$B" 998900000011 retry
S=$(cst "$B" 998900000011)
NEXT=$(sql "select extract(epoch from next_attempt_at - last_attempt_at)::int from campaign_contacts where campaign_id='$B'")
check "$( [[ "$S" == "retry|BUSY|1|0|" && "$NEXT" -ge 55 && "$NEXT" -le 65 ]]; echo $?)" "4: 486 -> retry BUSY, keyingi urinish ~60 s keyin" "$S / $NEXT s"
sql "update campaign_contacts set next_attempt_at=now() where campaign_id='$B'" >/dev/null
wait_until 20 is_status "$B" completed
S=$(cst "$B" 998900000011)
check "$( [[ "$S" == "failed|BUSY|2|0|" ]]; echo $?)" "4: 2-urinish ham band -> failed (max_attempts=2), completed" "$S / $(camp_status "$B")"

camp_create "{\"name\":\"M6 Jiring\",\"mode\":\"message\",\"audio_id\":\"$AUDIO_ID\",\"max_attempts\":1,\"ring_seconds\":10,$ALL_DAY}"
J2=$CID_
camp_import "$J2" "998900000021"
mode ring
CAN0=$(cancels)
T0=$(date +%s)
camp_do "$J2" start >/dev/null
wait_until 30 is_status "$J2" completed
T1=$(date +%s)
S=$(cst "$J2" 998900000021)
check "$( [[ "$S" == "failed|NOANSWER|1|0|" ]]; echo $?)" "4: javobsiz (ring 10 s) -> failed NOANSWER" "$S"
check "$( [[ $(( $(cancels) - CAN0 )) -ge 1 && $(( T1 - T0 )) -ge 9 ]]; echo $?)" "4: trunk CANCEL oldi, ~10 s jiringladi" "$(( T1 - T0 )) s"

echo "--- 5. DTMF 9 -> opt-out ---"
camp_create "{\"name\":\"M6 Optout\",\"mode\":\"message\",\"audio_id\":\"$AUDIO_ID\",\"dtmf_optout\":true,\"dtmf_connect\":true,\"target_number\":\"201\",\"max_attempts\":2,\"ring_seconds\":15,$ALL_DAY}"
O=$CID_
camp_import "$O" "$OPTOUT_NUM"
mode answer:9
camp_do "$O" start >/dev/null
wait_until 30 is_status "$O" completed
S=$(cst "$O" "$OPTOUT_NUM")
check "$( [[ "$S" == skipped\|OPTOUT\|1\|*\|9 ]]; echo $?)" "5: «9» -> skipped OPTOUT, key=9 (qayta terilmaydi)" "$S"
check "$( [[ "$(sql "select count(*) from campaign_optouts where number='$OPTOUT_NUM'")" == "1" ]]; echo $?)" "5: campaign_optouts yozuvi"
check "$( [[ "$(sql "select key from campaign_attempts where campaign_id='$O'")" == "9" ]]; echo $?)" "5: urinishda key=9"

echo "--- 6. DTMF 1 -> operatorga ulash ---"
camp_create "{\"name\":\"M6 Ulash\",\"mode\":\"message\",\"audio_id\":\"$AUDIO_ID\",\"dtmf_optout\":true,\"dtmf_connect\":true,\"target_number\":\"201\",\"max_attempts\":1,\"ring_seconds\":15,$ALL_DAY}"
U=$CID_
camp_import "$U" "$(printf '998900000061\n%s\n' "$OPTOUT_NUM")"
check "$( [[ "$(jget "$(jbody "$IMP")" skipped)" == "1" && "$(cst "$U" "$OPTOUT_NUM")" == "skipped|OPTOUT|0|0|" ]]; echo $?)" \
  "5: opt-out keyingi kampaniyada ham -> import'da skipped OPTOUT" "$(jbody "$IMP")"
mode answer:1
INV201=$(invites 201)
camp_do "$U" start >/dev/null
op_answered() { (( $(invites 201) > INV201 )) && plog 201 | tail -5 | grep -q ANSWERED; }
wait_until 30 op_answered
check "$(op_answered; echo $?)" "6: «1» -> 201 ga INVITE, operator javob berdi" "$(plog 201 | tail -3)"
plog 201 | grep '^INVITE' | tail -1 | grep -q "from=998900000061" && pass "6: operatorga mijoz raqami ko'rinadi" \
  || fail "6: operator CallerID -> $(plog 201 | grep '^INVITE' | tail -1)"
sleep 2
ast "channel request hangup all" >/dev/null
wait_until 20 is_status "$U" completed
S=$(cst "$U" 998900000061)
check "$( [[ "$S" == done\|ANSWER\|1\|*\|1 && "$(cut -d'|' -f4 <<<"$S")" -ge 3 ]]; echo $?)" "6: kontakt done ANSWER key=1, billsec ulanish bilan" "$S"
check "$( [[ "$(jget "$(jbody "$(api GET "/campaigns/$U")")" item stats connected)" == "1" ]]; echo $?)" "6: stats.connected = 1"

echo "--- 7. oyna, pause/stop, holat qoidalari ---"
H=$(TZ=Asia/Tashkent date +%-H)
WS=$(printf '%02d:00:00' $(( (H + 2) % 24 ))); WE=$(printf '%02d:00:00' $(( (H + 3) % 24 )))
camp_create "{\"name\":\"M6 Oyna\",\"mode\":\"message\",\"audio_id\":\"$AUDIO_ID\",\"max_attempts\":1,\"window_start\":\"$WS\",\"window_end\":\"$WE\",\"days\":[1,2,3,4,5,6,7]}"
W=$CID_
camp_import "$W" "998900000071"
mode answer
INV0=$(invites trunk)
camp_do "$W" start >/dev/null
sleep 6
check "$( [[ "$(invites trunk)" == "$INV0" && "$(cst "$W" 998900000071)" == pending* && "$(camp_status "$W")" == "running" ]]; echo $?)" \
  "7: oyna ($WS-$WE) tashqarisida -> terilmadi, pending" "$(cst "$W" 998900000071)"
STAMP=$(jget "$(jbody "$(api GET "/campaigns/$W")")" item updated_at)
R=$(api PATCH "/campaigns/$W" "{\"max_concurrent\":3,\"updated_at\":\"$STAMP\"}")
check "$(err_is "$R" 409 campaign_running; echo $?)" "7: running'da PATCH -> 409 campaign_running" "$R"
R=$(api DELETE "/campaigns/$W")
check "$(err_is "$R" 409 campaign_running; echo $?)" "7: running'da DELETE -> 409 campaign_running" "$R"
R=$(camp_do "$W" pause)
check "$( [[ "$(jget "$(jbody "$R")" item status)" == "paused" ]]; echo $?)" "7: pause -> paused" "$R"
STAMP=$(jget "$(jbody "$R")" item updated_at)
R=$(api PATCH "/campaigns/$W" "{${ALL_DAY},\"updated_at\":\"$STAMP\"}")
check "$( [[ "$(jcode "$R")" == "200" ]]; echo $?)" "7: paused'da oynani o'zgartirish -> 200" "$R"
camp_do "$W" start >/dev/null
wait_until 30 is_status "$W" completed
check "$( [[ "$(cst "$W" 998900000071)" == done\|ANSWER* ]]; echo $?)" "7: oyna ochilgach -> terildi, done" "$(cst "$W" 998900000071)"

camp_create "{\"name\":\"M6 Stop\",\"mode\":\"message\",\"audio_id\":\"$AUDIO_ID\",\"window_start\":\"$WS\",\"window_end\":\"$WE\"}"
X=$CID_
camp_import "$X" "998900000081"
R=$(camp_do "$X" stop)
check "$( [[ "$(jget "$(jbody "$R")" item status)" == "stopped" && -n "$(sql "select finished_at from campaigns where id='$X'")" ]]; echo $?)" \
  "7: stop -> stopped, finished_at" "$R"
R=$(camp_do "$X" start)
check "$(err_is "$R" 409 campaign_bad_state; echo $?)" "7: stopped -> start 409 campaign_bad_state" "$R"
camp_import "$X" "998900000082"
check "$(err_is "$IMP" 409 campaign_bad_state; echo $?)" "7: stopped kampaniyaga import -> 409" "$IMP"
R=$(api DELETE "/campaigns/$X")
check "$( [[ "$(jcode "$R")" == "204" && "$(sql "select count(*) from campaign_contacts where campaign_id='$X'")" == "0" ]]; echo $?)" \
  "7: DELETE -> 204, kontaktlar CASCADE" "$R"

echo "--- 8. eksport, jurnal ---"
EXP=$(jbody "$(api GET "/campaigns/$A/export.csv")")
check "$( [[ "$(head -1 <<<"$EXP" | tr -d '\r')" == "number,name,status,result,attempts,billsec,key,last_attempt_at" ]] \
  && grep -q '^998900000001,Ali,done,ANSWER,1,' <<<"$EXP" && grep -q "^998900000002,\"'=HYPERLINK" <<<"$EXP" \
  && grep -q "^$BLACK,Qora,skipped,BLACKLIST,0," <<<"$EXP"; echo $?)" \
  "8: export.csv: sarlavha, natijalar, formula himoyasi (')" "$EXP"
R=$(api GET "/campaigns/$A/contacts?status=done&page_size=2")
check "$( [[ "$(jget "$(jbody "$R")" total)" == "3" && "$(jbody "$R" | python3 -c 'import json,sys;print(len(json.load(sys.stdin)["items"]))')" == "2" ]]; echo $?)" \
  "8: contacts?status=done -> total 3, sahifa 2" "$R"
AUD=$(sql "select string_agg(distinct 'campaign.'||(diff->>'op'), ' ') from audit_log where entity='campaign'")
check "$( [[ "$AUD" == *campaign.create* && "$AUD" == *campaign.import* && "$AUD" == *campaign.start* \
  && "$AUD" == *campaign.pause* && "$AUD" == *campaign.stop* && "$AUD" == *campaign.update* && "$AUD" == *campaign.delete* ]]; echo $?)" \
  "8: jurnal campaign.{create,import,start,pause,stop,update,delete}" "$AUD"
check "$( [[ "$(sql "select count(*) from campaign_contacts where status='dialing'")" == "0" ]]; echo $?)" "8: osilib qolgan dialing yo'q"

echo
echo "=== NATIJA: PASS=$PASS FAIL=$FAIL ==="
(( FAIL == 0 ))
