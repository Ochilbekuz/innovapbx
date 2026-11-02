#!/usr/bin/env bash
# Innova PBX — M4a (apparat auto-provisioning) proof (replica/m4a-contract.md §5.1–5.6):
#   1. Token/xavfsizlik: noto'g'ri token 404 `bad_token`; noma'lum MAC 404 + discovered (vendor/model UA'dan);
#      tarmoqdan tashqari IP 403; 20 xatodan keyin 21-so'rov 403 `rate_limited` + alert, boshqa IP ishlaydi;
#      umumiy fayl, jurnal, audit, `/devices/{id}/config` da parol yo'q.
#   2. Yealink: topilganni 101 ga biriktirish -> `<mac>.cfg` 200, `account.1.*`; config'dagi login/parol bilan REGISTER 200,
#      status `registered`; BLF 102 -> `linekey.1.type = 16`, `value = 102`.
#   3. Grandstream `cfg<mac>.xml` (XML valid, P35/P34/P47) + REGISTER 200; Fanvil `SIP1 Register User/Pswd`.
#   4. rotate-secret -> `stale_config` -> apparat NOTIFY `check-sync` oladi -> qayta yuklaydi -> yangi parol bilan 200,
#      eski parol 401; ro'yxatda bo'lmagan apparatga resync 409.
#   5. Validatsiya: MAC dublikat 409, webrtc 422, max_contacts 422, BLF noma'lum 422, `\n` 422, `extra` 422.
#   6. Token almashtirish -> eski URL 404, yangi 200; operator -> /devices 403.
# «Apparatlar» — proof tarmog'idagi python konteynerlari (`tests/sipp/m4a_phone.py`, haqiqiy UA satrlari bilan),
# config'ni `web` nginx `/prov/` orqali oladi.
#
# Foydalanish:
#   scripts/m4a-proof.sh            # joriy `innova-m0` stack (M4a qoldiqlari bo'lsa — exit 2)
#   scripts/m4a-proof.sh --fresh    # avval `docker compose down -v` + build + up -d
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
OP_PW="M4aProof!2026a"
ADMIN_PROV_PW="M4aAdm!Phone77"

declare -A MAC=([y]="805ec0a40001" [g]="000b82a40002" [f]="0c383ea40003")
declare -A UA=([y]="Yealink SIP-T46S 66.86.0.15 80:5e:c0:a4:00:01"
               [g]="Grandstream Model HW GXP2170 SW 1.0.11.6 DevId 000b82a40002"
               [f]="Fanvil X4U 2.12.1 0c383ea40003"
               [b]="curl/8.5.0" [o]="Wget/1.21.4")
declare -A FILE=([y]="805ec0a40001.cfg" [g]="cfg000b82a40002.xml" [f]="0c383ea40003.cfg")
declare -A VENDOR=([y]="yealink" [g]="grandstream" [f]="fanvil")

# shellcheck source=lib/m2a_common.sh
source "$LIB_DIR/m2a_common.sh"
# shellcheck source=lib/m3b_common.sh
source "$LIB_DIR/m3b_common.sh"

ADMIN_PASSWORD="${PROOF_ADMIN_PASSWORD:-$(grep -E '^PROOF_ADMIN_PASSWORD=' "$DEPLOY_DIR/.env" | cut -d= -f2-)}"
[[ -n "$ADMIN_PASSWORD" ]] || { echo "PROOF_ADMIN_PASSWORD deploy/.env da yo'q"; exit 2; }

CONTAINERS=(m4a-proof-y m4a-proof-g m4a-proof-f m4a-proof-b m4a-proof-o)
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
LEFTOVER=$(python3 -c "import json,sys;print(len(json.load(sys.stdin)['items']))" <<<"$(jbody "$(api GET /devices)")" 2>/dev/null)
if [[ "$LEFTOVER" != "0" ]]; then
  echo "Stekda oldingi M4a isbot qoldiqlari bor (devices=$LEFTOVER) — 'scripts/m4a-proof.sh --fresh' bilan ishga tushiring."
  exit 2
fi

# ---------------------------------------------------------------- yordamchilar
PREFIX=$(docker network inspect "$NET" -f '{{(index .IPAM.Config 0).Subnet}}' | cut -d. -f1-3)
declare -A IP=([y]="$PREFIX.231" [g]="$PREFIX.232" [f]="$PREFIX.233" [b]="$PREFIX.234" [o]="$PREFIX.250")

phone() { docker exec "m4a-proof-$1" python3 /tmp/m4a_phone.py "${@:2}"; }      # qurilma rejim args...
prov() { phone "$1" fetch "http://web/prov/${3:-$TOKEN}/$2" "${UA[$1]}" /tmp/out; }  # qurilma fayl [token] -> HTTP kod
prov_body() { docker exec "m4a-proof-$1" cat /tmp/out; }
last_req() { sql "select reason||'|'||status_code from provision_requests where ip='$1' order by id desc limit 1"; }
dev() { jbody "$(api GET "/devices/$1")"; }
dev_field() { jget "$(dev "$1")" item "$2"; }
status_is() { [[ "$(dev_field "$1" status)" == "$2" ]]; }
log_count() { docker exec "m4a-proof-$1" sh -c "grep -c '$2' /tmp/phone.log 2>/dev/null || true"; }
log_has_n() { (( $(log_count "$1" "$2") >= $3 )); }                             # qurilma naqsh n
start_phone() { # qurilma lport [reload_delay]
  docker exec -d "m4a-proof-$1" sh -c "cd /tmp && python3 m4a_phone.py phone ${VENDOR[$1]} \
    'http://web/prov/$TOKEN/${FILE[$1]}' '${UA[$1]}' $2 /tmp/phone.log 600 ${3:-0} >/tmp/phone.err 2>&1"
}

# ---------------------------------------------------------------- resurslar
echo "=== resurslar ==="
declare -A EXT_ID SECRET
for spec in 101:false 102:false 103:true 104:false 105:false; do
  n=${spec%%:*}
  j=$(jbody "$(api POST /extensions "{\"number\":\"$n\",\"name\":\"M4a$n\",\"webrtc\":${spec#*:}}")")
  EXT_ID[$n]=$(jget "$j" item id); SECRET[$n]=$(jget "$j" sip password)
  check "$( [[ -n "${EXT_ID[$n]}" ]]; echo $?)" "POST /extensions $n (webrtc=${spec#*:})" "$j"
done

PJ=$(jbody "$(api GET /settings/provisioning)")
TOKEN=$(python3 -c "import json,sys;print(json.load(sys.stdin)['url'].rstrip('/').rsplit('/',1)[1])" <<<"$PJ")
check "$( [[ ${#TOKEN} == 32 ]]; echo $?)" "GET /settings/provisioning -> url /prov/<32 hex>/" "$PJ"
PATCH_J=$(api PATCH /settings/provisioning "{\"updated_at\":\"$(jget "$PJ" updated_at)\",\"sip_server_host\":\"asterisk\",
  \"allowed_networks\":[\"$PREFIX.224/28\"],\"admin_password\":\"$ADMIN_PROV_PW\"}")
check "$( [[ "$(jcode "$PATCH_J")" == "200" && "$(jget "$(jbody "$PATCH_J")" has_admin_password)" == "True" ]]; echo $?)" \
  "PATCH provisioning: sip_server_host=asterisk, allowed_networks=$PREFIX.224/28, admin_password" "$PATCH_J"

for c in y g f b o; do
  docker run -d --name "m4a-proof-$c" --network "$NET" --ip "${IP[$c]}" "$PY_IMAGE" sleep infinity >/dev/null
  for f in m4a_phone.py outbound_invite.py; do docker cp "$SIPP_DIR/$f" "m4a-proof-$c:/tmp/$f"; done
done

# ---------------------------------------------------------------- 1. token / xavfsizlik
echo "=== 1. token/xavfsizlik ==="
BAD_TOKEN=$(python3 -c "import secrets;print(secrets.token_hex(16))")
C=$(prov b y000000000000.cfg "$BAD_TOKEN")
check "$( [[ "$C" == "404" && "$(last_req "${IP[b]}")" == "bad_token|404" ]]; echo $?)" \
  "1: noto'g'ri token -> 404, jurnal bad_token" "$C $(last_req "${IP[b]}")"

for c in y g f; do
  C=$(prov "$c" "${FILE[$c]}")
  check "$( [[ "$C" == "404" && "$(last_req "${IP[$c]}")" == "unknown_mac|404" ]]; echo $?)" \
    "1: ${VENDOR[$c]} noma'lum MAC -> 404 unknown_mac" "$C $(last_req "${IP[$c]}")"
done
DISC=$(jbody "$(api GET /devices/discovered)")
DISC_OK=$(python3 -c '
import json, sys
items = {i["mac"]: i for i in json.load(sys.stdin)["items"]}
want = {"805ec0a40001": ("yealink", "T46S"), "000b82a40002": ("grandstream", "GXP2170"), "0c383ea40003": ("fanvil", "X4U")}
print(all(m in items and (items[m]["vendor"], items[m]["model"]) == v and items[m]["supported"] for m, v in want.items()))
' <<<"$DISC")
check "$( [[ "$DISC_OK" == "True" ]]; echo $?)" "1: /devices/discovered -> 3 MAC, vendor/model UA'dan (T46S, GXP2170, X4U)" "$DISC"

C=$(prov o y000000000000.cfg)
check "$( [[ "$C" == "403" && "$(last_req "${IP[o]}")" == "network_denied|403" ]]; echo $?)" \
  "1: allowed_networks dan tashqari IP (${IP[o]}) -> 403 network_denied" "$C"

C=$(prov y y000000000000.cfg); COMMON=$(prov_body y)
check "$( [[ "$C" == "200" && "$COMMON" == *"local_time.time_zone"* && "${COMMON,,}" != *password* \
  && "$COMMON" != *"${SECRET[101]}"* ]]; echo $?)" "1: umumiy y000000000000.cfg -> 200, parol YO'Q" "$COMMON"

CODES=$(phone b burst "http://web/prov/$BAD_TOKEN/y000000000000.cfg" "${UA[b]}" 19)
C21=$(prov b y000000000000.cfg "$BAD_TOKEN"); R21=$(last_req "${IP[b]}")
check "$( [[ "$CODES" != *403* && "$C21" == "403" && "$R21" == "rate_limited|403" ]]; echo $?)" \
  "1: 20 ta xato (404) -> 21-so'rov 403 rate_limited" "$CODES | $C21 $R21"
C=$(prov b y000000000000.cfg)
check "$( [[ "$C" == "403" ]]; echo $?)" "1: bloklangan IP to'g'ri token bilan ham 403" "$C"
ALERT=$(wait_for_sql "select count(*) from alert_log where kind='prov_bruteforce' and key='prov:${IP[b]}' and text like '%${IP[b]}%'" 5)
check "$( [[ "$ALERT" == "1" ]]; echo $?)" "1: alert prov_bruteforce (bir marta, IP matnda)" "$ALERT"
C=$(prov y y000000000000.cfg)
check "$( [[ "$C" == "200" ]]; echo $?)" "1: boshqa IP (${IP[y]}) ishlaydi -> 200" "$C"

# ---------------------------------------------------------------- 2. Yealink
echo "=== 2. Yealink ==="
AJ=$(api POST "/devices/discovered/${MAC[y]}/assign" "{\"extension_id\":\"${EXT_ID[101]}\",\"label\":\"Qabulxona\"}")
DEV_Y=$(jget "$(jbody "$AJ")" item id)
check "$( [[ "$(jcode "$AJ")" == "201" && "$(jget "$(jbody "$AJ")" item model)" == "T46S" \
  && "$(jget "$(jbody "$AJ")" item status)" == "never" ]]; echo $?)" "2: discovered -> 101 biriktirildi (T46S, never)" "$AJ"
GONE=$(python3 -c "import json,sys;print('805ec0a40001' not in [i['mac'] for i in json.load(sys.stdin)['items']])" \
  <<<"$(jbody "$(api GET /devices/discovered)")")
check "$( [[ "$GONE" == "True" ]]; echo $?)" "2: biriktirilgan MAC discovered'dan chiqdi" "$GONE"
KJ=$(api PUT "/devices/$DEV_Y/keys" '{"keys":[{"idx":1,"type":"blf","value":"102","label":"Rahbar"},{"idx":2,"type":"speed_dial","value":"+998901234567","label":"Mobil"}]}')
check "$( [[ "$(jcode "$KJ")" == "200" && "$(jget "$(jbody "$KJ")" item keys_count)" == "2" ]]; echo $?)" \
  "2: PUT keys (BLF 102, speed dial)" "$KJ"

C=$(prov y "${FILE[y]}"); YCFG=$(prov_body y)
YCHK=$(python3 -c '
import sys
kv = {}
for line in sys.stdin.read().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1); kv[k.strip()] = v.strip()
want = {"account.1.enable": "1", "account.1.auth_name": "t1-101", "account.1.user_name": "t1-101",
        "account.1.password": sys.argv[1], "account.1.sip_server.1.address": "asterisk",
        "account.1.sip_server.1.port": "5060", "account.1.label": "Qabulxona",
        "linekey.1.type": "16", "linekey.1.value": "102", "linekey.2.type": "13",
        "static.security.user_password": "admin:" + sys.argv[2]}
bad = {k: kv.get(k) for k, v in want.items() if kv.get(k) != v}
print("OK" if not bad else bad)' "${SECRET[101]}" "$ADMIN_PROV_PW" <<<"$YCFG")
check "$( [[ "$C" == "200" && "$YCHK" == "OK" ]]; echo $?)" \
  "2: ${FILE[y]} -> 200, account.1.* to'g'ri, linekey.1.type=16 value=102" "$C $YCHK"

start_phone y 5060 4   # check-sync'dan keyin 4 s o'tib qayta yuklaydi (stale_config ko'rinsin)
wait_until 15 log_has_n y "REGISTER 200 t1-101" 1
check "$( log_has_n y "REGISTER 200 t1-101" 1; echo $?)" "2: Yealink config'dagi login/parol bilan REGISTER -> 200" \
  "$(docker exec m4a-proof-y cat /tmp/phone.log /tmp/phone.err 2>&1 | tail -5)"
wait_until 10 status_is "$DEV_Y" registered
check "$( status_is "$DEV_Y" registered; echo $?)" "2: /devices status registered" "$(dev "$DEV_Y")"
CHK_IP=$(dev_field "$DEV_Y" last_ip); CHK_FW=$(dev_field "$DEV_Y" firmware)
check "$( [[ "$CHK_IP" == "${IP[y]}" && "$CHK_FW" == "66.86.0.15" ]]; echo $?)" "2: last_ip/firmware yangilandi" "$CHK_IP $CHK_FW"

# ---------------------------------------------------------------- 3. Grandstream / Fanvil
echo "=== 3. Grandstream / Fanvil ==="
AJ=$(api POST "/devices/discovered/${MAC[g]}/assign" "{\"extension_id\":\"${EXT_ID[102]}\"}")
DEV_G=$(jget "$(jbody "$AJ")" item id)
check "$( [[ "$(jcode "$AJ")" == "201" ]]; echo $?)" "3: Grandstream -> 102 biriktirildi" "$AJ"
C=$(prov g "${FILE[g]}"); GCFG=$(prov_body g)
GCHK=$(python3 -c '
import sys, xml.etree.ElementTree as ET
root = ET.fromstring(sys.stdin.read())
p = {el.tag: el.text for el in root.find("config")}
ok = (root.tag == "gs_provision" and root.findtext("mac") == "000b82a40002" and p.get("P35") == "t1-102"
      and p.get("P34") == sys.argv[1] and p.get("P47") == "asterisk:5060" and p.get("P271") == "1")
print("OK" if ok else p)' "${SECRET[102]}" <<<"$GCFG" 2>&1)
check "$( [[ "$C" == "200" && "$GCHK" == "OK" ]]; echo $?)" "3: ${FILE[g]} -> 200, XML valid, P35/P34/P47 to'g'ri" "$C $GCHK"
start_phone g 5060
wait_until 15 log_has_n g "REGISTER 200 t1-102" 1
check "$( log_has_n g "REGISTER 200 t1-102" 1; echo $?)" "3: Grandstream XML'dagi login/parol bilan REGISTER -> 200" \
  "$(docker exec m4a-proof-g cat /tmp/phone.log /tmp/phone.err 2>&1 | tail -5)"
wait_until 10 status_is "$DEV_G" registered
check "$( status_is "$DEV_G" registered; echo $?)" "3: Grandstream status registered" "$(dev "$DEV_G")"

AJ=$(api POST "/devices/discovered/${MAC[f]}/assign" "{\"extension_id\":\"${EXT_ID[105]}\"}")
DEV_F=$(jget "$(jbody "$AJ")" item id)
C=$(prov f "${FILE[f]}")
docker exec m4a-proof-f sh -c 'cp /tmp/out /tmp/f.cfg'
FCREDS=$(phone f creds fanvil /tmp/f.cfg)
check "$( [[ "$(jcode "$AJ")" == "201" && "$C" == "200" && "$FCREDS" == "t1-105	${SECRET[105]}	asterisk	5060" ]]; echo $?)" \
  "3: Fanvil -> 105, ${FILE[f]} 200, SIP1 Register User/Pswd/Addr/Port to'g'ri" "$C $FCREDS"
check "$( status_is "$DEV_F" provisioned; echo $?)" "3: Fanvil (oldi, ro'yxatdan o'tmagan) -> provisioned" "$(dev "$DEV_F")"

# ---------------------------------------------------------------- 4. yangilanish
echo "=== 4. rotate-secret -> NOTIFY check-sync -> qayta yuklash ==="
PROV_AT_1=$(dev_field "$DEV_Y" provisioned_at)
OLD_SECRET=${SECRET[101]}
RJ=$(jbody "$(api POST "/extensions/${EXT_ID[101]}/rotate-secret")")
NEW_SECRET=$(jget "$RJ" sip password)
ST=$(dev_field "$DEV_Y" status)
check "$( [[ -n "$NEW_SECRET" && "$NEW_SECRET" != "$OLD_SECRET" && "$ST" == "stale_config" ]]; echo $?)" \
  "4: 101 rotate-secret -> status stale_config" "$ST"
wait_until 10 log_has_n y "NOTIFY Event: check-sync" 1
check "$( log_has_n y "NOTIFY Event: check-sync" 1; echo $?)" "4: apparat NOTIFY Event: check-sync oldi" \
  "$(docker exec m4a-proof-y cat /tmp/phone.log 2>&1 | tail -5)"
wait_until 20 log_has_n y "REGISTER 200 t1-101" 2
check "$( [[ "$(log_count y 'FETCH 200')" -ge 2 ]] && log_has_n y "REGISTER 200 t1-101" 2; echo $?)" \
  "4: apparat config'ni qayta oldi va YANGI parol bilan REGISTER -> 200" "$(docker exec m4a-proof-y cat /tmp/phone.log | tail -4)"
ST=$(dev_field "$DEV_Y" status); PROV_AT_2=$(dev_field "$DEV_Y" provisioned_at)
check "$( [[ "$ST" != "stale_config" && "$PROV_AT_2" > "$PROV_AT_1" ]]; echo $?)" \
  "4: qayta yuklashdan keyin stale_config emas ($ST), provisioned_at yangilandi" "$ST $PROV_AT_1 -> $PROV_AT_2"
OLD_R=$(phone y register t1-101 "$OLD_SECRET" asterisk 5060 5099)
check "$( [[ "$OLD_R" == "REGISTER 401" ]]; echo $?)" "4: eski parol bilan REGISTER -> 401" "$OLD_R"
RS=$(api POST "/devices/$DEV_F/resync")
check "$( err_is "$RS" 409 not_registered; echo $?)" "4: POST /resync ro'yxatda bo'lmagan apparatga (Fanvil) -> 409" "$RS"
RS=$(api POST "/devices/$DEV_Y/resync")
wait_until 10 log_has_n y "NOTIFY Event: check-sync" 2
check "$( [[ "$(jcode "$RS")" == "200" ]] && log_has_n y "NOTIFY Event: check-sync" 2; echo $?)" \
  "4: POST /resync ro'yxatdagi apparatga -> 200 + NOTIFY" "$RS"

# ---------------------------------------------------------------- 5. validatsiya
echo "=== 5. validatsiya ==="
R=$(api POST /devices "{\"mac\":\"80:5E:C0:A4:00:01\",\"vendor\":\"yealink\",\"model\":\"T46S\",\"extension_id\":\"${EXT_ID[105]}\"}")
check "$( err_is "$R" 409 mac_taken; echo $?)" "5: MAC dublikat (boshqa yozuv shaklida) -> 409 mac_taken" "$R"
R=$(api POST /devices "{\"mac\":\"805ec0a400a3\",\"vendor\":\"yealink\",\"model\":\"T46S\",\"extension_id\":\"${EXT_ID[103]}\"}")
check "$( err_is "$R" 422 extension_webrtc; echo $?)" "5: webrtc raqamga (103) -> 422 extension_webrtc" "$R"
MC_CODES=""
for i in 1 2 3 4; do
  R=$(api POST /devices "{\"mac\":\"0c383ea4f00$i\",\"vendor\":\"fanvil\",\"model\":\"X4U\",\"extension_id\":\"${EXT_ID[104]}\"}")
  MC_CODES+="$(jcode "$R") "
done
check "$( [[ "$MC_CODES" == "201 201 201 422 " ]] && err_is "$R" 422 max_contacts; echo $?)" \
  "5: max_contacts (3) dan ortiq -> 422 max_contacts" "$MC_CODES $R"
R=$(api PUT "/devices/$DEV_Y/keys" '{"keys":[{"idx":1,"type":"blf","value":"999"}]}')
check "$( err_is "$R" 422 unknown_extension; echo $?)" "5: BLF noma'lum raqam -> 422" "$R"
R=$(api PATCH "/devices/$DEV_Y" "{\"updated_at\":\"$(dev_field "$DEV_Y" updated_at)\",\"label\":\"a\nb\"}")
check "$( [[ "$(jcode "$R")" == "422" ]]; echo $?)" "5: label'da \\n -> 422" "$R"
R=$(api PUT "/devices/$DEV_Y/keys" '{"keys":[{"idx":1,"type":"blf","value":"102","label":"x\r\nlinekey.9.type = 16"}]}')
check "$( [[ "$(jcode "$R")" == "422" ]]; echo $?)" "5: tugma label'ida CR/LF -> 422" "$R"
R=$(api PATCH /settings/provisioning "{\"updated_at\":\"$(updated_at_of /settings/provisioning)\",\"extra\":{\"yealink\":\"bu noto'g'ri qator\"}}")
check "$( err_is "$R" 422 validation_error && [[ "$(jget "$(jbody "$R")" error field)" == "extra.yealink" ]]; echo $?)" \
  "5: extra noto'g'ri qator -> 422 (field extra.yealink)" "$R"
R=$(api POST /devices "{\"mac\":\"805ec0a400a4\",\"vendor\":\"yealink\",\"model\":\"X999\",\"extension_id\":\"${EXT_ID[105]}\"}")
check "$( err_is "$R" 422 unsupported_model; echo $?)" "5: noma'lum model -> 422 unsupported_model" "$R"
R=$(api POST /devices "{\"mac\":\"zz5ec0a400a4\",\"vendor\":\"yealink\",\"model\":\"T46S\",\"extension_id\":\"${EXT_ID[105]}\"}")
check "$( err_is "$R" 422 invalid_mac; echo $?)" "5: noto'g'ri MAC -> 422 invalid_mac" "$R"

# ---------------------------------------------------------------- 1 (davomi). sirlar hech qayerda ochiq emas
echo "=== 1. sirlar jurnal/audit/config'da yo'q ==="
CFG=$(jbody "$(api GET "/devices/$DEV_Y/config")")
CONTENT=$(jget "$CFG" content)
check "$( [[ "$CONTENT" == *"account.1.password = ***"* && "$CONTENT" == *"admin:***"* && "$CONTENT" != *"$NEW_SECRET"* \
  && "$CONTENT" != *"$ADMIN_PROV_PW"* && "$(jget "$CFG" filename)" == "${FILE[y]}" ]]; echo $?)" \
  "1: GET /devices/{id}/config -> parollar ***" "$CFG"
LEAK_LOG=$(sql "select count(*) from provision_requests where path like '%$TOKEN%' or path like '%$BAD_TOKEN%'
  or coalesce(user_agent,'') like '%$NEW_SECRET%'")
check "$( [[ "$LEAK_LOG" == "0" && "$(sql "select count(*) from provision_requests where path like '/prov/***/%'")" -gt 20 ]]; echo $?)" \
  "1: provision_requests: token/parol yo'q (yo'l /prov/***/...)" "$LEAK_LOG"
LEAK_AUDIT=$(sql "select count(*) from audit_log where diff::text like '%$NEW_SECRET%' or diff::text like '%$OLD_SECRET%'
  or diff::text like '%$ADMIN_PROV_PW%' or diff::text like '%$TOKEN%'")
AUD_N=$(sql "select count(*) from audit_log where action in ('create','update','delete') and entity in ('device','settings')")
check "$( [[ "$LEAK_AUDIT" == "0" && "$AUD_N" -ge 4 ]]; echo $?)" "1: audit_log: parol/token yo'q ($AUD_N device/settings yozuvi)" "$LEAK_AUDIT"

# ---------------------------------------------------------------- 6. token almashtirish / operator
echo "=== 6. token almashtirish / operator ==="
OLD_TOKEN=$TOKEN
TJ=$(jbody "$(api POST /settings/provisioning/rotate-token '{}')")
TOKEN=$(python3 -c "import json,sys;print(json.load(sys.stdin)['url'].rstrip('/').rsplit('/',1)[1])" <<<"$TJ")
C_OLD=$(prov f "${FILE[f]}" "$OLD_TOKEN"); C_NEW=$(prov f "${FILE[f]}")
check "$( [[ "$TOKEN" != "$OLD_TOKEN" && ${#TOKEN} == 32 && "$C_OLD" == "404" && "$C_NEW" == "200" ]]; echo $?)" \
  "6: rotate-token -> eski URL 404, yangi URL 200" "$C_OLD $C_NEW"
UJ=$(api POST /users "{\"username\":\"m4a_op\",\"full_name\":\"M4a Op\",\"role\":\"operator\",\"extension_id\":\"${EXT_ID[102]}\",\"password\":\"M4aTmp!2026x\"}")
t=$(login_as m4a_op 'M4aTmp!2026x')
api_as "$t" POST /auth/change-password "{\"current\":\"M4aTmp!2026x\",\"new\":\"$OP_PW\"}" >/dev/null
OP_TOKEN=$(login_as m4a_op "$OP_PW")
C1=$(jcode "$(api_as "$OP_TOKEN" GET /devices)"); C2=$(jcode "$(api_as "$OP_TOKEN" GET /settings/provisioning)")
check "$( [[ "$(jcode "$UJ")" == "201" && "$C1" == "403" && "$C2" == "403" ]]; echo $?)" \
  "6: operator -> /devices 403, /settings/provisioning 403" "$C1 $C2"

echo
echo "=== NATIJA: $PASS PASS / $FAIL FAIL ==="
[[ "$FAIL" == "0" ]]
