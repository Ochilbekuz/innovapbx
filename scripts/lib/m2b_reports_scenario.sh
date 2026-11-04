# shellcheck shell=bash
# Innova PBX — M2b ssenariy 7: Analitika (m2b-contract.md §5, §6.7).
#
# BU FAYL MUSTAQIL ISHLAMAYDI: `scripts/m2b-proof.sh` ichida (3-6 ssenariylardan
# KEYIN) `source` qilinadi va chaqiruvchi skriptdagi global o'zgaruvchi/
# funksiyalarga tayanadi: `pass`/`fail`/`check`, `api`/`jbody`/`jcode`/`jget`,
# `place_call_bg`/`call_done`/`mode`/`ast`, `member_action`, `wait_until`,
# `EXT_ID`/`SECRET`, `QUEUE_ID`, `AUTH`/`API_BASE`, `NET`/`PY_IMAGE`/`SIPP_DIR`,
# `CONTAINERS`.
#
# "Bugun" sonlari OLDIN/KEYIN farqi (delta) bilan tekshiriladi: bazada boshqa
# ssenariylar qoldirgan yozuvlar bor. Delta isbot yaratgan qo'ng'iroqlar soniga
# AYNAN teng bo'lishi kerak.
#
# Oqim:
#   a. Hamma qo'ng'iroq (5-6 ssenariy: q5a 14 s + ChanSpy) tugashini kutish —
#      aks holda ularning CDR/queue_log yozuvlari "keyin" o'qishga tushib qoladi
#      (1-urinishda shunday bo'lgan: 101 hali band edi, delta +4).
#   b. Trunk (alohida IP, `match`) + 2 DID: 712000600 -> navbat, 712000105 ->
#      105 (ro'yxatdan o'tmagan -> javobsiz).
#   c. OLDIN: /reports/summary|queues|agents.
#   d. t7a: trunk -> 600, 101 javob beradi       -> inbound+1, answered+1, navbat entered/answered +1
#      t7b: trunk -> 105, hech kim javob bermaydi -> inbound+1, missed+1
#      q7c: 104 -> 600, 101 jiringlaydi-yu olmaydi (agent_ring 8 s), chaqiruvchi
#           10 s da o'zi tashlaydi                -> internal+1, navbat entered+1, abandoned+1,
#                                                    agents[101].missed_ring +1 (RINGNOANSWER)
#   e. KEYIN: delta, hourly yig'indisi == summary, 102 login/pauza vaqti > 0.

echo "--- 7. analitika ---"

TODAY=$(python3 -c "
from datetime import datetime
from zoneinfo import ZoneInfo
print(datetime.now(ZoneInfo('Asia/Tashkent')).date().isoformat())")
TRUNK_IP="172.28.0.184"
DID_QUEUE="712000600"
DID_MISSED="712000105"

reports_get() { REP_OUT=$(api GET "/reports/$1"); }   # path?query -> $REP_OUT
rbody() { jbody "$REP_OUT"; }
rcode() { jcode "$REP_OUT"; }
queue_row_field() { jget "$1" items 0 "$2"; }         # queue_id filtri -> doim 1 item

agent_field() { # json_tana ext_raqam maydon -> qiymat (yo'q bo'lsa bo'sh)
  python3 -c "
import json, sys
d = json.load(sys.stdin)
row = next((r for r in d['items'] if r['extension'] == sys.argv[1]), None)
v = row.get(sys.argv[2]) if row else None
print('' if v is None else v)
" "$2" "$3" <<<"$1"
}

hourly_sum() { # json_tana maydon -> 24 soat yig'indisi
  python3 -c "
import json, sys
print(sum(r[sys.argv[1]] for r in json.load(sys.stdin)['items']))" "$2" <<<"$1"
}

target_of() { # kind matn -> label'ida matn bo'lgan birinchi call_targets id
  python3 -c "
import json, sys
d = json.load(sys.stdin)
print(next((i['id'] for i in d['items'] if sys.argv[1] in i['label']), ''))
" "$2" <<<"$(curl -s "$API_BASE/targets?kind=$1&q=$2" "${AUTH[@]}")"
}

no_calls() { ast "core show channels count" | grep -q "^0 active calls"; }

delta_check() { # nom kutilgan oldin keyin
  check "$( [[ "$(($4 - $3))" == "$2" ]]; echo $?)" "7: $1 +$2" "oldin=$3 keyin=$4"
}

snapshot() { # prefiks -> ${prefiks}_SUM / _Q / _AG
  reports_get "summary?from=$TODAY&to=$TODAY"; printf -v "${1}_SUM" '%s' "$(rbody)"
  check "$( [[ "$(rcode)" == "200" ]]; echo $?)" "7: GET /reports/summary ($1) -> 200" "$REP_OUT"
  reports_get "queues?from=$TODAY&to=$TODAY&queue_id=$QUEUE_ID"; printf -v "${1}_Q" '%s' "$(rbody)"
  check "$( [[ "$(rcode)" == "200" ]]; echo $?)" "7: GET /reports/queues ($1) -> 200" "$REP_OUT"
  reports_get "agents?from=$TODAY&to=$TODAY&queue_id=$QUEUE_ID"; printf -v "${1}_AG" '%s' "$(rbody)"
  check "$( [[ "$(rcode)" == "200" ]]; echo $?)" "7: GET /reports/agents ($1) -> 200" "$REP_OUT"
}

# --- a. oldingi qo'ng'iroqlar tugashi ----------------------------------------
wait_until 40 no_calls && pass "7: oldingi qo'ng'iroqlar tugadi (0 active calls)" \
  || fail "7: kanallar qolib ketdi ($(ast 'core show channels concise'))"
sleep 2   # cdr_pgsql / queue_log yozuvi hangup'dan keyin

# --- b. trunk + DID'lar ------------------------------------------------------
CONTAINERS+=(m2b-proof-trunk)
docker run -d --name m2b-proof-trunk --network "$NET" --ip "$TRUNK_IP" "$PY_IMAGE" sleep infinity >/dev/null
for f in outbound_invite.py vm_caller.py m2a_phone.py; do docker cp "$SIPP_DIR/$f" "m2b-proof-trunk:/tmp/$f"; done
TJ=$(api POST /trunks "{\"name\":\"M2bTrunk\",\"host\":\"$TRUNK_IP\",\"port\":5060,\"match\":[\"$TRUNK_IP/32\"],\"codecs\":[\"ulaw\"],\"max_channels\":5,\"enabled\":true}")
check "$( [[ "$(jcode "$TJ")" == "201" ]]; echo $?)" "7: POST /trunks -> M2bTrunk" "$TJ"
Q_TARGET=$(target_of queue M2bQueue); X105_TARGET=$(target_of extension 105)
for pair in "$DID_QUEUE:$Q_TARGET" "$DID_MISSED:$X105_TARGET"; do
  RJ=$(api POST /inbound-routes "{\"name\":\"M2bDid${pair%%:*}\",\"did\":\"${pair%%:*}\",\"target_id\":\"${pair#*:}\",\"enabled\":true}")
  check "$( [[ "$(jcode "$RJ")" == "201" ]]; echo $?)" "7: POST /inbound-routes ${pair%%:*}" "$RJ"
done
trunk_call() { # nom did talk_s -> trunk konteyneridan (IP identify, digest yo'q)
  CALL_N=$((CALL_N + 1))
  docker exec -d m2b-proof-trunk sh -c "cd /tmp && python3 m2a_phone.py call 'trunk' '-' $((6070 + CALL_N)) $((14000 + CALL_N * 2)) '$2' $3 > /tmp/$1.log 2>&1"
}

# --- c. OLDIN ----------------------------------------------------------------
snapshot B

# --- d. qo'ng'iroqlar --------------------------------------------------------
mode 101 answer
trunk_call t7a "$DID_QUEUE" 3
wait_until 20 call_done trunk t7a || fail "7: t7a tugamadi ($(call_log trunk t7a))"
check "$(call_log trunk t7a | grep -q 'INVITE_FINAL: SIP/2.0 200'; echo $?)" "7: t7a trunk -> 600 -> javob" "$(call_log trunk t7a)"
trunk_call t7b "$DID_MISSED" 3
wait_until 40 call_done trunk t7b || fail "7: t7b tugamadi ($(call_log trunk t7b))"
mode 101 ring
place_call_bg q7c caller 104 "${SECRET[104]}" 600 10
wait_until 25 call_done caller q7c || fail "7: q7c tugamadi ($(call_log caller q7c))"
mode 101 answer
wait_until 20 no_calls; sleep 2

# --- e. KEYIN ----------------------------------------------------------------
snapshot A
reports_get "hourly?from=$TODAY&to=$TODAY"; HOURLY_A=$(rbody)
check "$( [[ "$(rcode)" == "200" ]]; echo $?)" "7: GET /reports/hourly -> 200" "$REP_OUT"

for f in total inbound internal answered missed; do
  case $f in total) want=3;; inbound) want=2;; internal|answered|missed) want=1;; esac
  delta_check "summary.$f" "$want" "$(jget "$B_SUM" "$f")" "$(jget "$A_SUM" "$f")"
done
for f in entered:2 answered:1 abandoned:1; do
  delta_check "queues.${f%%:*}" "${f#*:}" "$(queue_row_field "$B_Q" "${f%%:*}")" "$(queue_row_field "$A_Q" "${f%%:*}")"
done
MR_B=$(agent_field "$B_AG" 101 missed_ring); MR_A=$(agent_field "$A_AG" 101 missed_ring)
delta_check "agents[101].missed_ring (RINGNOANSWER)" 1 "${MR_B:-0}" "${MR_A:-0}"

HS_IN=$(hourly_sum "$HOURLY_A" inbound); HS_ANS=$(hourly_sum "$HOURLY_A" answered); HS_MISS=$(hourly_sum "$HOURLY_A" missed)
check "$( [[ "$HS_IN" == "$(jget "$A_SUM" inbound)" && "$HS_ANS" == "$(jget "$A_SUM" answered)" \
  && "$HS_MISS" == "$(jget "$A_SUM" missed)" ]]; echo $?)" "7: hourly yig'indisi == summary (inbound/answered/missed)" \
  "hourly: $HS_IN/$HS_ANS/$HS_MISS summary: $(jget "$A_SUM" inbound)/$(jget "$A_SUM" answered)/$(jget "$A_SUM" missed)"

# 102 — dinamik: 3-ssenariyda kirgan, 5-dan beri pauzada (101 statik -> login hodisasi yo'q).
LOGIN_102=$(agent_field "$A_AG" 102 login_seconds); PAUSE_102=$(agent_field "$A_AG" 102 pause_seconds)
check "$( [[ -n "$LOGIN_102" && "$LOGIN_102" -gt 0 ]]; echo $?)" "7: agents[102].login_seconds > 0" "$LOGIN_102"
check "$( [[ -n "$PAUSE_102" && "$PAUSE_102" -gt 0 ]]; echo $?)" "7: agents[102].pause_seconds > 0" "$PAUSE_102"
