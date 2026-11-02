#!/usr/bin/env bash
# M5b isboti (replica/m5b-contract.md): Follow Me + QR orqali mobil softfonni sozlash.
#   1. API tekshiruvlari: 422 (bo'sh, o'zi, yo'q ichki raqam, park, ring_seconds), toll -> follow_me_outbound_forbidden.
#   2. ring_all: 204 -> 201 (javob yo'q) -> 201 + 202 + 203 parallel, 202 javob beradi. Reload YO'Q (realtime).
#   3. sequential: 202 (javob yo'q) -> keyin 203 javob beradi; 202 CANCEL oldi.
#   4. tashqi raqam trunk orqali, trunk'dan kirgan qo'ng'iroqda: tasdiq (DTMF 1) -> ulanadi; tasdiqsiz -> ulanmaydi.
#   5. *21 almashtirish (yoqish/o'chirish), bo'sh ro'yxatda yoqilmaydi.
#   6. operator: /me/follow-me o'zi, admin yo'li 403, ichki raqamsiz 409 no_extension.
#   7. QR: 409 (tashqi manzil yo'q / webrtc), token -> Linphone XML (parol bor), bazada faqat xesh, jurnalda `***`,
#      60 s grace, yangi token eskisini bekor qiladi, xato urinishlar limiti (403 rate_limited).
# Foydalanish: scripts/m5b-proof.sh [--fresh]
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

declare -A IP=([201]="172.21.0.180" [202]="172.21.0.181" [203]="172.21.0.182" [204]="172.21.0.183"
               [trunk]="172.21.0.184" [probe]="172.21.0.185")
EXT_NUMBER="998901112233"   # Follow Me tashqi raqami (marshrut 998XXXXXXXXX -> M5bTrunk)
DID="555010050"             # trunk -> 201
OPERATOR_LOGIN="m5b_operator"
OPERATOR_PASSWORD="M5bOperPass9x"

source "$LIB_DIR/m2a_common.sh"
source "$LIB_DIR/m3b_common.sh"

ADMIN_PASSWORD="${PROOF_ADMIN_PASSWORD:-$(grep -E '^PROOF_ADMIN_PASSWORD=' "$DEPLOY_DIR/.env" | cut -d= -f2-)}"
[[ -n "$ADMIN_PASSWORD" ]] || { echo "PROOF_ADMIN_PASSWORD deploy/.env da yo'q"; exit 2; }

CONTAINERS=(m5b-proof-201 m5b-proof-202 m5b-proof-203 m5b-proof-204 m5b-proof-trunk m5b-proof-probe)
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
LEFTOVER=$(jget "$(jbody "$(api GET "/extensions?q=M5b")")" total 2>/dev/null)
if [[ -n "$LEFTOVER" && "$LEFTOVER" != "0" ]]; then
  echo "Stekda oldingi M5b qoldiqlari bor ($LEFTOVER ext) — 'scripts/m5b-proof.sh --fresh' bilan ishga tushiring."
  exit 2
fi

echo "=== resurslar ==="
declare -A EXT_ID SECRET
for n in 201 202 203 204; do
  j=$(jbody "$(api POST /extensions "{\"number\":\"$n\",\"name\":\"M5b$n\",\"ring_seconds\":5}")")
  EXT_ID[$n]=$(jget "$j" item id); SECRET[$n]=$(jget "$j" sip password)
done
check "$( [[ -n "${EXT_ID[201]}" && -n "${EXT_ID[204]}" ]]; echo $?)" "POST /extensions 201..204 (ring 5 s)" "${EXT_ID[*]}"
TRUNK_ID=$(jget "$(jbody "$(api POST /trunks "{\"name\":\"M5bTrunk\",\"host\":\"${IP[trunk]}\",\"port\":5060,\"match\":[\"${IP[trunk]}/32\"],\"codecs\":[\"ulaw\"],\"max_channels\":5,\"enabled\":true}")")" item id)
ROUTE=$(api POST /outbound-routes "{\"name\":\"M5bRoute\",\"priority\":1,\"patterns\":[{\"pattern\":\"998XXXXXXXXX\"}],\"trunk_ids\":[\"$TRUNK_ID\"],\"international\":false}")
T201=$(jbody "$(api GET "/targets?kind=extension&q=201")" | python3 -c "
import json,sys
print(next((i['id'] for i in json.load(sys.stdin)['items'] if i.get('number') == '201'), ''))")
INB=$(api POST /inbound-routes "{\"name\":\"M5bDid\",\"did\":\"$DID\",\"target_id\":\"$T201\",\"enabled\":true}")
check "$( [[ -n "$TRUNK_ID" && "$(jcode "$ROUTE")" == "201" && "$(jcode "$INB")" == "201" ]]; echo $?)" \
  "trunk + marshrut 998XXXXXXXXX + kiruvchi DID $DID -> 201" "$ROUTE / $INB"
check "$(ast "dialplan show t1-fm" | grep -q "INNOVA_FM_OWNER"; ast "dialplan show t1-fm-leg" | grep -q "INNOVA_FM_TRUNK"; echo $?)" \
  "Asterisk: t1-fm va t1-fm-leg kontekstlari yuklangan"

echo "=== telefonlar ==="
for c in 201 202 203 204 trunk; do
  docker run -d --name "m5b-proof-$c" --network "$NET" --ip "${IP[$c]}" "$PY_IMAGE" sleep infinity >/dev/null
  for f in outbound_invite.py vm_caller.py m2a_phone.py; do docker cp "$SIPP_DIR/$f" "m5b-proof-$c:/tmp/$f"; done
done
for n in 201 202 203 204; do
  docker exec -d "m5b-proof-$n" sh -c "cd /tmp && echo ring > /tmp/mode && python3 m2a_phone.py serve t1-$n '${SECRET[$n]}' 5070 12000 /tmp/mode 900 > /tmp/phone.log 2>&1"
done
docker exec m5b-proof-trunk sh -c "echo busy > /tmp/mode"
docker exec -d m5b-proof-trunk sh -c "cd /tmp && python3 m2a_phone.py serve trunk - 5060 12000 /tmp/mode 900 > /tmp/phone.log 2>&1"
registered() { for n in 201 202 203 204; do docker exec "m5b-proof-$n" grep -q 'REGISTER_RESULT: OK' /tmp/phone.log 2>/dev/null || return 1; done; }
wait_until 15 registered && pass "201..204 REGISTER -> 200 OK" || fail "REGISTER"

mode() { docker exec "m5b-proof-$1" sh -c "echo '$2' > /tmp/mode"; }
plog() { docker exec "m5b-proof-$1" cat /tmp/phone.log 2>/dev/null; }
invites() { plog "$1" | grep -c '^INVITE '; }
cancels() { plog "$1" | grep -c '^REQ CANCEL'; }
CALL_N=0
place_call() { # ext dialed talk_s -> $OUT
  CALL_N=$((CALL_N + 1))
  OUT=$(docker exec "m5b-proof-$1" sh -c "cd /tmp && python3 m2a_phone.py call t1-$1 '${SECRET[$1]}' $((5100 + CALL_N)) $((13000 + CALL_N * 2)) '$2' $3" 2>&1)
}
trunk_call() { # caller_num did talk_s -> $OUT (trunk IP'sidan, autentifikatsiyasiz)
  CALL_N=$((CALL_N + 1))
  OUT=$(docker exec m5b-proof-trunk sh -c "cd /tmp && python3 m2a_phone.py call '$1' unused $((5100 + CALL_N)) $((13000 + CALL_N * 2)) '$2' $3" 2>&1)
}
final_of() { sed -n 's/^INVITE_FINAL: SIP\/2.0 \([0-9]*\).*/\1/p' <<<"$1"; }
FM="/extensions/${EXT_ID[201]}/follow-me"
fm_put() { # json (updated_at'siz) -> $PUT_OUT
  PUT_OUT=$(api PUT "$FM" "$1")
}
fm_state() { sql "select fm_enabled::text||'|'||fm_strategy||'|'||coalesce(fm_numbers,'') from asterisk_ext_state where endpoint='t1-201'"; }
ext_stamp() { jget "$(jbody "$(api GET "/extensions/$1/follow-me")")" updated_at; }  # ext_id -> updated_at
revisions() { sql "select count(*) from config_revisions"; }

echo "--- 1. API tekshiruvlari ---"
R=$(api GET "$FM")
check "$( [[ "$(jcode "$R")" == "200" && "$(jget "$(jbody "$R")" follow_me enabled)" == "False" && "$(jget "$(jbody "$R")" follow_me strategy)" == "ring_all" ]]; echo $?)" \
  "1: GET follow-me -> standart (o'chiq, ring_all)" "$R"
for spec in '{"enabled":true,"numbers":[]}|follow_me_empty' '{"numbers":["201"]}|follow_me_self' \
            '{"numbers":["299"]}|follow_me_unknown_extension' '{"numbers":["701"]}|follow_me_bad_target' \
            '{"numbers":["202","202"]}|follow_me_duplicate'; do
  fm_put "${spec%%|*}"
  check "$(err_is "$PUT_OUT" 422 "${spec##*|}"; echo $?)" "1: PUT ${spec%%|*} -> 422 ${spec##*|}" "$PUT_OUT"
done
fm_put '{"numbers":["202"],"ring_seconds":4}'
check "$( [[ "$(jcode "$PUT_OUT")" == "422" ]]; echo $?)" "1: ring_seconds=4 -> 422" "$PUT_OUT"
STAMP=$(ext_stamp "${EXT_ID[201]}")
api PATCH "/extensions/${EXT_ID[201]}" "{\"outbound_allowed\":false,\"updated_at\":\"$STAMP\"}" >/dev/null
fm_put "{\"enabled\":true,\"numbers\":[\"$EXT_NUMBER\"]}"
check "$(err_is "$PUT_OUT" 422 follow_me_outbound_forbidden; echo $?)" "1: outbound_allowed=false + tashqi raqam -> 422" "$PUT_OUT"
STAMP=$(ext_stamp "${EXT_ID[201]}")
api PATCH "/extensions/${EXT_ID[201]}" "{\"outbound_allowed\":true,\"updated_at\":\"$STAMP\"}" >/dev/null
fm_put '{"numbers":["202"],"updated_at":"2020-01-01T00:00:00Z"}'
check "$(err_is "$PUT_OUT" 409 stale; echo $?)" "1: eskirgan updated_at -> 409 stale" "$PUT_OUT"

echo "--- 2. ring_all (reload'siz) ---"
REV0=$(revisions)
fm_put '{"enabled":true,"numbers":["202","203"],"strategy":"ring_all","include_extension":true,"ring_seconds":10,"confirm":false}'
check "$( [[ "$(jcode "$PUT_OUT")" == "200" && "$(fm_state)" == "true|ring_all|202&203" && "$(revisions)" == "$REV0" ]]; echo $?)" \
  "2: PUT -> 200, asterisk_ext_state fm_enabled=t, reviziya YO'Q (realtime)" "$PUT_OUT / $(fm_state)"
AUD=$(sql "select diff::text from audit_log where action='update' and entity='extension' and diff ? 'follow_me' and entity_id='${EXT_ID[201]}' order by id desc limit 1")
check "$(grep -q '"follow_me"' <<<"$AUD"; echo $?)" "2: audit extension.update diff.follow_me" "$AUD"
mode 201 ring; mode 202 answer; mode 203 ring
B201=$(invites 201); B202=$(invites 202); B203=$(invites 203); C203=$(cancels 203)
place_call 204 201 2
check "$( [[ "$(final_of "$OUT")" == "200" && "$(invites 201)" == "$((B201 + 2))" && "$(invites 202)" == "$((B202 + 1))" && "$(invites 203)" == "$((B203 + 1))" && "$(cancels 203)" == "$((C203 + 1))" ]]; echo $?)" \
  "2: 204 -> 201 javobsiz -> 201+202+203 parallel, 202 javob berdi, 203 CANCEL" \
  "$OUT / 201:$(invites 201) 202:$(invites 202) 203:$(invites 203)"

echo "--- 3. sequential ---"
fm_put '{"enabled":true,"numbers":["202","203"],"strategy":"sequential","include_extension":false,"ring_seconds":5,"confirm":false}'
mode 202 ring; mode 203 answer
B201=$(invites 201); B202=$(invites 202); B203=$(invites 203); C202=$(cancels 202)
place_call 204 201 2
SEQ_ORDER=$(plog 202 | grep -E '^(INVITE|REQ CANCEL)' | tail -2 | cut -c1-6 | tr '\n' ' ')
check "$( [[ "$(final_of "$OUT")" == "200" && "$(invites 201)" == "$((B201 + 1))" && "$(invites 202)" == "$((B202 + 1))" && "$(cancels 202)" == "$((C202 + 1))" && "$(invites 203)" == "$((B203 + 1))" ]]; echo $?)" \
  "3: 204 -> 201 -> 202 (5 s, CANCEL) -> 203 javob berdi" "$OUT / $SEQ_ORDER"

echo "--- 4. tashqi raqam trunk orqali (trunk'dan kirgan qo'ng'iroq) ---"
fm_put "{\"enabled\":true,\"numbers\":[\"$EXT_NUMBER\"],\"strategy\":\"ring_all\",\"include_extension\":false,\"ring_seconds\":15,\"confirm\":true}"
mode 201 ring; mode trunk 'answer:1'
BT=$(invites trunk)
trunk_call 998900000555 "$DID" 3
TRUNK_INV=$(plog trunk | grep '^INVITE ' | tail -1)
check "$( [[ "$(final_of "$OUT")" == "200" && "$(invites trunk)" == "$((BT + 1))" ]] && grep -q "$EXT_NUMBER" <<<"$TRUNK_INV"; echo $?)" \
  "4: trunk -> DID -> 201 javobsiz -> $EXT_NUMBER (trunk), tasdiq DTMF 1 -> ulandi" "$OUT / $TRUNK_INV"
mode trunk answer
BT=$(invites trunk)
trunk_call 998900000555 "$DID" 2
check "$( [[ "$(final_of "$OUT")" != "200" && "$(invites trunk)" == "$((BT + 1))" ]]; echo $?)" \
  "4: tasdiqsiz (DTMF yo'q) -> tashqi oyoq tashlandi, chaqiruvchi ulanmadi" "$OUT"
fm_put "{\"enabled\":true,\"numbers\":[\"$EXT_NUMBER\"],\"ring_seconds\":15,\"confirm\":false,\"include_extension\":false}"
STAMP=$(ext_stamp "${EXT_ID[201]}")
api PATCH "/extensions/${EXT_ID[201]}" "{\"outbound_allowed\":false,\"updated_at\":\"$STAMP\"}" >/dev/null
BT=$(invites trunk)
place_call 204 201 1
check "$( [[ "$(final_of "$OUT")" != "200" && "$(invites trunk)" == "$BT" ]]; echo $?)" \
  "4: keyin outbound_allowed=false -> Follow Me tashqi oyog'i trunk'ga CHIQMAYDI (egasi ruxsati)" "$OUT"
STAMP=$(ext_stamp "${EXT_ID[201]}")
api PATCH "/extensions/${EXT_ID[201]}" "{\"outbound_allowed\":true,\"updated_at\":\"$STAMP\"}" >/dev/null

echo "--- 5. *21 ---"
fm_put '{"enabled":false,"numbers":["202"]}'
place_call 201 '*21' 4
check "$( [[ "$(final_of "$OUT")" == "200" && "$(jget "$(jbody "$(api GET "$FM")")" follow_me enabled)" == "True" ]]; echo $?)" "5: *21 -> yoqildi" "$OUT"
place_call 201 '*21' 4
check "$( [[ "$(jget "$(jbody "$(api GET "$FM")")" follow_me enabled)" == "False" ]]; echo $?)" "5: *21 yana -> o'chirildi"
fm_put '{"enabled":false,"numbers":[]}'
place_call 201 '*21' 4
check "$( [[ "$(jget "$(jbody "$(api GET "$FM")")" follow_me enabled)" == "False" && "$(sql "select follow_me->>'enabled' from extensions where id='${EXT_ID[201]}'")" == "false" ]]; echo $?)" \
  "5: bo'sh ro'yxatda *21 -> yoqilmaydi (CHECK)"
FC=$(jbody "$(api GET /feature-codes)")
check "$(grep -q '"followme_toggle"' <<<"$FC" && grep -q '"\*21"' <<<"$FC"; echo $?)" "5: GET /feature-codes -> followme_toggle *21"

echo "--- 6. operator /me ---"
OP=$(api POST /users "{\"username\":\"$OPERATOR_LOGIN\",\"full_name\":\"M5b Operator\",\"role\":\"operator\",\"extension_id\":\"${EXT_ID[204]}\",\"password\":\"$OPERATOR_PASSWORD\"}")
OP_TOKEN=$(login_as "$OPERATOR_LOGIN" "$OPERATOR_PASSWORD")
NEW_PW="${OPERATOR_PASSWORD}Z"
CH=$(api_as "$OP_TOKEN" POST /auth/change-password "{\"current\":\"$OPERATOR_PASSWORD\",\"new\":\"$NEW_PW\"}")
[[ "$(jcode "$CH")" == "200" ]] && OP_TOKEN=$(jget "$(jbody "$CH")" access)
R=$(api_as "$OP_TOKEN" PUT /me/follow-me '{"enabled":true,"numbers":["203"],"ring_seconds":12}')
check "$( [[ "$(jcode "$OP")" == "201" && "$(jcode "$R")" == "200" && "$(jget "$(jbody "$R")" number)" == "204" && "$(jget "$(jbody "$R")" follow_me ring_seconds)" == "12" ]]; echo $?)" \
  "6: operator PUT /me/follow-me -> o'z raqami 204" "$R"
R=$(api_as "$OP_TOKEN" GET "$FM")
check "$( [[ "$(jcode "$R")" == "403" ]]; echo $?)" "6: operator GET /extensions/{201}/follow-me -> 403" "$R"
api POST /users "{\"username\":\"m5b_noext\",\"full_name\":\"NoExt\",\"role\":\"operator\",\"password\":\"M5bNoExtPass9\"}" >/dev/null
NOEXT=$(login_as m5b_noext M5bNoExtPass9)
R=$(api_as "$NOEXT" GET /me/follow-me)
check "$(err_is "$R" 409 no_extension; echo $?)" "6: ichki raqamsiz operator -> 409 no_extension" "$R"

echo "--- 7. QR orqali sozlash ---"
QR="/extensions/${EXT_ID[201]}/qr-provisioning"
R=$(api POST "$QR")
check "$(err_is "$R" 409 public_host_not_configured; echo $?)" "7: tashqi manzil yo'q -> 409 public_host_not_configured" "$R"
api PATCH /settings/integrations "{\"public_base_url\":\"$API_ROOT\",\"updated_at\":\"$(updated_at_of /settings/integrations)\"}" >/dev/null
R=$(api POST "$QR"); URL=$(jget "$(jbody "$R")" url); TOKEN=$(basename "$(dirname "$URL")")
check "$( [[ "$(jcode "$R")" == "200" && "$URL" == "$API_ROOT/prov/qr/"*"/linphone.xml" && ${#TOKEN} -ge 43 ]]; echo $?)" \
  "7: POST qr-provisioning -> bir martalik havola (token ${#TOKEN} belgi)" "$R"
TOKEN_HASH=$(printf '%s' "$TOKEN" | sha256sum | cut -d' ' -f1)
check "$( [[ "$(sql "select count(*) from qr_provision_tokens where token_hash=decode('$TOKEN_HASH','hex')")" == "1" ]] \
  && ! sql "select row_to_json(q)::text from qr_provision_tokens q" | grep -q "$TOKEN" \
  && [[ "$(sql "select count(*) from audit_log where entity='extension' and diff->>'qr_provisioning'='issued'")" -ge 1 ]] \
  && ! sql "select diff::text from audit_log where diff ? 'qr_provisioning'" | grep -q "$TOKEN"; echo $?)" \
  "7: bazada faqat SHA-256 xesh; audit (issued) bor, unda token yo'q"
XML=$(curl -s "$URL"); CODE=$(http_code "$URL")
check "$( [[ "$CODE" == "200" ]] && grep -q "<entry name=\"passwd\" overwrite=\"true\">${SECRET[201]}</entry>" <<<"$XML" \
  && grep -q '<entry name="username" overwrite="true">t1-201</entry>' <<<"$XML"; echo $?)" \
  "7: GET havola -> Linphone XML (t1-201 + parol); 60 s ichida qayta -> 200" "$CODE / ${XML:0:120}"
check "$( [[ "$(sql "select count(*) from provision_requests where path='/prov/qr/***/linphone.xml' and status_code=200")" -ge 1 && "$(sql "select count(*) from audit_log where user_id is null and diff->>'qr_provisioning'='used'")" == "1" && "$(sql "select count(*) from provision_requests where path like '%$TOKEN%'")" == "0" ]]; echo $?)" \
  "7: provision_requests: /prov/qr/***/linphone.xml (token yashirin); audit used — 1 marta"
sql "update qr_provision_tokens set first_used_at = now() - interval '61 seconds' where token_hash=decode('$TOKEN_HASH','hex')" >/dev/null
check "$( [[ "$(http_code "$URL")" == "404" ]]; echo $?)" "7: birinchi olishdan 61 s o'tib -> 404"
URL2=$(jget "$(jbody "$(api POST "$QR")")" url)
URL3=$(jget "$(jbody "$(api POST "$QR")")" url)
check "$( [[ "$(http_code "$URL2")" == "404" && "$(http_code "$URL3")" == "200" && "$(sql "select count(*) from qr_provision_tokens where extension_id='${EXT_ID[201]}'")" == "1" ]]; echo $?)" \
  "7: yangi token eskisini bekor qiladi (ichki raqamga bitta token)"
R=$(api_as "$OP_TOKEN" POST /me/qr-provisioning)
check "$( [[ "$(jcode "$R")" == "200" ]] && [[ "$(http_code "$(jget "$(jbody "$R")" url)")" == "200" ]]; echo $?)" \
  "7: operator POST /me/qr-provisioning -> o'z raqami uchun havola" "$R"
check "$( [[ "$(jcode "$(api_as "$OP_TOKEN" POST "$QR")")" == "403" ]]; echo $?)" "7: operator admin QR yo'li -> 403"
STAMP=$(ext_stamp "${EXT_ID[203]}")
api PATCH "/extensions/${EXT_ID[203]}" "{\"webrtc\":true,\"updated_at\":\"$STAMP\"}" >/dev/null
R=$(api POST "/extensions/${EXT_ID[203]}/qr-provisioning")
check "$(err_is "$R" 409 extension_webrtc_only; echo $?)" "7: webrtc ichki raqam -> 409 extension_webrtc_only" "$R"
docker run -d --name m5b-proof-probe --network "$NET" --ip "${IP[probe]}" "$PY_IMAGE" sleep infinity >/dev/null
CODES=$(docker exec m5b-proof-probe python3 -c "
import urllib.request, urllib.error
out = []
for i in range(22):
    try:
        out.append(urllib.request.urlopen('http://api:8000/prov/qr/' + 'x' * 43 + '/linphone.xml', timeout=5).status)
    except urllib.error.HTTPError as e:
        out.append(e.code)
    except Exception as e:
        out.append(0)
print(' '.join(map(str, out)))")
check "$( [[ "$(cut -d' ' -f1-20 <<<"$CODES" | tr ' ' '\n' | sort -u)" == "404" && "$(cut -d' ' -f21- <<<"$CODES")" == "403 403" ]]; echo $?)" \
  "7: 20 ta noto'g'ri token -> 404, keyin IP bloklandi -> 403 rate_limited" "$CODES"

echo
echo "=== NATIJA: PASS=$PASS FAIL=$FAIL ==="
(( FAIL == 0 ))
