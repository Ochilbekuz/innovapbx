#!/usr/bin/env bash
# Innova PBX — M9 Bo'lak B isboti (replica/m9-freepbx-gaps-contract.md Bo'lak B):
#   B1. PIN to'plamlari: /pin-sets CRUD + PIN qo'shish/o'chirish + chiquvchi
#       marshrutga biriktirish + /internal/outbound-routes/{id}/pin-set-check
#       (dialplan CURL() aynan shu HTTP so'rovni yuboradi — bu yerda to'g'ridan-to'g'ri
#       curl bilan takrorlanadi: xato PIN -> "0", to'g'ri PIN -> "1:<label>").
#   B2. Telefon kitobi + CID Lookup manbalari: /phonebook CRUD + CSV import/eksport,
#       /cid-sources CRUD + /test, /internal/cid-lookup (xuddi B1 kabi — dialplan
#       CURL() so'rovi to'g'ridan-to'g'ri).
#   B3. Kiruvchi marshrut: cid_name_prefix/alert_info/cid_lookup_source_id maydonlari
#       API orqali saqlanadi/qaytariladi (dialplan satrlari — compiler.py, A agent
#       ishi, bu yerda qayta tekshirilmaydi — dryer).
#   B4. Ichki raqamlar CSV: /extensions/export.csv + /extensions/import.
#
# CHEKLOV: bu skript faqat HTTP API darajasida isbotlaydi (SIPp YO'Q) — B1/B2'ning
# ichki endpoint'lari AYNAN Asterisk dialplan `CURL()` chaqiradigan HTTP so'rov
# bo'lgani uchun, ularni to'g'ridan-to'g'ri curl bilan chaqirish ham haqiqiy
# integratsiya isboti hisoblanadi (faqat Asterisk INVITE/DTMF bosqichi
# simulyatsiya qilinmaydi — buni alohida SIPp ssenariysi bilan kengaytirish
# mumkin, qolgan M1b/M6 proof'lardagi qolipga o'xshash).
#
# Foydalanish:
#   scripts/m9b-proof.sh            # joriy `innova-m0` stackka qarshi
#   scripts/m9b-proof.sh --fresh    # avval build + up -d (migratsiya 0032 shu bilan qo'llanadi)
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"
LIB_DIR="$ROOT_DIR/scripts/lib"
API_BASE="${API_BASE:-http://127.0.0.1:8710/api/v1}"
API_ROOT="${API_BASE%/api/v1}"
PROJECT="innova-m0"
PG="innova-m0-postgres-1"   # m2a_common.sh sql()/wait_for_sql() shu konteynerga tegadi
AST="innova-m0-asterisk-1"  # m2a_common.sh ast() shu konteynerga tegadi

source "$LIB_DIR/m2a_common.sh"  # wait_for_sql(), ast(), sql()
source "$LIB_DIR/m3b_common.sh"   # err_is()

ADMIN_PASSWORD="${PROOF_ADMIN_PASSWORD:-$(grep -E '^PROOF_ADMIN_PASSWORD=' "$DEPLOY_DIR/.env" 2>/dev/null | cut -d= -f2-)}"
INTERNAL_TOKEN="${INTERNAL_API_TOKEN:-$(grep -E '^INTERNAL_API_TOKEN=' "$DEPLOY_DIR/.env" 2>/dev/null | cut -d= -f2-)}"
[[ -n "$ADMIN_PASSWORD" ]] || { echo "PROOF_ADMIN_PASSWORD deploy/.env da yo'q"; exit 2; }
[[ -n "$INTERNAL_TOKEN" ]] || { echo "INTERNAL_API_TOKEN deploy/.env da yo'q"; exit 2; }

if [[ "${1:-}" == "--fresh" ]]; then
  echo "--- --fresh: stack qayta quriladi (migratsiya 0032 shu bilan qo'llanadi) ---"
  (cd "$DEPLOY_DIR" && docker compose -p "$PROJECT" build) || { fail "docker compose build"; exit 1; }
  (cd "$DEPLOY_DIR" && docker compose -p "$PROJECT" up -d) || { fail "docker compose up"; exit 1; }
  wait_api
fi

echo "=== setup/login (admin) ==="
login "$ADMIN_PASSWORD" || { fail "login"; exit 1; }

# Skript idempotent bo'lishi SHART (stack umumiy, `--fresh` ISHLATILMAYDI) —
# oldingi (muvaffaqiyatsiz tugagan yoki shunchaki qayta ishga tushirilgan)
# yurgizishdan qolgan M9b* resurslarni, FK bog'liqligini hisobga olib
# (marshrutlar -> pin to'plami/trunk/cid manba, inbound -> cid manba),
# TARTIB BILAN tozalaymiz: avval bog'liqlar, keyin asoslar (m9a-proof.sh'dagi
# `del_ids` bilan bir xil qolip).
del_by() { # path field prefix [list_query]
  # `/phonebook`/`/extensions` sahifalangan (`Paged`, sukut `page_size=50`) —
  # katta sinov ma'lumotlari orasida nishon chetda qolib ketmasin, SERVER
  # tomonidagi `?q=` filtrini ishlatamiz (ikkisi ham qo'llaydi).
  local path="$1" field="$2" prefix="$3" query="${4:-}" id
  for id in $(jbody "$(api GET "$path$query")" | python3 -c "
import json,sys
d=json.load(sys.stdin)
for i in d.get('items', []):
    if str(i.get('$field', '')).startswith('$prefix'):
        print(i['id'])
" 2>/dev/null); do
    api DELETE "$path/$id" >/dev/null 2>&1 || true
  done
}
del_by /outbound-routes name M9b
del_by /inbound-routes name M9b
del_by /pin-sets name M9b
del_by /trunks name M9b
del_by /cid-sources name M9b
del_by /phonebook name "Ali Valiyev" "?q=Ali%20Valiyev"
del_by /phonebook name "Vali Boyev" "?q=Vali%20Boyev"
del_by /extensions number 9201 "?q=9201"
del_by /extensions number 9150 "?q=9150"

echo "=== B1: PIN to'plamlari ==="
PS_JSON=$(api POST /pin-sets '{"name":"M9bPinSet","record_in_cdr":true}')
check "$( [[ "$(jcode "$PS_JSON")" == "201" ]]; echo $?)" "POST /pin-sets -> 201" "$PS_JSON"
PS_ID=$(jget "$(jbody "$PS_JSON")" id)  # PinSetOut o'ralmagan (item YO'Q)

ADD_PINS_JSON=$(api POST "/pin-sets/$PS_ID/pins" '{"pins":[{"pin":"4455","label":"mehmon"}]}')
check "$( [[ "$(jcode "$ADD_PINS_JSON")" == "201" ]]; echo $?)" "POST /pin-sets/{id}/pins -> 201" "$ADD_PINS_JSON"

DUP_PIN_JSON=$(api POST "/pin-sets/$PS_ID/pins" '{"pins":[{"pin":"4455","label":"dublikat"}]}')
check "$(err_is "$DUP_PIN_JSON" 409 pin_taken; echo $?)" "takror PIN -> 409 pin_taken" "$DUP_PIN_JSON"

TRUNK_JSON=$(api POST /trunks '{"name":"M9bTrunk","host":"172.21.0.199","port":5060,"match":["172.21.0.199/32"],"codecs":["ulaw"],"max_channels":2,"enabled":true}')
TRUNK_ID=$(jget "$(jbody "$TRUNK_JSON")" item id)
[[ -n "$TRUNK_ID" ]] && pass "POST /trunks -> M9bTrunk yaratildi" || fail "POST /trunks -> $TRUNK_JSON"
# DIQQAT (jonli isbotda topilgan): `ip` rejimdagi trunk yangi realtime AOR
# qatori sifatida DARHOL o'qiladi (Dial() vaqtida), LEKIN Asterisk'ning
# ichki qualify-rejalashtiruvchisi YANGI obyektni faqat `pjsip reload`dan
# keyin tanib oladi (xuddi `register` rejim uchun `app/services/live_status.py`
# `reload_pjsip()`da yozilgan sababga o'xshash) — reload bo'lmasa, AOR ko'pincha
# "NonQual" holida qolib, quyidagi qualify/retry sikli INVITE'ni hech qachon
# yetkazolmaydi. Bu FAQAT shu isbot skriptining o'zi (production trunks.py
# `ip` rejimda reload yubormaydi, chunki oddiy Dial() aslida reload shart
# emas) uchun qo'shilgan — yangi AOR'ni qualify-rejalashtiruvchiga ro'yxatdan
# o'tkazish uchun.
docker exec "$AST" asterisk -rx "pjsip reload" >/dev/null 2>&1 || true
sleep 0.5  # reload CLI'dan qaytgach obyektlarning haqiqatan qayta yuklanishi uchun qisqa bo'shliq

# DIQQAT (jonli isbotda topilgan haqiqiy ildiz sabab): naqsh ILGARI
# "9XXXXXXXXX" (10 raqam) edi, PIN_DIALED ham 10 raqamli edi. Stekda doimiy
# qoladigan M1bUZRoute (m1b-proof.sh yaratadi, hech qachon tozalanmaydi,
# ustunligi ancha yuqori) OLDIDAN 1 ta raqamni kesib tashlaydi va qolgan
# ANIQ 9 raqamni o'ziga mos deb oladi (`strip_prefix` uzunligi=1,
# naqsh="XXXXXXXXX") -- ya'ni U HAR QANDAY 10 xonali raqamni "yutib
# yuboradi", M9bRoute'ga YETIB BORMAY turib M1b o'z trunklariga (ular bu
# sinovda tinglovchisiz) Dial qiladi va Congestion bilan tugaydi. Haqiqiy
# PIN-to'plam logikasi hech qachon ishga tushmaydi. Yechim: naqsh/raqam
# uzunligini 12 xonaga (literal "900" prefiks + 9 X) kengaytirish -- shunda
# M1bUZRoute 1 ta belgi kesgandan keyin 11 raqam qoladi, uning "aniq 9
# raqam" qoidasiga (^[0-9]{9}$) mos kelmaydi, M6Route/M1bRGRoute/
# M1bPinRoute'ning 10/12 xonali literal-prefiksli naqshlariga ham mos
# kelmaydi (pastda PIN_DIALED ham mos ravishda o'zgartirilgan).
ROUTE_JSON=$(api POST /outbound-routes "{\"name\":\"M9bRoute\",\"priority\":90,\"patterns\":[{\"pattern\":\"900XXXXXXXXX\"}],\"trunk_ids\":[\"$TRUNK_ID\"],\"pin_set_id\":\"$PS_ID\",\"international\":false}")
check "$( [[ "$(jcode "$ROUTE_JSON")" == "201" ]]; echo $?)" "POST /outbound-routes (pin_set_id) -> 201" "$ROUTE_JSON"
ROUTE_ID=$(jget "$(jbody "$ROUTE_JSON")" item id)

echo "--- /internal/outbound-routes/{id}/pin-set-check (dialplan CURL() yo'li) ---"
WRONG_RESP=$(curl -s "$API_ROOT/internal/outbound-routes/$ROUTE_ID/pin-set-check" \
  --data-urlencode "token=$INTERNAL_TOKEN" --data-urlencode "pin=0000" -G)
check "$( [[ "$WRONG_RESP" == "0" ]]; echo $?)" "xato PIN -> \"0\"" "$WRONG_RESP"

RIGHT_RESP=$(curl -s "$API_ROOT/internal/outbound-routes/$ROUTE_ID/pin-set-check" \
  --data-urlencode "token=$INTERNAL_TOKEN" --data-urlencode "pin=4455" -G)
check "$( [[ "$RIGHT_RESP" == "1:mehmon" ]]; echo $?)" "to'g'ri PIN -> \"1:mehmon\"" "$RIGHT_RESP"

BADTOK_RESP=$(curl -s "$API_ROOT/internal/outbound-routes/$ROUTE_ID/pin-set-check" \
  --data-urlencode "token=yomon" --data-urlencode "pin=4455" -G)
check "$( [[ "$BADTOK_RESP" == "0" ]]; echo $?)" "noto'g'ri token -> \"0\"" "$BADTOK_RESP"

echo "--- HAQIQIY SIP qo'ng'iroq: PIN to'plami bilan chiquvchi qo'ng'iroq ---"
# Yuqorida `/internal/.../pin-set-check` ni to'g'ridan-to'g'ri curl bilan
# chaqirish B1'ning HTTP qatlamini isbotladi; bu yerda esa HAQIQIY DTMF PIN
# bilan to'liq SIP qo'ng'iroq o'tkazib, `compiler.py`dagi
# `Set(CDR(pin_label)=...)` qatori ishlab, YAKUNDA `cdr.accountcode` (tenant
# kodi, O'ZGARMAGAN) VA `cdr.pin_label` (yangi, "mehmon") TO'G'RI to'lganini,
# hamda shu qo'ng'iroq `GET /calls`da ko'rinishini tasdiqlaymiz (SIPp qolipi —
# `scripts/m1b-proof.sh` ssenariy3 bilan BIR XIL, DRY, faqat shu skript
# mustaqil ishlashi uchun qisqa nusxa).
if ! command -v docker >/dev/null; then
  fail "docker topilmadi, PIN qo'ng'iroq SIP isboti o'tkazib yuborildi"
else
  SIPP_DIR="$ROOT_DIR/tests/sipp"
  NET="${PROJECT}_innova-net"
  SIPP_IMAGE="python:3.12-slim"
  CALL_EXT_IP="172.21.0.200"
  # DIQQAT: trunk-UAS IP yuqoridagi `TRUNK_JSON` (M9bTrunk) `host` qiymati
  # (172.21.0.199) BILAN AYNAN BIR XIL bo'lishi SHART — Asterisk
  # `from-trunk`ni shu IP orqali aniqlaydi.
  CALL_TRUNK_IP="172.21.0.199"
  CALL_SIP_CONTAINERS=(m9b-proof-ext m9b-proof-trunk)
  docker rm -f "${CALL_SIP_CONTAINERS[@]}" >/dev/null 2>&1 || true
  cleanup_m9b_sip() { docker rm -f "${CALL_SIP_CONTAINERS[@]}" >/dev/null 2>&1 || true; }
  trap cleanup_m9b_sip EXIT

  CALLEXT_JSON=$(api POST /extensions '{"number":"9150","name":"M9bCallExt"}')
  CALLEXT_SECRET=$(jget "$(jbody "$CALLEXT_JSON")" sip password)
  [[ -n "$CALLEXT_SECRET" ]] && pass "POST /extensions -> 9150 (PIN qo'ng'iroq uchun) yaratildi" \
    || fail "POST /extensions 9150 -> $CALLEXT_JSON"

  docker network inspect "$NET" >/dev/null 2>&1 || fail "tarmoq $NET topilmadi"
  docker run -d --name m9b-proof-ext --network "$NET" --ip "$CALL_EXT_IP" "$SIPP_IMAGE" sleep infinity >/dev/null
  docker run -d --name m9b-proof-trunk --network "$NET" --ip "$CALL_TRUNK_IP" "$SIPP_IMAGE" sleep infinity >/dev/null
  docker cp "$SIPP_DIR/outbound_invite.py" m9b-proof-ext:/tmp/outbound_invite.py
  docker cp "$SIPP_DIR/uas_log_and_answer.py" m9b-proof-trunk:/tmp/uas_log_and_answer.py

  start_uas() { # container script ip max_seconds (m1b-proof.sh'dagi bilan BIR XIL qolip)
    docker exec "$1" pkill -x python3 >/dev/null 2>&1 || true
    local waited=0
    while docker exec "$1" pgrep -x python3 >/dev/null 2>&1; do
      sleep 0.1; waited=$((waited + 1)); (( waited > 20 )) && break
    done
    docker exec -d "$1" sh -c "python3 -u /tmp/$2 $3 5060 $4 > /tmp/out.log 2>&1"
  }
  uas_log() { docker exec "$1" cat /tmp/out.log 2>/dev/null; }
  qualify_trunk() { docker exec "$AST" asterisk -rx "pjsip qualify t1-trunk-$1" >/dev/null 2>&1; }
  wait_for_aor_avail() { # trunk_id max_seconds
    local tries=$(( ${2:-3} * 10 )) i=0
    while (( i < tries )); do
      docker exec "$AST" asterisk -rx "pjsip show aor t1-trunk-$1" 2>/dev/null | grep -q "Avail" && return 0
      sleep 0.1; i=$((i + 1))
    done
    return 1
  }
  wait_for_uas_log() { # container pattern max_seconds
    local out="" i=0 tries=$(( ${3:-3} * 10 ))
    while (( i < tries )); do
      out=$(uas_log "$1")
      echo "$out" | grep -q "$2" && { echo "$out"; return 0; }
      sleep 0.1; i=$((i + 1))
    done
    echo "$out"
  }

  PIN_DIALED=900201112233  # M9bRoute pattern "900XXXXXXXXX" (12 raqam) bilan mos; M1bUZRoute to'qnashuvidan qochish uchun 12 xona (yuqoridagi izohga qarang)
  TRC_LOG=""; TRC_OUT=""
  for attempt in 1 2 3 4 5; do
    start_uas m9b-proof-trunk uas_log_and_answer.py "$CALL_TRUNK_IP" 10
    sleep 0.5
    qualify_trunk "$TRUNK_ID"
    # DIQQAT (jonli isbotda topilgan): AOR "NonQual"/"Unavailable" bo'lsa
    # chan_pjsip Dial()ni HECH QACHON simga chiqarmaydi (darhol 503/CONGESTION,
    # INVITE paketi umuman yuborilmaydi) — shu sabab `wait_for_aor_avail`
    # natijasi albatta tekshiriladi; "Avail" bo'lmasa HAQIQIY qo'ng'iroqni
    # urinib ko'rmasdan, to'g'ridan-to'g'ri keyingi urinishga o'tamiz (vaqt
    # tejash + yolg'on-NonQual holatida muvaffaqiyatsiz chaqiruv sonini kamaytirish).
    if ! wait_for_aor_avail "$TRUNK_ID" 5; then
      echo "PIN qo'ng'iroq: urinish $attempt -- AOR hali Avail emas, qayta urinamiz"
      continue
    fi
    TRC_OUT=$(docker exec m9b-proof-ext python3 /tmp/outbound_invite.py asterisk 5060 "$((5190 + attempt))" 9150 "$CALLEXT_SECRET" "$PIN_DIALED" --dtmf "4455#" --hold-ms 2000 --no-register 2>&1)
    TRC_LOG=$(wait_for_uas_log m9b-proof-trunk "REQUEST_LINE" 5)
    echo "$TRC_LOG" | grep -q "REQUEST_LINE" && break
    echo "PIN qo'ng'iroq: urinish $attempt muvaffaqiyatsiz (NonQual ehtimoli) -- qayta urinamiz"
  done
  if echo "$TRC_LOG" | grep -q "REQUEST_LINE"; then
    pass "PIN qo'ng'iroq: to'g'ri PIN (4455) bilan trunk M9bTrunk'ga INVITE bordi"
  else
    fail "PIN qo'ng'iroq: trunk'ga INVITE kelmadi"; echo "$TRC_LOG"; echo "$TRC_OUT"
  fi

  TENANT_CODE=$(wait_for_sql "select code from tenants limit 1" 2)
  CALL_CDR=$(wait_for_sql "select accountcode, pin_label, disposition from cdr where dst='$PIN_DIALED' order by calldate desc limit 1" 8)
  check "$( [[ "$CALL_CDR" == "$TENANT_CODE|mehmon|ANSWERED" ]]; echo $?)" \
    "CDR: accountcode=$TENANT_CODE (tenant kodi, o'zgarmagan) + pin_label=mehmon (yangi)" "$CALL_CDR"

  CALLS_LIST=$(api GET "/calls?q=$PIN_DIALED")
  CALLS_DST0=$(jget "$(jbody "$CALLS_LIST")" items 0 dst)
  check "$( [[ "$CALLS_DST0" == "$PIN_DIALED" ]]; echo $?)" \
    "GET /calls -> PIN qo'ng'iroq ko'rinadi (dst=$PIN_DIALED)" "$CALLS_LIST"
fi

echo "=== B2: Telefon kitobi + CID Lookup manbalari ==="
PB_JSON=$(api POST /phonebook '{"name":"Ali Valiyev","company":"Acme","numbers":[{"number":"998901234567","label":"ish"}]}')
check "$( [[ "$(jcode "$PB_JSON")" == "201" ]]; echo $?)" "POST /phonebook -> 201" "$PB_JSON"

# MUHIM: CSV standart (RFC 4180) bo'yicha CRLF ("\r\n") qator ajratgichi
# bilan qaytadi — `tr -d '\r'` bilan tozalamasak, pastdagi `grep -q "^...$"`
# (satr OXIRIDA $ langar) doim MOS KELMAYDI (haqiqiy ishlab chiqarish bug'i
# EMAS, faqat isbot-skript tekshiruvi uchun).
CSV_EXPORT=$(curl -s "${AUTH[@]}" "$API_BASE/phonebook/export.csv" | tr -d '\r')
check "$(echo "$CSV_EXPORT" | grep -q "^name,company,note,numbers$"; echo $?)" \
  "GET /phonebook/export.csv -> sarlavha to'g'ri" "$CSV_EXPORT"
check "$(echo "$CSV_EXPORT" | grep -q "Ali Valiyev,Acme,,998901234567:ish"; echo $?)" \
  "export.csv'da yangi kontakt bor" "$CSV_EXPORT"

IMPORT_CSV=$'name,company,note,numbers\nVali Boyev,,,998907654321\n'
IMPORT_RESP=$(curl -s -w '\n%{http_code}' -X POST "$API_BASE/phonebook/import" "${AUTH[@]}" \
  -F "dry_run=false" -F "file=@-;filename=pb.csv;type=text/csv" <<<"$IMPORT_CSV")
check "$( [[ "$(jcode "$IMPORT_RESP")" == "200" ]]; echo $?)" "POST /phonebook/import -> 200" "$IMPORT_RESP"
check "$( [[ "$(jget "$(jbody "$IMPORT_RESP")" created)" == "1" ]]; echo $?)" \
  "import: created=1" "$IMPORT_RESP"

CID_JSON=$(api POST /cid-sources '{"name":"M9bPhonebook","kind":"phonebook"}')
check "$( [[ "$(jcode "$CID_JSON")" == "201" ]]; echo $?)" "POST /cid-sources (phonebook) -> 201" "$CID_JSON"
CID_ID=$(jget "$(jbody "$CID_JSON")" id)  # CidSourceOut o'ralmagan (item YO'Q)

TEST_LOOKUP=$(api POST "/cid-sources/$CID_ID/test" '{"number":"998901234567"}')
check "$( [[ "$(jget "$(jbody "$TEST_LOOKUP")" name)" == "Ali Valiyev" ]]; echo $?)" \
  "POST /cid-sources/{id}/test -> topildi (Ali Valiyev)" "$TEST_LOOKUP"

echo "--- /internal/cid-lookup (dialplan CURL() yo'li) ---"
LOOKUP_RESP=$(curl -s "$API_ROOT/internal/cid-lookup" \
  --data-urlencode "token=$INTERNAL_TOKEN" --data-urlencode "source_id=$CID_ID" \
  --data-urlencode "num=998901234567" -G)
check "$( [[ "$LOOKUP_RESP" == "Ali Valiyev" ]]; echo $?)" \
  "/internal/cid-lookup -> \"Ali Valiyev\"" "$LOOKUP_RESP"

NOTFOUND_RESP=$(curl -s "$API_ROOT/internal/cid-lookup" \
  --data-urlencode "token=$INTERNAL_TOKEN" --data-urlencode "source_id=$CID_ID" \
  --data-urlencode "num=998900000000" -G)
check "$( [[ "$NOTFOUND_RESP" == "" ]]; echo $?)" "/internal/cid-lookup (topilmadi) -> bo'sh" "$NOTFOUND_RESP"

echo "=== B3: kiruvchi marshrut — cid_name_prefix/alert_info/cid_lookup_source_id ==="
HANGUP_TARGET=$(jget "$(jbody "$(api GET "/targets?kind=hangup")")" items 0 id)
IR_JSON=$(api POST /inbound-routes "{\"name\":\"M9bInbound\",\"did\":\"998900009999\",\"target_id\":\"$HANGUP_TARGET\",\"cid_name_prefix\":\"[Tashqi] \",\"alert_info\":\"Bellcore-dr2\",\"cid_lookup_source_id\":\"$CID_ID\"}")
check "$( [[ "$(jcode "$IR_JSON")" == "201" ]]; echo $?)" "POST /inbound-routes (B3 maydonlari) -> 201" "$IR_JSON"
IR_BODY=$(jbody "$IR_JSON")
check "$( [[ "$(jget "$IR_BODY" item alert_info)" == "Bellcore-dr2" ]]; echo $?)" \
  "inbound-route.alert_info saqlandi/qaytdi" "$IR_BODY"
check "$( [[ "$(jget "$IR_BODY" item cid_name_prefix)" == "[Tashqi] " ]]; echo $?)" \
  "inbound-route.cid_name_prefix saqlandi/qaytdi" "$IR_BODY"
check "$( [[ "$(jget "$IR_BODY" item cid_lookup_source id)" == "$CID_ID" ]]; echo $?)" \
  "inbound-route.cid_lookup_source biriktirildi" "$IR_BODY"

BAD_ALERT=$(api POST /inbound-routes "{\"name\":\"M9bBad\",\"did\":\"998900009998\",\"target_id\":\"$HANGUP_TARGET\",\"alert_info\":\"bad header\"}")
check "$(err_is "$BAD_ALERT" 422 validation_error; echo $?)" \
  "alert_info noto'g'ri formatda -> 422 validation_error" "$BAD_ALERT"

echo "=== B4: ichki raqamlar CSV import/eksport ==="
EXT_EXPORT=$(curl -s "${AUTH[@]}" "$API_BASE/extensions/export.csv" | tr -d '\r')
check "$(echo "$EXT_EXPORT" | grep -q "^number,name,email,outbound_cid,language,voicemail,record_in,record_out,max_contacts,call_waiting,enabled$"; echo $?)" \
  "GET /extensions/export.csv -> sarlavha to'g'ri" "$EXT_EXPORT"

EXT_CSV=$'number,name,email,outbound_cid,record_in,record_out,max_contacts,enabled\n9201,M9b Ext,,,,,,1\n'
EXT_IMPORT=$(curl -s -w '\n%{http_code}' -X POST "$API_BASE/extensions/import" "${AUTH[@]}" \
  -F "dry_run=false" -F "file=@-;filename=ext.csv;type=text/csv" <<<"$EXT_CSV")
check "$( [[ "$(jcode "$EXT_IMPORT")" == "200" ]]; echo $?)" "POST /extensions/import -> 200" "$EXT_IMPORT"
check "$( [[ "$(jget "$(jbody "$EXT_IMPORT")" created)" == "1" ]]; echo $?)" \
  "extensions import: created=1 (9201)" "$EXT_IMPORT"

EXT_EXPORT2=$(curl -s "${AUTH[@]}" "$API_BASE/extensions/export.csv" | tr -d '\r')
check "$(echo "$EXT_EXPORT2" | grep -q "^9201,M9b Ext,"; echo $?)" \
  "export.csv'da yangi ichki raqam (9201) bor" "$EXT_EXPORT2"

echo
echo "=== NATIJA: PASS=$PASS FAIL=$FAIL ==="
(( FAIL == 0 ))
