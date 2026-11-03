#!/usr/bin/env bash
# Innova PBX — M10 Bo'lak B isboti (replica/m10-onlinepbx-contract.md Bo'lak B):
#   B1. Sifat baholash (QA): /qa/checklists + /qa/evaluations CRUD, ball hisobi
#       (og'irlik + critical-fail=0%, Decimal ROUND_HALF_UP), `/calls` `qa`
#       belgisi, `/calls/{linkedid}/evaluations`, `/me/evaluations` (operator,
#       `evaluator_name` HAR DOIM `None`), `/qa/summary`, checklist 409 `in_use`.
#   B2. 2FA (TOTP, RFC 6238): `/me/2fa/setup|enable|disable|recovery-codes`,
#       login 2 bosqich (`/auth/login` -> `totp_required` -> `/auth/login/totp`),
#       takror himoyasi (`totp_last_step`), tiklash kodi bir martalik ishlatilishi,
#       `require_2fa` siyosati ("admins") -> 403 `2fa_enrollment_required` ->
#       `/me/2fa/setup` orqali ro'yxatdan o'tish -> ruxsat qaytadi, admin
#       `/users/{id}/2fa/reset`.
#   B3. Tashqi WS hodisalar: `WS /api/public/v1/events/ws` — sarlavha YOKI
#       birinchi xabar autentifikatsiyasi, `events:read` skopi yo'q -> 4403,
#       avtorizatsiya yo'q -> 4401, `since_seq` replay (`include_internal`
#       bilan/bilmasdan), jonli tarqatish (`integration_events` so'rovchi fon
#       vazifa), ulanish chegarasi (5/kalit) -> 4429, nginx `wss://` yo'li.
#
# CHEKLOV: B1/B3 faqat HTTP/WS API darajasida isbotlanadi (SIPp YO'Q — QA
# baholash uchun kerakli CDR qatori `cdr` jadvaliga TO'G'RIDAN-TO'G'RI SQL
# bilan sintetik kiritiladi, chunki `qa_evaluations.call_id`da haqiqiy FK yo'q
# va bu yerda maqsad — QA/2FA/WS mantiqini isbotlash, SIP signalizatsiyasini
# emas, m9b-proof.sh'dagi B1-B2 qolipiga o'xshash).
#
# Foydalanish:
#   scripts/m10b-proof.sh            # joriy `innova-m0` stackka qarshi
#   scripts/m10b-proof.sh --fresh    # avval build + up -d (migratsiya 0034_m10b shu bilan qo'llanadi)
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"
LIB_DIR="$ROOT_DIR/scripts/lib"
API_BASE="${API_BASE:-http://127.0.0.1:8710/api/v1}"
API_ROOT="${API_BASE%/api/v1}"
PROJECT="innova-m0"
PG="innova-m0-postgres-1"    # m2a_common.sh sql()/wait_for_sql() shu konteynerga tegadi
AST="innova-m0-asterisk-1"   # m2a_common.sh ast() shu konteynerga tegadi
APICONT="innova-m0-api-1"    # TOTP kod hisoblash shu konteyner ichida (m3b_common.sh signed_link() bilan BIR XIL qolip)
WS_DIRECT_BASE="${WS_DIRECT_BASE:-ws://127.0.0.1:8710}"
WS_WSS_BASE="${WS_WSS_BASE:-wss://127.0.0.1:8712}"

source "$LIB_DIR/m2a_common.sh"  # pass/fail/check, sql(), wait_for_sql(), login(), api(), login_as(), api_as(), jbody/jcode/jget
source "$LIB_DIR/m3b_common.sh"  # err_is()

ADMIN_PASSWORD="${PROOF_ADMIN_PASSWORD:-$(grep -E '^PROOF_ADMIN_PASSWORD=' "$DEPLOY_DIR/.env" 2>/dev/null | cut -d= -f2-)}"
[[ -n "$ADMIN_PASSWORD" ]] || { echo "PROOF_ADMIN_PASSWORD deploy/.env da yo'q"; exit 2; }

# `websockets` kutubxonasi FAQAT `api/.venv`da bor (M10 B3 isboti shu yerda yoziladi).
PYBIN="$ROOT_DIR/api/.venv/bin/python3"
[[ -x "$PYBIN" ]] || PYBIN="python3"
WS_PROBE="$LIB_DIR/ws_events_probe.py"

if [[ "${1:-}" == "--fresh" ]]; then
  echo "--- --fresh: stack qayta quriladi (migratsiya 0034_m10b shu bilan qo'llanadi) ---"
  flock /tmp/innova-stack.lock -c "cd '$DEPLOY_DIR' && docker compose -p '$PROJECT' build" || { fail "docker compose build"; exit 1; }
  flock /tmp/innova-stack.lock -c "cd '$DEPLOY_DIR' && docker compose -p '$PROJECT' up -d" || { fail "docker compose up"; exit 1; }
  wait_api
fi

echo "=== setup/login (admin) ==="
login "$ADMIN_PASSWORD" || { fail "login"; exit 1; }

# ---------------------------------------------------------------- yordamchilar
totp_code() { # secret ofset_soniya -> 6 xonali kod (API konteyner soati, +ofset)
  docker exec "$APICONT" python -c "
import sys, time
from app.services.totp import totp_at
print(totp_at(sys.argv[1], int(time.time()) + int(sys.argv[2])))
" "$1" "$2"
}

# Skript idempotent bo'lishi SHART (stack umumiy, `--fresh` ISHLATILMAYDI) —
# oldingi yurgizishdan qolgan M10b* resurslarni, FK bog'liqligini hisobga olib
# (baholash -> varaqa, foydalanuvchi -> ichki raqam), TARTIB BILAN tozalaymiz
# (m9a/m9b-proof.sh `del_by`/`del_ids` bilan BIR XIL qolip).
del_by() { # path field prefix [list_query]
  local path="$1" field="$2" prefix="$3" query="${4:-}" id
  for id in $(jbody "$(api GET "$path$query")" | python3 -c "
import json,sys
d=json.load(sys.stdin)
items = d.get('items', d) if isinstance(d, dict) else d
for i in items:
    if str(i.get('$field', '')).startswith('$prefix'):
        print(i['id'])
" 2>/dev/null); do
    api DELETE "$path/$id" >/dev/null 2>&1 || true
  done
}
echo "=== tozalash (oldingi yurgizishdan qolganlar) ==="
del_by /qa/evaluations call_id "m10b-"
del_by /qa/checklists name "M10b"
del_by /users username "m10b"
del_by /extensions number 9310 "?q=9310"
for id in $(jbody "$(api GET /integrations/api-keys)" | python3 -c "
import json,sys
for i in json.load(sys.stdin).get('items', []):
    if str(i.get('name','')).startswith('M10b'):
        print(i['id'])
" 2>/dev/null); do
  api DELETE "/integrations/api-keys/$id" >/dev/null 2>&1 || true
done

echo "=== B1: Sifat baholash (QA) ==="
CHECKLIST_JSON=$(api POST /qa/checklists '{"name":"M10bChecklist","criteria":[
  {"label":"Salomlashish","kind":"yesno","weight":1,"critical":false},
  {"label":"Muammoni hal qildi","kind":"scale5","weight":2,"critical":true}
]}')
check "$( [[ "$(jcode "$CHECKLIST_JSON")" == "201" ]]; echo $?)" "POST /qa/checklists -> 201" "$CHECKLIST_JSON"
CHECKLIST_BODY=$(jbody "$CHECKLIST_JSON")
CHECKLIST_ID=$(jget "$CHECKLIST_BODY" id)
C1_ID=$(jget "$CHECKLIST_BODY" criteria 0 id)
C2_ID=$(jget "$CHECKLIST_BODY" criteria 1 id)
[[ -n "$CHECKLIST_ID" && -n "$C1_ID" && -n "$C2_ID" ]] && pass "checklist/mezon id'lari olindi" \
  || fail "checklist/mezon id'lari olinmadi -> $CHECKLIST_BODY"

# Ichki raqam (operator'ning o'zi — keyinroq /me/evaluations uchun ham kerak).
OPEXT_JSON=$(api POST /extensions '{"number":"9310","name":"M10b Operator Ext"}')
check "$( [[ "$(jcode "$OPEXT_JSON")" == "201" ]]; echo $?)" "POST /extensions -> 9310 (operator) yaratildi" "$OPEXT_JSON"
OPEXT_ID=$(jget "$(jbody "$OPEXT_JSON")" item id)

# Haqiqiy qo'ng'iroqqa bog'lab tekshirish uchun `cdr` qatoriga TO'G'RIDAN-TO'G'RI
# sintetik kiritish (SIPp shart emas — B1 maqsadi QA mantiqi, SIP emas).
TENANT_CODE=$(sql "select code from tenants limit 1")
CALL_LINKEDID="m10b-$(sql "select gen_random_uuid()")"
sql "insert into cdr (calldate, clid, src, dst, dcontext, channel, dstchannel, duration, billsec, disposition, accountcode, uniqueid, linkedid)
     values (now(), '\"M10b Caller\" <9999>', '9999', '9310', 'from-internal', 'PJSIP/9999-m10b', 'PJSIP/9310-m10b',
             60, 55, 'ANSWERED', '$TENANT_CODE', '$CALL_LINKEDID', '$CALL_LINKEDID')" >/dev/null

EVAL_JSON=$(api POST /qa/evaluations "{\"checklist_id\":\"$CHECKLIST_ID\",\"call_id\":\"$CALL_LINKEDID\",\"extension_id\":\"$OPEXT_ID\",\"answers\":{\"$C1_ID\":true,\"$C2_ID\":5},\"comment\":\"yaxshi\"}")
check "$( [[ "$(jcode "$EVAL_JSON")" == "201" ]]; echo $?)" "POST /qa/evaluations -> 201" "$EVAL_JSON"
EVAL_BODY=$(jbody "$EVAL_JSON")
EVAL_ID=$(jget "$EVAL_BODY" id)
check "$( [[ "$(jget "$EVAL_BODY" score_pct)" == "100.0" ]]; echo $?)" \
  "score_pct=100.0 (c1 yesno=true + c2 scale5=5, critical mos keldi)" "$EVAL_BODY"

# `q` faqat src/dst/userfield'ni qidiradi (linkedid'ni EMAS) — shu sabab
# ichki raqam (9310) bo'yicha topamiz va ro'yxatdan AYNAN shu linkedid'ni olamiz.
CALLS_LIST=$(api GET "/calls?ext=9310")
CALLS_BODY=$(jbody "$CALLS_LIST")
CALL_IDX=$(python3 -c "
import json,sys
items = json.loads(sys.argv[1]).get('items', [])
for i, c in enumerate(items):
    if c.get('linkedid') == sys.argv[2]:
        print(i); break
" "$CALLS_BODY" "$CALL_LINKEDID")
check "$( [[ -n "$CALL_IDX" ]]; echo $?)" "GET /calls?ext=9310 -> sintetik qo'ng'iroq topildi" "$CALLS_BODY"
check "$( [[ "$(jget "$CALLS_BODY" items "$CALL_IDX" qa evaluation_id)" == "$EVAL_ID" ]]; echo $?)" \
  "GET /calls -> qa belgisi (evaluation_id) to'g'ri" "$CALLS_BODY"
check "$( [[ "$(jget "$CALLS_BODY" items "$CALL_IDX" qa checklist_name)" == "M10bChecklist" ]]; echo $?)" \
  "GET /calls -> qa.checklist_name to'g'ri" "$CALLS_BODY"

CALL_EVALS=$(api GET "/calls/$CALL_LINKEDID/evaluations")
check "$( [[ "$(jget "$(jbody "$CALL_EVALS")" items 0 id)" == "$EVAL_ID" ]]; echo $?)" \
  "GET /calls/{linkedid}/evaluations -> baholash ko'rinadi" "$CALL_EVALS"
check "$( [[ "$(jget "$(jbody "$CALL_EVALS")" items 0 evaluator_name)" == "" ]]; echo $?)" \
  "GET /calls/{linkedid}/evaluations -> evaluator_name ko'rsatilmaydi" "$CALL_EVALS"

UPDATED_AT=$(jget "$EVAL_BODY" updated_at)
UPDATE_JSON=$(api PATCH "/qa/evaluations/$EVAL_ID" "{\"answers\":{\"$C1_ID\":true,\"$C2_ID\":3},\"updated_at\":\"$UPDATED_AT\"}")
check "$( [[ "$(jcode "$UPDATE_JSON")" == "200" ]]; echo $?)" "PATCH /qa/evaluations/{id} -> 200" "$UPDATE_JSON"
check "$( [[ "$(jget "$(jbody "$UPDATE_JSON")" score_pct)" == "0.0" ]]; echo $?)" \
  "score_pct=0.0 (c2 scale5=3<5 critical muvaffaqiyatsiz -> ball 0%)" "$UPDATE_JSON"

SUMMARY_JSON=$(api GET /qa/summary)
SUMMARY_BODY=$(jbody "$SUMMARY_JSON")
check "$( [[ "$(jcode "$SUMMARY_JSON")" == "200" && "$(jget "$SUMMARY_BODY" count)" -ge "1" ]]; echo $?)" \
  "GET /qa/summary -> count>=1" "$SUMMARY_BODY"

# Operator sifatida /me/evaluations — o'zining baholashini ko'radi, baholovchi ismi YO'Q.
OP_PASSWORD="M10bPass123"
OPUSER_JSON=$(api POST /users "{\"username\":\"m10bop1\",\"full_name\":\"M10b Operator\",\"role\":\"operator\",\"extension_id\":\"$OPEXT_ID\",\"password\":\"$OP_PASSWORD\",\"language\":\"uz\"}")
check "$( [[ "$(jcode "$OPUSER_JSON")" == "201" ]]; echo $?)" "POST /users -> m10bop1 (operator) yaratildi" "$OPUSER_JSON"
OP_TOKEN=$(login_as m10bop1 "$OP_PASSWORD")
[[ -n "$OP_TOKEN" ]] && pass "operator login -> token olindi" || fail "operator login -> token yo'q"
MY_EVALS=$(api_as "$OP_TOKEN" GET "/me/evaluations")
MY_EVALS_BODY=$(jbody "$MY_EVALS")
check "$( [[ "$(jget "$MY_EVALS_BODY" items 0 id)" == "$EVAL_ID" ]]; echo $?)" \
  "GET /me/evaluations (operator) -> o'z baholashi ko'rinadi" "$MY_EVALS_BODY"
check "$( [[ "$(jget "$MY_EVALS_BODY" items 0 evaluator_name)" == "" ]]; echo $?)" \
  "GET /me/evaluations -> evaluator_name HAR DOIM None" "$MY_EVALS_BODY"

# Checklist ishlatilayotganda o'chirish -> 409 in_use.
DEL_IN_USE=$(api DELETE "/qa/checklists/$CHECKLIST_ID")
check "$(err_is "$DEL_IN_USE" 409 in_use; echo $?)" "DELETE /qa/checklists/{id} (ishlatilgan) -> 409 in_use" "$DEL_IN_USE"

DEL_EVAL=$(api DELETE "/qa/evaluations/$EVAL_ID")
check "$( [[ "$(jcode "$DEL_EVAL")" == "204" ]]; echo $?)" "DELETE /qa/evaluations/{id} -> 204" "$DEL_EVAL"
DEL_CHECKLIST=$(api DELETE "/qa/checklists/$CHECKLIST_ID")
check "$( [[ "$(jcode "$DEL_CHECKLIST")" == "204" ]]; echo $?)" "DELETE /qa/checklists/{id} (bo'shagandan keyin) -> 204" "$DEL_CHECKLIST"

echo "=== B3: Tashqi WS hodisalar ==="
KEY_EVENTS_JSON=$(api POST /integrations/api-keys '{"name":"M10bWsKey","scopes":["events:read"]}')
check "$( [[ "$(jcode "$KEY_EVENTS_JSON")" == "201" ]]; echo $?)" "POST /integrations/api-keys (events:read) -> 201" "$KEY_EVENTS_JSON"
KEY_EVENTS_BODY=$(jbody "$KEY_EVENTS_JSON")
KEY_EVENTS_ID=$(jget "$KEY_EVENTS_BODY" item id)
KEY_EVENTS_TOKEN=$(jget "$KEY_EVENTS_BODY" key)

KEY_NOSCOPE_JSON=$(api POST /integrations/api-keys '{"name":"M10bNoScopeKey","scopes":["calls:read"]}')
KEY_NOSCOPE_BODY=$(jbody "$KEY_NOSCOPE_JSON")
KEY_NOSCOPE_ID=$(jget "$KEY_NOSCOPE_BODY" item id)
KEY_NOSCOPE_TOKEN=$(jget "$KEY_NOSCOPE_BODY" key)

KEY_LIMIT_JSON=$(api POST /integrations/api-keys '{"name":"M10bLimitKey","scopes":["events:read"]}')
KEY_LIMIT_BODY=$(jbody "$KEY_LIMIT_JSON")
KEY_LIMIT_ID=$(jget "$KEY_LIMIT_BODY" item id)
KEY_LIMIT_TOKEN=$(jget "$KEY_LIMIT_BODY" key)

WS_URL="$WS_DIRECT_BASE/api/public/v1/events/ws"

READY_OUT=$("$PYBIN" "$WS_PROBE" ready "$WS_URL" "$KEY_EVENTS_TOKEN" 2>&1)
check "$(echo "$READY_OUT" | grep -q '^seq='; echo $?)" "WS: sarlavha (header) autentifikatsiyasi -> ready" "$READY_OUT"

FIRSTMSG_OUT=$("$PYBIN" "$WS_PROBE" first-msg-send "$WS_URL" "$KEY_EVENTS_TOKEN" 2>&1)
check "$(echo "$FIRSTMSG_OUT" | grep -q '^seq='; echo $?)" "WS: birinchi-xabar autentifikatsiyasi -> ready" "$FIRSTMSG_OUT"

NOAUTH_OUT=$("$PYBIN" "$WS_PROBE" closecode "$WS_URL" 2>&1)
check "$(echo "$NOAUTH_OUT" | grep -q 'code=4401'; echo $?)" "WS: token yo'q -> 4401" "$NOAUTH_OUT"

NOSCOPE_OUT=$("$PYBIN" "$WS_PROBE" closecode "$WS_URL" "$KEY_NOSCOPE_TOKEN" 2>&1)
check "$(echo "$NOSCOPE_OUT" | grep -q 'code=4403'; echo $?)" "WS: events:read skopi yo'q -> 4403" "$NOSCOPE_OUT"

echo "--- since_seq replay (include_internal bilan/bilmasdan) ---"
BASE_SEQ=$(sql "select coalesce(max(seq),0) from integration_events")
TENANT_ID=$(sql "select id from tenants limit 1")
INT_DEDUPE="m10b-int-$(sql "select gen_random_uuid()")"
NORM_DEDUPE="m10b-norm-$(sql "select gen_random_uuid()")"
# `type` ustunida CHECK cheklovi bor ('call.ringing'/'call.answered'/'call.ended'/
# 'test.ping' — faqat shular) — "ichki" hodisa ALOHIDA `type` EMAS, xuddi
# haqiqiy ichki (ext->ext) qo'ng'iroqdagidek BIR XIL `call.ended` turi,
# faqat `internal` bayrogi farq qiladi (`missed_call_rules.py` bilan BIR XIL
# naqsh).
INT_SEQ=$(sql "insert into integration_events (tenant_id, type, dedupe_key, internal, payload)
               values ('$TENANT_ID', 'call.ended', '$INT_DEDUPE', true, '{\"probe\":\"m10b\"}'::jsonb) returning seq")
NORM_SEQ=$(sql "insert into integration_events (tenant_id, type, dedupe_key, internal, payload)
                values ('$TENANT_ID', 'call.ended', '$NORM_DEDUPE', false, '{\"probe\":\"m10b\"}'::jsonb) returning seq")
[[ -n "$INT_SEQ" && -n "$NORM_SEQ" ]] || { fail "integration_events sintetik kiritish muvaffaqiyatsiz (INT=$INT_SEQ NORM=$NORM_SEQ)"; }

REPLAY_DEFAULT=$("$PYBIN" "$WS_PROBE" replay "$WS_URL" "$KEY_EVENTS_TOKEN" "$BASE_SEQ" '*' 2>&1)
check "$(echo "$REPLAY_DEFAULT" | grep -q "seq=$NORM_SEQ"; echo $?)" \
  "WS replay (include_internal=false): oddiy hodisa keldi" "$REPLAY_DEFAULT"
check "$(! echo "$REPLAY_DEFAULT" | grep -q "seq=$INT_SEQ"; echo $?)" \
  "WS replay (include_internal=false): ICHKI hodisa YO'Q (sukut qoida)" "$REPLAY_DEFAULT"

REPLAY_INTERNAL=$("$PYBIN" "$WS_PROBE" replay "$WS_URL" "$KEY_EVENTS_TOKEN" "$BASE_SEQ" '*' true 2>&1)
check "$(echo "$REPLAY_INTERNAL" | grep -q "seq=$INT_SEQ"; echo $?)" \
  "WS replay (include_internal=true): ICHKI hodisa HAM keldi" "$REPLAY_INTERNAL"
check "$(echo "$REPLAY_INTERNAL" | grep -q "seq=$NORM_SEQ"; echo $?)" \
  "WS replay (include_internal=true): oddiy hodisa ham keldi" "$REPLAY_INTERNAL"

echo "--- jonli tarqatish (fon so'rovchi, ~1s davriy) ---"
LIVE_DEDUPE="m10b-live-$(sql "select gen_random_uuid()")"
( "$PYBIN" "$WS_PROBE" live "$WS_URL" "$KEY_EVENTS_TOKEN" 'call.ended' 6 > /tmp/m10b-live.out 2>&1 ) &
LIVE_PID=$!
sleep 1
sql "insert into integration_events (tenant_id, type, dedupe_key, internal, payload)
     values ('$TENANT_ID', 'call.ended', '$LIVE_DEDUPE', false, '{\"probe\":\"m10b-live\"}'::jsonb)" >/dev/null
wait "$LIVE_PID"; LIVE_RC=$?
LIVE_OUT=$(cat /tmp/m10b-live.out 2>/dev/null)
check "$LIVE_RC" "WS: fon so'rovchi (events_ws_broadcast) orqali yangi hodisa real vaqtda yetkazildi" "$LIVE_OUT"

echo "--- ulanish chegarasi (5/kalit) -> 4429 ---"
LIMIT_OUT=$("$PYBIN" "$WS_PROBE" limit "$WS_URL" "$KEY_LIMIT_TOKEN" 5 2>&1)
check "$(echo "$LIMIT_OUT" | grep -q 'code=4429'; echo $?)" "WS: 6-chi ulanish (5/kalit chegarasidan keyin) -> 4429" "$LIMIT_OUT"

echo "--- nginx wss:// yo'li (443) ---"
WS_WSS_URL="$WS_WSS_BASE/api/public/v1/events/ws"
WSS_OUT=$("$PYBIN" "$WS_PROBE" ready "$WS_WSS_URL" "$KEY_EVENTS_TOKEN" 2>&1)
check "$(echo "$WSS_OUT" | grep -q '^seq='; echo $?)" "WS: nginx wss://(443) orqali ham ishlaydi" "$WSS_OUT"

api DELETE "/integrations/api-keys/$KEY_EVENTS_ID" >/dev/null
api DELETE "/integrations/api-keys/$KEY_NOSCOPE_ID" >/dev/null
api DELETE "/integrations/api-keys/$KEY_LIMIT_ID" >/dev/null

echo "=== B2: 2FA (TOTP, RFC 6238) ==="
# Asosiy `admin` sessiyasiga (keyingi bo'limlar/boshqa isbot skriptlari uning
# 2FA'siz kira olishiga tayanadi) TEGMASLIK uchun — IKKI ALOHIDA admin-rolli
# test foydalanuvchisi (`m10badmin2` o'z 2FA'sini yoqadi, `m10badmin3` siyosat
# sinovida ATAYLAB yoqmaydi).
ADM2_PASSWORD="M10bPass123"
ADM3_PASSWORD="M10bPass123"
ADM2_JSON=$(api POST /users "{\"username\":\"m10badmin2\",\"full_name\":\"M10b Admin2\",\"role\":\"admin\",\"password\":\"$ADM2_PASSWORD\",\"language\":\"uz\"}")
check "$( [[ "$(jcode "$ADM2_JSON")" == "201" ]]; echo $?)" "POST /users -> m10badmin2 (admin) yaratildi" "$ADM2_JSON"
ADM2_ID=$(jget "$(jbody "$ADM2_JSON")" item id)

# `m10badmin3` HAM shu yerda (siyosat yoqilishidan OLDIN, asosiy `admin` orqali)
# yaratiladi — siyosat "admins" bo'lgan vaqt oynasida asosiy `admin` BIRON
# so'rov yubormaydi (o'zi hali 2FA'ga ro'yxatdan o'tmagan, bloklanib qoladi).
ADM3_JSON=$(api POST /users "{\"username\":\"m10badmin3\",\"full_name\":\"M10b Admin3\",\"role\":\"admin\",\"password\":\"$ADM3_PASSWORD\",\"language\":\"uz\"}")
check "$( [[ "$(jcode "$ADM3_JSON")" == "201" ]]; echo $?)" "POST /users -> m10badmin3 (admin) yaratildi" "$ADM3_JSON"
ADM3_ID=$(jget "$(jbody "$ADM3_JSON")" item id)

T2=$(login_as m10badmin2 "$ADM2_PASSWORD")
[[ -n "$T2" ]] && pass "m10badmin2 login -> token (2FA hali yoqilmagan)" || fail "m10badmin2 login -> token yo'q"

SETUP_JSON=$(api_as "$T2" POST /me/2fa/setup)
check "$( [[ "$(jcode "$SETUP_JSON")" == "200" ]]; echo $?)" "POST /me/2fa/setup -> 200" "$SETUP_JSON"
SECRET=$(jget "$(jbody "$SETUP_JSON")" secret)
[[ -n "$SECRET" ]] && pass "TOTP sekret olindi" || fail "TOTP sekret yo'q -> $SETUP_JSON"

CODE_NOW=$(totp_code "$SECRET" 0)
CODE_NEXT=$(totp_code "$SECRET" 30)
ENABLE_JSON=$(api_as "$T2" POST /me/2fa/enable "{\"code\":\"$CODE_NOW\"}")
check "$( [[ "$(jcode "$ENABLE_JSON")" == "200" ]]; echo $?)" "POST /me/2fa/enable -> 200" "$ENABLE_JSON"
# `jget` ro'yxatni Python repr (bitta qo'shtirnoq) qilib chiqaradi — JSON
# EMAS, shu sabab ro'yxat uchun to'g'ridan-to'g'ri xom tanadan (`jbody`) o'qiymiz.
ENABLE_BODY=$(jbody "$ENABLE_JSON")
RECOVERY_COUNT=$(python3 -c "import json,sys; print(len(json.loads(sys.argv[1])['recovery_codes']))" "$ENABLE_BODY" 2>/dev/null || echo 0)
check "$( [[ "$RECOVERY_COUNT" == "10" ]]; echo $?)" "2FA yoqildi -> 10 ta tiklash kodi qaytdi" "$ENABLE_JSON"
RECOVERY_CODE_1=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['recovery_codes'][0])" "$ENABLE_BODY" 2>/dev/null)

echo "--- login 2 bosqich + takror himoyasi ---"
LOGIN1_JSON=$(curl -s -X POST "$API_BASE/auth/login" -H 'Content-Type: application/json' \
  -d "{\"login\":\"m10badmin2\",\"password\":\"$ADM2_PASSWORD\"}")
check "$( [[ "$(jget "$LOGIN1_JSON" status)" == "totp_required" ]]; echo $?)" \
  "POST /auth/login (2FA yoqilgan) -> status=totp_required" "$LOGIN1_JSON"
CHALLENGE1=$(jget "$LOGIN1_JSON" challenge)

REPLAY_LOGIN=$(curl -s -w '\n%{http_code}' -X POST "$API_BASE/auth/login/totp" -H 'Content-Type: application/json' \
  -d "{\"challenge\":\"$CHALLENGE1\",\"code\":\"$CODE_NOW\"}")
check "$(err_is "$REPLAY_LOGIN" 401 invalid_code; echo $?)" \
  "POST /auth/login/totp (ENABLE'da ishlatilgan kodni QAYTA yuborish) -> 401 invalid_code (takror himoyasi)" "$REPLAY_LOGIN"

FRESH_LOGIN=$(curl -s -w '\n%{http_code}' -X POST "$API_BASE/auth/login/totp" -H 'Content-Type: application/json' \
  -d "{\"challenge\":\"$CHALLENGE1\",\"code\":\"$CODE_NEXT\"}")
check "$( [[ "$(jcode "$FRESH_LOGIN")" == "200" ]]; echo $?)" \
  "POST /auth/login/totp (YANGI qadam kodi) -> 200 (to'liq login)" "$FRESH_LOGIN"

echo "--- tiklash kodi (bir martalik) ---"
LOGIN2_JSON=$(curl -s -X POST "$API_BASE/auth/login" -H 'Content-Type: application/json' \
  -d "{\"login\":\"m10badmin2\",\"password\":\"$ADM2_PASSWORD\"}")
CHALLENGE2=$(jget "$LOGIN2_JSON" challenge)
RECOVERY_LOGIN1=$(curl -s -w '\n%{http_code}' -X POST "$API_BASE/auth/login/totp" -H 'Content-Type: application/json' \
  -d "{\"challenge\":\"$CHALLENGE2\",\"code\":\"$RECOVERY_CODE_1\"}")
check "$( [[ "$(jcode "$RECOVERY_LOGIN1")" == "200" ]]; echo $?)" \
  "POST /auth/login/totp (tiklash kodi, 1-marta) -> 200" "$RECOVERY_LOGIN1"

LOGIN3_JSON=$(curl -s -X POST "$API_BASE/auth/login" -H 'Content-Type: application/json' \
  -d "{\"login\":\"m10badmin2\",\"password\":\"$ADM2_PASSWORD\"}")
CHALLENGE3=$(jget "$LOGIN3_JSON" challenge)
RECOVERY_LOGIN2=$(curl -s -w '\n%{http_code}' -X POST "$API_BASE/auth/login/totp" -H 'Content-Type: application/json' \
  -d "{\"challenge\":\"$CHALLENGE3\",\"code\":\"$RECOVERY_CODE_1\"}")
check "$(err_is "$RECOVERY_LOGIN2" 401 invalid_code; echo $?)" \
  "POST /auth/login/totp (BIR XIL tiklash kodi, 2-marta) -> 401 invalid_code (bir martalik)" "$RECOVERY_LOGIN2"

echo "--- require_2fa siyosati ('admins') -> ro'yxatdan o'tish majburiyati ---"
# T2 (m10badmin2) ALLAQACHON 2FA yoqgan — siyosat o'rnatilgandan KEYIN ham
# T2 o'zi uchun bloklanmaydi, shu sabab siyosatni O'RNATISH VA QAYTARISH
# ikkalasi HAM T2 orqali (asosiy `admin`ga HECH QACHON tegmaymiz).
SEC_BEFORE=$(api_as "$T2" GET /security/settings)
SEC_UPDATED_AT=$(jget "$(jbody "$SEC_BEFORE")" updated_at)
POLICY_ON=$(api_as "$T2" PATCH /security/settings "{\"require_2fa\":\"admins\",\"updated_at\":\"$SEC_UPDATED_AT\"}")
check "$( [[ "$(jcode "$POLICY_ON")" == "200" ]]; echo $?)" "PATCH /security/settings require_2fa=admins -> 200" "$POLICY_ON"
restore_2fa_policy() { # tozalik uchun — boshqa isbot skriptlari admin'ning 2FA'siz kira olishiga tayanadi
  local cur updated_at
  cur=$(api_as "$T2" GET /security/settings 2>/dev/null)
  [[ "$(jget "$(jbody "$cur")" require_2fa)" == "off" ]] && return 0
  updated_at=$(jget "$(jbody "$cur")" updated_at)
  api_as "$T2" PATCH /security/settings "{\"require_2fa\":\"off\",\"updated_at\":\"$updated_at\"}" >/dev/null
}
trap restore_2fa_policy EXIT

T3=$(login_as m10badmin3 "$ADM3_PASSWORD")
[[ -n "$T3" ]] && pass "m10badmin3 login -> token (siyosat allaqachon 'admins', lekin login o'zi bloklanmaydi)" \
  || fail "m10badmin3 login -> token yo'q"

BLOCKED=$(api_as "$T3" GET /extensions)
check "$(err_is "$BLOCKED" 403 2fa_enrollment_required; echo $?)" \
  "GET /extensions (ro'yxatdan o'tmagan admin, siyosat=admins) -> 403 2fa_enrollment_required" "$BLOCKED"

EXEMPT_SETUP=$(api_as "$T3" POST /me/2fa/setup)
check "$( [[ "$(jcode "$EXEMPT_SETUP")" == "200" ]]; echo $?)" \
  "POST /me/2fa/setup (majburiylik ostida ham ISTISNO yo'l) -> 200" "$EXEMPT_SETUP"
SECRET3=$(jget "$(jbody "$EXEMPT_SETUP")" secret)
CODE3=$(totp_code "$SECRET3" 0)
EXEMPT_ENABLE=$(api_as "$T3" POST /me/2fa/enable "{\"code\":\"$CODE3\"}")
check "$( [[ "$(jcode "$EXEMPT_ENABLE")" == "200" ]]; echo $?)" \
  "POST /me/2fa/enable (ISTISNO yo'l) -> 200" "$EXEMPT_ENABLE"

UNBLOCKED=$(api_as "$T3" GET /extensions)
check "$( [[ "$(jcode "$UNBLOCKED")" == "200" ]]; echo $?)" \
  "GET /extensions (ro'yxatdan o'tgandan keyin) -> 200 (403 ko'tarildi)" "$UNBLOCKED"

echo "--- admin /users/{id}/2fa/reset ---"
# Asosiy `admin` emas — T2 orqali (siyosat hali "admins", asosiy `admin`
# hamon ro'yxatdan o'tmagan, shu sabab unga HECH BIR so'rov yubormaymiz).
RESET_JSON=$(api_as "$T2" POST "/users/$ADM3_ID/2fa/reset")
check "$( [[ "$(jcode "$RESET_JSON")" == "200" ]]; echo $?)" "POST /users/{id}/2fa/reset -> 200" "$RESET_JSON"
check "$( [[ "$(jget "$(jbody "$RESET_JSON")" ok)" == "True" ]]; echo $?)" "2fa/reset -> ok=true" "$RESET_JSON"

RE_BLOCKED=$(api_as "$T3" GET /extensions)
check "$(err_is "$RE_BLOCKED" 403 2fa_enrollment_required; echo $?)" \
  "GET /extensions (admin reset'dan keyin, 2FA yana o'chirilgan) -> yana 403" "$RE_BLOCKED"

restore_2fa_policy
trap - EXIT
POLICY_AFTER=$(jget "$(jbody "$(api GET /security/settings)")" require_2fa)
check "$( [[ "$POLICY_AFTER" == "off" ]]; echo $?)" "require_2fa siyosati 'off'ga qaytarildi (tozalik)" "$POLICY_AFTER"

echo "--- TOTP brute-force: har safar yangi challenge -> baribir blok (423) ---"
# m10badmin2 (2FA yoqilgan) — oxirgi tekshiruv, keyin o'chiriladi.
BF_LAST=""
for _ in 1 2 3 4 5 6; do
  BF_CH=$(jget "$(curl -s -X POST "$API_BASE/auth/login" -H 'Content-Type: application/json' \
    -d "{\"login\":\"m10badmin2\",\"password\":\"$ADM2_PASSWORD\"}")" challenge)
  BF_LAST=$(curl -s -w '\n%{http_code}' -X POST "$API_BASE/auth/login/totp" -H 'Content-Type: application/json' \
    -d "{\"challenge\":\"$BF_CH\",\"code\":\"000000\"}")
done
BF_LOGIN=$(curl -s -w '\n%{http_code}' -X POST "$API_BASE/auth/login" -H 'Content-Type: application/json' \
  -d "{\"login\":\"m10badmin2\",\"password\":\"$ADM2_PASSWORD\"}")
check "$(err_is "$BF_LOGIN" 423 locked; echo $?)" \
  "5+ noto'g'ri TOTP (har biri yangi challenge) -> hisob bloklandi (423 locked)" "$BF_LOGIN $BF_LAST"

echo "=== tozalash ==="
api DELETE "/users/$ADM2_ID" >/dev/null
api DELETE "/users/$ADM3_ID" >/dev/null
OPUSER_ID=$(jget "$(jbody "$OPUSER_JSON")" item id)
api DELETE "/users/$OPUSER_ID" >/dev/null
api DELETE "/extensions/$OPEXT_ID" >/dev/null

echo
echo "=== NATIJA: PASS=$PASS FAIL=$FAIL ==="
(( FAIL == 0 ))
