#!/usr/bin/env bash
# Innova PBX — M2b (1-yarim) proof skripti (replica/m2b-contract.md §6):
#   1. Foydalanuvchilar (admin -> admin2/operator102, CRUD, 409lar, parol oqimi) —
#      `scripts/lib/m2b_users_scenario.sh` (§3, 1-qism).
#   2. Operator portali DND/forward (`PATCH /me/extension`, admin bilan BIR XIL
#      tekshiruv funksiyasi) + ruxsatlar (403) — `scripts/lib/m2b_portal_scenario.sh` (§4).
#   3. Navbat Q: 101 statik, 102 dinamik (kirmagan). Kiruvchi -> faqat 101 jiringlaydi.
#      102 `*45` -> login (GET /live logged_in=true, keyingi qo'ng'iroq 102ga ham boradi).
#      102 `*46` -> pauza (jiringlamaydi). `POST /me/queues/{id}/unpause` (operator102 o'zi
#      nomidan, §4) -> yana jiringlaydi (<= 3s); operator102 yo'q bo'lsa (SKIP holati)
#      TENG KUCHGA EGA admin endpoint (§1) zaxira sifatida ishlatiladi.
#   4. 101 DND -> navbatdan qo'ng'iroq olmaydi (102 jiringlaydi).
#   5. Faol qo'ng'iroq paytida `GET /live`: calls'da state=up (101), queues[].waiting=1 (105).
#   6. Admin (ext 103 — `PATCH /users/{admin_id}` orqali biriktirilgan, §3) `POST /live/spy
#      listen` -> 103 jiringlaydi, javob beradi -> Asterisk'da ChanSpy kanali; audit `live.spy`.
#   7. `GET /reports/*` — boshqa agent (`scripts/lib/m2b_reports_scenario.sh`, bo'lsa ishlaydi).
#      MANDATE: §5 MENIKI EMAS.
#   8. Faolsizlantirilgan foydalanuvchi kira olmaydi va refresh token bekor bo'ladi —
#      `scripts/lib/m2b_users_scenario.sh` (§3, 2-qism — 1-band BILAN BIR XIL fayl,
#      ikkinchi marta `source` qilinadi, fayl o'zi ichida 1/8 qismlarini ajratadi).
#
# Foydalanish:
#   scripts/m2b-proof.sh            # joriy `innova-m0` stackka qarshi (M2b qoldiqlari bo'lsa — exit 2)
#   scripts/m2b-proof.sh --fresh    # avval `docker compose down -v` + qayta build + up -d
#
# MUHIM: faqat `innova-m0` compose loyihasiga tegadi; o'z konteynerlarini (m2b-proof-*) oxirida o'chiradi.
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

declare -A IP=([101]="172.28.0.180" [102]="172.28.0.181" [103]="172.28.0.182" [caller]="172.28.0.183")

# shellcheck source=lib/m2a_common.sh
# M2a'dan QAYTA ISHLATILADI (dryer) — bu yerdagi login/api/jget/sql/ast/wait_until/
# bridged kabi yordamchilar M2a'ga XOS EMAS, umumiy proof-infratuzilma; alohida
# `m2b_common.sh` yozish = shu funksiyalarning ikkinchi nusxasi bo'lardi.
source "$LIB_DIR/m2a_common.sh"

ADMIN_PASSWORD="${PROOF_ADMIN_PASSWORD:-$(grep -E '^PROOF_ADMIN_PASSWORD=' "$DEPLOY_DIR/.env" | cut -d= -f2-)}"
[[ -n "$ADMIN_PASSWORD" ]] || { echo "PROOF_ADMIN_PASSWORD deploy/.env da yo'q"; exit 2; }

CONTAINERS=(m2b-proof-101 m2b-proof-102 m2b-proof-103 m2b-proof-caller)
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

LEFTOVER=$(jget "$(jbody "$(api GET "/extensions?q=M2b")")" total 2>/dev/null)
if [[ -n "$LEFTOVER" && "$LEFTOVER" != "0" ]]; then
  echo "Stekda oldingi M2b isbot qoldiqlari bor ($LEFTOVER ext) — 'scripts/m2b-proof.sh --fresh' bilan ishga tushiring."
  exit 2
fi

# ---------------------------------------------------------------- resurslar
echo "=== resurslar ==="
declare -A EXT_ID SECRET
for n in 101 102 103 104 105; do
  j=$(jbody "$(api POST /extensions "{\"number\":\"$n\",\"name\":\"M2b$n\"}")")
  EXT_ID[$n]=$(jget "$j" item id); SECRET[$n]=$(jget "$j" sip password)
done
check "$( [[ -n "${EXT_ID[101]}" && -n "${EXT_ID[102]}" && -n "${EXT_ID[103]}" && -n "${EXT_ID[104]}" && -n "${EXT_ID[105]}" ]]; echo $?)" \
  "POST /extensions -> 101..105" "${EXT_ID[*]}"

HANGUP_TARGET=$(python3 -c "
import json,sys
d=json.load(sys.stdin)
items=[i for i in d['items'] if i['kind']=='hangup']
print(items[0]['id'] if items else '')
" <<<"$(curl -s "$API_BASE/targets?kind=hangup" "${AUTH[@]}")")
[[ -n "$HANGUP_TARGET" ]] && pass "hangup tizim manzili topildi" || fail "hangup tizim manzili topilmadi"

QJ=$(api POST /queues "{\"name\":\"M2bQueue\",\"number\":\"600\",\"strategy\":\"ringall\",\"agent_ring_seconds\":8,\"retry_seconds\":1,\"max_wait_seconds\":30,\"members\":[{\"extension_id\":\"${EXT_ID[101]}\",\"dynamic\":false},{\"extension_id\":\"${EXT_ID[102]}\",\"dynamic\":true}],\"timeout_target_id\":\"$HANGUP_TARGET\"}")
QUEUE_ID=$(jget "$(jbody "$QJ")" item id)
check "$( [[ "$(jcode "$QJ")" == "201" && -n "$QUEUE_ID" ]]; echo $?)" \
  "POST /queues -> M2bQueue (600): 101 statik + 102 dinamik (kirmagan)" "$QJ"

echo "=== admin ext biriktirish ==="
# Users API (§3) endi bor — admin foydalanuvchiga ichki raqam `PATCH /users/{id}`
# orqali biriktiriladi (ssenariy 6 `users.extension_id` talabi uchun; avval
# to'g'ridan-to'g'ri SQL ishlatilardi, endi kontrakt yo'li bilan).
ADMIN_ID=$(jget "$(jbody "$(api GET /auth/me)")" id)
ADMIN_STAMP=$(python3 -c "
import json,sys
d=json.load(sys.stdin)
print(next(u['updated_at'] for u in d['items'] if u['username']=='admin'))" <<<"$(jbody "$(api GET /users)")")
ADMIN_EXT_J=$(api PATCH "/users/$ADMIN_ID" "{\"extension_id\":\"${EXT_ID[103]}\",\"updated_at\":\"$ADMIN_STAMP\"}")
check "$( [[ "$(jcode "$ADMIN_EXT_J")" == "200" && "$(jget "$(jbody "$ADMIN_EXT_J")" item extension number)" == "103" ]]; echo $?)" \
  "admin.extension_id = 103 (PATCH /users/{admin})" "$ADMIN_EXT_J"

echo "=== telefonlar ==="
for c in 101 102 103 caller; do
  docker run -d --name "m2b-proof-$c" --network "$NET" --ip "${IP[$c]}" "$PY_IMAGE" sleep infinity >/dev/null
  for f in outbound_invite.py vm_caller.py m2a_phone.py; do docker cp "$SIPP_DIR/$f" "m2b-proof-$c:/tmp/$f"; done
done
for n in 101 102 103; do
  docker exec -d "m2b-proof-$n" sh -c "cd /tmp && python3 m2a_phone.py serve $n '${SECRET[$n]}' 5070 12000 /tmp/mode 520 > /tmp/phone.log 2>&1"
done
registered() { for n in 101 102 103; do docker exec "m2b-proof-$n" grep -q 'REGISTER_RESULT: OK' /tmp/phone.log 2>/dev/null || return 1; done; }
wait_until 15 registered && pass "101, 102, 103 REGISTER -> 200 OK" || fail "REGISTER -> $(docker exec m2b-proof-101 cat /tmp/phone.log)"

# TOPILGAN XATO (isbot yordamchisi, mahsulot EMAS): REGISTER 200 qaytargandan
# SO'NG HAM PJSIP kontakt bir necha soniya "NonQual" holatida qoladi
# (`pjsip.conf`: `max_initial_qualify_time = 5` — birinchi OPTIONS qualify
# TASODIFIY 0-5s ichida taqsimlanadi, storm oldini olish uchun); shu oraliqda
# `Queue()` ringall qilsa ushbu a'zoni JIRINGLATMAYDI (o'lchandi: real vaqtda
# ~4.7s gacha "NonQual", "Avail" ~5.3sda) — 101ning BIRINCHI isbot chaqiruvi
# aynan shu poyga tufayli FAIL berardi. Tuzatish: "Avail" holatini kutish.
qualified() { for n in 101 102 103; do ast "pjsip show contacts" | grep "$n/" | grep -q "Avail " || return 1; done; }
wait_until 10 qualified && pass "101, 102, 103 PJSIP qualify -> Avail" || fail "qualify -> $(ast 'pjsip show contacts')"

mode() { docker exec "m2b-proof-$1" sh -c "echo '$2' > /tmp/mode"; }
plog() { docker exec "m2b-proof-$1" cat /tmp/phone.log 2>/dev/null; }
invites() { plog "$1" | grep -c '^INVITE '; }
count_of() { plog "$1" | grep -c "^$2"; }
CALL_N=0
place_call() { # container ext secret dialed talk_s -> $OUT (sinxron, feature-kod chaqiruvlari uchun)
  CALL_N=$((CALL_N + 1))
  OUT=$(docker exec "m2b-proof-$1" sh -c "cd /tmp && python3 m2a_phone.py call '$2' '$3' $((6070 + CALL_N)) $((14000 + CALL_N * 2)) '$4' $5" 2>&1)
}
place_call_bg() { # nom container ext secret dialed talk_s -> /tmp/<nom>.log (fon, navbatga kiruvchi chaqiruvlar)
  CALL_N=$((CALL_N + 1))
  docker exec -d "m2b-proof-$2" sh -c "cd /tmp && python3 m2a_phone.py call '$3' '$4' $((6070 + CALL_N)) $((14000 + CALL_N * 2)) '$5' $6 > /tmp/$1.log 2>&1"
}
call_log() { docker exec "m2b-proof-$1" cat "/tmp/$2.log" 2>/dev/null; }
call_done() { call_log "$1" "$2" | grep -Eq 'BYE_SENT|REMOTE_BYE|INVITE_FINAL: SIP/2.0 [3-6]'; }
final_of() { sed -n 's/^INVITE_FINAL: SIP\/2.0 \([0-9]*\).*/\1/p' <<<"$1"; }
chanspy_active() { ast "core show channels concise" | grep -qi "ChanSpy"; }

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
member_action() { # raqam action json_tana -> $ACT_OUT
  ACT_OUT=$(api POST "/queues/$QUEUE_ID/members/${EXT_ID[$1]}/$2" "$3")
}
fetch_live() { LIVE=$(jbody "$(api GET /live)"); }
live_agent_field() { # raqam field -> qiymat (fetch_live keyin, $LIVE ichidan)
  python3 -c "
import json,sys
d=json.load(sys.stdin)
for q in d['queues']:
    for a in q['agents']:
        if a['extension']==sys.argv[1]:
            v=a.get(sys.argv[2])
            print('' if v is None else v)
            sys.exit()
" "$1" "$2" <<<"$LIVE"
}

# ---------------------------------------------------------------- 1
echo "--- 1. foydalanuvchilar ---"
if [[ -f "$LIB_DIR/m2b_users_scenario.sh" ]]; then
  # shellcheck source=/dev/null
  source "$LIB_DIR/m2b_users_scenario.sh"
else
  echo "SKIP: 1 — scripts/lib/m2b_users_scenario.sh topilmadi"
fi

# ---------------------------------------------------------------- 2
echo "--- 2. operator portali: DND ---"
if [[ -f "$LIB_DIR/m2b_portal_scenario.sh" ]]; then
  # shellcheck source=/dev/null
  source "$LIB_DIR/m2b_portal_scenario.sh"
else
  echo "SKIP: 2 — scripts/lib/m2b_portal_scenario.sh topilmadi"
fi

# ---------------------------------------------------------------- 3
echo "--- 3. navbat: dinamik login/pauza ---"
mode 101 answer; mode 102 answer
B101=$(invites 101); B102=$(invites 102)
place_call_bg q3a caller 104 "${SECRET[104]}" 600 4
wait_until 8 sh -c "[ \$(docker exec m2b-proof-101 grep -c '^INVITE ' /tmp/phone.log) -gt $B101 ]"
check "$( [[ "$(invites 101)" -gt "$B101" && "$(invites 102)" == "$B102" ]]; echo $?)" \
  "3: kiruvchi (104->600) -> faqat 101 jiringladi (102 kirmagan, YO'Q)" "101=$(invites 101) 102=$(invites 102)"
wait_until 10 call_done caller q3a

place_call 102 102 "${SECRET[102]}" '*45' 5
check "$( [[ "$(final_of "$OUT")" == "200" ]]; echo $?)" "3: 102 *45 -> login OK" "$OUT"
fetch_live
check "$( [[ "$(live_agent_field 102 logged_in)" == "True" ]]; echo $?)" "3: GET /live -> 102 logged_in=true" "$LIVE"

B101=$(invites 101); B102=$(invites 102)
place_call_bg q3b caller 104 "${SECRET[104]}" 600 4
wait_until 8 sh -c "[ \$(docker exec m2b-proof-102 grep -c '^INVITE ' /tmp/phone.log) -gt $B102 ]"
check "$( [[ "$(invites 101)" -gt "$B101" && "$(invites 102)" -gt "$B102" ]]; echo $?)" \
  "3: login'dan keyin 101 VA 102 ikkisi ham jiringladi" "101=$(invites 101) 102=$(invites 102)"
wait_until 10 call_done caller q3b

place_call 102 102 "${SECRET[102]}" '*46' 5
check "$( [[ "$(final_of "$OUT")" == "200" ]]; echo $?)" "3: 102 *46 -> pauza yoqildi" "$OUT"
fetch_live
check "$( [[ "$(live_agent_field 102 paused)" == "True" ]]; echo $?)" "3: GET /live -> 102 paused=true" "$LIVE"

B101=$(invites 101); B102=$(invites 102)
place_call_bg q3c caller 104 "${SECRET[104]}" 600 4
wait_until 8 sh -c "[ \$(docker exec m2b-proof-101 grep -c '^INVITE ' /tmp/phone.log) -gt $B101 ]"
check "$( [[ "$(invites 101)" -gt "$B101" && "$(invites 102)" == "$B102" ]]; echo $?)" \
  "3: pauzadan keyin faqat 101 jiringladi (102 pauzada)" "101=$(invites 101) 102=$(invites 102)"
wait_until 10 call_done caller q3c

# Kontrakt matni `/me/queues/{id}/unpause` deydi (§4) — endi Users/portal API bor,
# shu sabab operator102 O'ZI nomidan (1-ssenariyda yaratilgan/eksport qilingan
# $OPERATOR102_LOGIN) chaqiradi. Agar 1-ssenariy fayli yo'q bo'lsa (SKIP holati) —
# TENG KUCHGA EGA admin endpoint (§1) zaxira sifatida ishlatiladi.
if [[ -n "${OPERATOR102_LOGIN:-}" ]]; then
  OP102_TOKEN=$(login_as "$OPERATOR102_LOGIN" "$OPERATOR102_PASSWORD")
  ACT_OUT=$(api_as "$OP102_TOKEN" POST "/me/queues/$QUEUE_ID/unpause" '{}')
  check "$( [[ "$(jcode "$ACT_OUT")" == "200" ]]; echo $?)" \
    "3: POST /me/queues/{id}/unpause (operator102 o'zi, §4) -> 200" "$ACT_OUT"
else
  member_action 102 unpause '{}'
  check "$( [[ "$(jcode "$ACT_OUT")" == "200" ]]; echo $?)" \
    "3: POST /queues/{id}/members/102/unpause (zaxira: admin, operator102 yo'q) -> 200" "$ACT_OUT"
fi
B101=$(invites 101); B102=$(invites 102)
place_call_bg q3d caller 104 "${SECRET[104]}" 600 4
wait_until 8 sh -c "[ \$(docker exec m2b-proof-102 grep -c '^INVITE ' /tmp/phone.log) -gt $B102 ]"
check "$( [[ "$(invites 102)" -gt "$B102" ]]; echo $?)" "3: unpause'dan keyin (<= 3 s) 102 yana jiringladi" "102=$(invites 102)"
wait_until 10 call_done caller q3d

# ---------------------------------------------------------------- 4
echo "--- 4. navbat DND ---"
ext_patch 101 '"dnd":true'
check "$( [[ "$(jcode "$PATCH_OUT")" == "200" ]]; echo $?)" "4: PATCH 101 dnd=true" "$PATCH_OUT"
B101=$(invites 101); B102=$(invites 102)
place_call_bg q4 caller 104 "${SECRET[104]}" 600 4
wait_until 8 sh -c "[ \$(docker exec m2b-proof-102 grep -c '^INVITE ' /tmp/phone.log) -gt $B102 ]"
check "$( [[ "$(invites 101)" == "$B101" && "$(invites 102)" -gt "$B102" ]]; echo $?)" \
  "4: 101 DND -> navbatdan qo'ng'iroq OLMADI (102 jiringladi)" "101=$(invites 101) 102=$(invites 102)"
wait_until 10 call_done caller q4
ext_patch 101 '"dnd":false'

# ---------------------------------------------------------------- 5
echo "--- 5. GET /live: faol qo'ng'iroq + kutish ---"
member_action 102 pause '{}'
check "$( [[ "$(jcode "$ACT_OUT")" == "200" ]]; echo $?)" "5: 102 pauza (faqat 101 band bo'lsin)" "$ACT_OUT"
place_call_bg q5a caller 104 "${SECRET[104]}" 600 14
wait_until 10 bridged 104 101 && pass "5: 104 -> 600 -> 101 bilan ulandi (bridge)" \
  || fail "5: bridge 104/101 yo'q ($(ast 'core show channels concise'))"
place_call_bg q5b caller 105 "${SECRET[105]}" 600 6
waiting_now() {
  fetch_live
  [[ "$(python3 -c "
import json,sys
d=json.load(sys.stdin)
for q in d['queues']:
    if q['id']=='$QUEUE_ID':
        print(len(q['waiting']))
        sys.exit()
print(-1)
" <<<"$LIVE")" == "1" ]]
}
wait_until 10 waiting_now && pass "5: 105 navbatda kutayotgan (waiting=1)" || fail "5: waiting=1 bo'lmadi ($LIVE)"
check "$(python3 -c "
import json,sys
d=json.load(sys.stdin)
c = next((x for x in d['calls'] if x.get('extension')=='101'), None)
ok = c is not None and c['state']=='up' and c.get('from') and c.get('to')
sys.exit(0 if ok else 1)" <<<"$LIVE"; echo $?)" "5: GET /live calls -> 101 state=up (from/to bor)" "$LIVE"
check "$(python3 -c "
import json,sys
d=json.load(sys.stdin)
q = next((x for x in d['queues'] if x['id']=='$QUEUE_ID'), None)
w = q['waiting'] if q else []
ok = len(w)==1 and w[0].get('position')==1 and w[0].get('from') and w[0].get('since')
sys.exit(0 if ok else 1)" <<<"$LIVE"; echo $?)" "5: GET /live queues[].waiting -> 1 ta (105, position=1)" "$LIVE"

# ---------------------------------------------------------------- 6
echo "--- 6. spy ---"
mode 103 answer
B103=$(invites 103)
fetch_live
CALL_ID=$(python3 -c "
import json,sys
d=json.load(sys.stdin)
c = next((x for x in d['calls'] if x.get('extension')=='101' and x.get('state')=='up'), None)
print(c['id'] if c else '')
" <<<"$LIVE")
check "$( [[ -n "$CALL_ID" ]]; echo $?)" "6: GET /live dan faol qo'ng'iroq (101) linkedid topildi"
SPY=$(api POST /live/spy "{\"call_id\":\"$CALL_ID\",\"mode\":\"listen\"}")
check "$( [[ "$(jcode "$SPY")" == "200" && "$(jget "$(jbody "$SPY")" status)" == "calling" ]]; echo $?)" \
  "6: POST /live/spy listen (103 biriktirilgan admin) -> 200 calling" "$SPY"
wait_until 10 sh -c "[ \$(docker exec m2b-proof-103 grep -c '^INVITE ' /tmp/phone.log) -gt $B103 ]" \
  && pass "6: 103 jiringladi (Originate)" || fail "6: 103ga INVITE kelmadi ($(plog 103))"
wait_until 10 sh -c "docker exec m2b-proof-103 grep -q ANSWERED /tmp/phone.log" \
  && pass "6: 103 javob berdi" || fail "6: 103 ANSWERED emas ($(plog 103))"
check "$(wait_until 5 chanspy_active; echo $?)" "6: Asterisk'da ChanSpy kanali bor" "$(ast 'core show channels concise')"
# ESLATMA: `audit_log.action` qattiq 8-fe'llik enum'ga normalizatsiya qilinadi
# (m1b-contract.md bo'lim 6, `normalize_action()`) — "live.spy" -> "spy" bu
# ro'yxatda yo'q, shu sabab umumiy "update"ga tushadi (ANIQ fe'l `diff`da
# saqlanadi: `{"mode":"listen",...}`); shu sabab `action=update` + `q=listen`
# substring qidiruvi orqali TASDIQLANADI (`action=live.spy` HECH QACHON
# topilmaydi — bu kutilgan, mahsulot talabi, isbot xatosi EMAS).
AUDIT_SPY=$(curl -s "$API_BASE/audit?entity=call&action=update&q=listen" "${AUTH[@]}")
check "$( [[ "$(jget "$AUDIT_SPY" total)" -ge 1 ]]; echo $?)" "6: audit live.spy (entity=call, action=update, diff.mode=listen) yozildi" "$AUDIT_SPY"

# ---------------------------------------------------------------- 7
echo "--- 7. analitika ---"
if [[ -f "$LIB_DIR/m2b_reports_scenario.sh" ]]; then
  # shellcheck source=/dev/null
  source "$LIB_DIR/m2b_reports_scenario.sh"
else
  echo "SKIP: 7 — keyingi agent (scripts/lib/m2b_reports_scenario.sh, §5 MENIKI EMAS)"
fi

# ---------------------------------------------------------------- 8
echo "--- 8. faolsizlantirilgan foydalanuvchi ---"
if [[ -f "$LIB_DIR/m2b_users_scenario.sh" ]]; then
  # shellcheck source=/dev/null
  # 1-band BILAN BIR XIL fayl (§3 MENIKI EMAS mandate'ning davomi) — ikkinchi
  # marta `source` qilinadi, fayl o'zi ichida 1/8 qismlarini ajratishi kutiladi.
  source "$LIB_DIR/m2b_users_scenario.sh"
else
  echo "SKIP: 8 — scripts/lib/m2b_users_scenario.sh topilmadi"
fi

echo "=== NATIJA: PASS=$PASS FAIL=$FAIL ==="
[[ "$FAIL" -eq 0 ]]
