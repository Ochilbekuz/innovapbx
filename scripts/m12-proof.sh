#!/usr/bin/env bash
# Innova PBX — M12 Bo'lak A isboti (replica/m12-contract.md Bo'lak A1/A2 + L3):
#   A1. Kun/Tun rejimi (`day_night`): CRUD (`/api/v1/day-night`) + `POST /{id}/toggle`
#       (admin API, PIN'siz) + `*28<code>` telefon xizmat kodi (BLF hint
#       `Custom:DAYNIGHT<code>`) + dialplan holatni RELOAD'SIZ o'qiydi (ichki
#       CURL `/internal/day-night/{id}/state|/toggle`, fail-SAFE "day").
#   A2. DISA (`disa`): CRUD (`/api/v1/disa`) + PIN HMAC (`allow_no_pin=true`
#       bo'lmasa PIN SHART, 422) + dialplan PIN-urinish siklida fail-CLOSED
#       ichki CURL (`/internal/disa/{id}/pin-check`) + muvaffaqiyatdan keyin
#       FAQAT `{code}-outbound-rg`ga Goto (ichki xizmat kodlariga yo'l YO'Q).
#   L3.  Render vaqtida `CODE_RE.fullmatch` qayta tekshiruvi (`dialplan_features.py`
#       :: `feature_code_lines`) — DB'ga to'g'ridan-to'g'ri (API'ni chetlab o'tib)
#       yozilgan buzilgan `feature_codes.code` dialplan'ga YOZILMAYDI, log'ga
#       ogohlantirish yoziladi; tuzatilgach qayta compile bilan tiklanadi.
#   Sanitizatsiya: nom maydonida Asterisk maxsus belgilar (`${...}` ko'rinishi)
#       Pydantic (faqat boshqaruv belgilarini bloklaydi) orqali O'TADI, LEKIN
#       render vaqtida `sanitize_dialplan_text()` tomonidan olib tashlanadi
#       ("ikkinchi himoya qatlami" — `dialplan_safety.py`).
#
# Ataylab SODDALASHTIRISHLAR (m10a-proof.sh'dagi TTS izohi bilan BIR XIL ruh):
#   - Haqiqiy DTMF/SIPp orqali `Read()` siklidan PIN kiritish SINALMAYDI (juda
#     murakkab/mo'rt) — o'rniga dialplan CHAQIRADIGAN ICHKI endpoint'lar
#     (`/internal/day-night/*`, `/internal/disa/*`) TO'G'RIDAN-TO'G'RI chaqiriladi
#     (xuddi `CURL()` qiladigan so'rovning o'zi) + statik `ast dialplan show`
#     matn tekshiruvi — ikkisi birga PIN/fail-safe/fail-closed mantiqini real
#     DB qatorlari ustida isbotlaydi.
#   - Ikkinchi tenant yaratib tenant izolyatsiyasini QAYTA ISBOTLAMAYMIZ — bu
#     allaqachon backend unit testlarida qoplangan (`_get_or_404` tenant_id
#     filtri); shu yerda faqat eslatma sifatida qayd etiladi.
#   - `day_night.code` dublikat to'qnashuvi (API orqali 409 EMAS, DB UNIQUE
#     constraint'dan keladigan ishlov qilinmagan 500) ataylab SINALMAYDI —
#     oldindan mavjud, brief doirasidan tashqari backend bo'shlig'i, mo'rt/
#     noaniq xatolikni "o'tdi" deb belgilash xavfi bor.
#
# Foydalanish:
#   scripts/m12-proof.sh            # joriy `innova-m0` stackka qarshi (--fresh YO'Q)
#
# MUHIM: faqat `innova-m0` compose loyihasiga tegadi; `--fresh`/`down -v` ISHLATILMAYDI.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"
LIB_DIR="$ROOT_DIR/scripts/lib"
API_BASE="${API_BASE:-http://127.0.0.1:8710/api/v1}"
API_ROOT="${API_BASE%/api/v1}"
PG=innova-m0-postgres-1
AST=innova-m0-asterisk-1
API_CTR=innova-m0-api-1

source "$LIB_DIR/m2a_common.sh"
source "$LIB_DIR/m3b_common.sh"

ADMIN_PASSWORD="${PROOF_ADMIN_PASSWORD:-$(grep -E '^PROOF_ADMIN_PASSWORD=' "$DEPLOY_DIR/.env" | cut -d= -f2-)}"
[[ -n "$ADMIN_PASSWORD" ]] || { echo "PROOF_ADMIN_PASSWORD deploy/.env da yo'q"; exit 2; }
INTERNAL_TOKEN=$(grep -E '^INTERNAL_API_TOKEN=' "$DEPLOY_DIR/.env" | cut -d= -f2-)
[[ -n "$INTERNAL_TOKEN" ]] || { echo "INTERNAL_API_TOKEN deploy/.env da yo'q"; exit 2; }

# `apply_config`/`_reload_and_verify` (apply.py) faqat `{tenant}-from-trunk`
# kontekst MAVJUDLIGINI tekshiradi (AMI "dialplan reload" javob qaytargach) —
# boshqa kontekstlar (`-from-internal`, `-dest-*`) HAM shu reload bilan birga
# qayta yoziladi, LEKIN Asterisk CLI'ning "dialplan show" buyrug'i reload
# tugagandan keyin HAM ba'zan bir lahzalik eski matnni qaytarishi kuzatildi
# (AMI javobi qaytgandan keyin ichki parser/hint registratsiyasi hali davom
# etayotganda) — shu sabab ICHKI KONTEKST matnini kutib SINAB qaraydigan kichik
# qayta urinish (`wait_for_sql` BILAN BIR XIL ruh, faqat `ast()` ustida).
# Bundan tashqari, bu stackda PARALLEL ishlayotgan boshqa agentlar (M12 B/C)
# HAM xuddi shu tenant uchun apply_config/reload chaqirishi mumkin — bitta
# o'tkazib yuborilgan reload oynasi kutilgan (`tries`/`delay` shu sabab
# saxiy: 16 x 1s = ~16s).
ast_wait() { # ctx pattern max_tries delay_s -> stdout: oxirgi "ast dialplan show <ctx>" natijasi
  local ctx="$1" pattern="$2" tries="${3:-24}" delay="${4:-1}" out="" i=0
  while (( i < tries )); do
    out=$(ast "dialplan show $ctx")
    echo "$out" | grep -q -- "$pattern" && break
    sleep "$delay"
    i=$((i + 1))
  done
  echo "$out"
}

echo "=== setup/login ==="
login "$ADMIN_PASSWORD" || { fail "login"; exit 1; }

echo "=== oldingi M12 qoldiqlarini tozalash (bo'lsa) ==="
del_ids() { # path prefix -> `name` shu prefiks bilan boshlanganlarni DELETE qiladi
  local path="$1" prefix="$2" id
  for id in $(jbody "$(api GET "$path")" | python3 -c "
import json,sys
d=json.load(sys.stdin)
for i in d.get('items', []):
    if str(i.get('name', '')).startswith('$prefix'):
        print(i['id'])
" 2>/dev/null); do
    api DELETE "$path/$id" >/dev/null 2>&1 || true
  done
}
del_ids /inbound-routes M12
del_ids /day-night M12
del_ids /disa M12

# `day_night`/`disa`ning OWN `target_id` (CallTarget id — nom bo'yicha `/targets?q=`
# orqali EMAS, to'g'ridan-to'g'ri jadvaldan — nomda Asterisk maxsus belgilar bo'lsa
# `endswith()`/URL query orqali qidirish mo'rt bo'lardi, SQL esa aniq va sodda).
day_night_target_id() { sql "select target_id from day_night where id='$1'"; }
disa_target_id() { sql "select target_id from disa where id='$1'"; }

echo "=== A1: hangup/busy psevdo-nishonlarini topish (kun/tun uchun tayyor, qo'shimcha sozlash kerak emas) ==="
TARGETS_HB=$(jbody "$(api GET "/targets?kind=hangup,busy")")
HANGUP_ID=$(python3 -c "
import json,sys
d=json.load(sys.stdin)
items=[i for i in d['items'] if i['kind']=='hangup']
print(items[0]['id'] if items else '')
" <<<"$TARGETS_HB")
BUSY_ID=$(python3 -c "
import json,sys
d=json.load(sys.stdin)
items=[i for i in d['items'] if i['kind']=='busy']
print(items[0]['id'] if items else '')
" <<<"$TARGETS_HB")
check "$( [[ -n "$HANGUP_ID" && -n "$BUSY_ID" ]]; echo $?)" "A1: hangup/busy psevdo-nishonlar topildi"

echo "=== A1: Kun/Tun CRUD ==="
DN_RESP=$(api POST /day-night "{\"name\":\"M12DayNight\",\"code\":\"7\",\"day_target_id\":\"$HANGUP_ID\",\"night_target_id\":\"$BUSY_ID\",\"pin\":\"2468\"}")
check "$([[ "$(jcode "$DN_RESP")" == "201" ]]; echo $?)" "A1: POST /day-night -> 201" "$DN_RESP"
DN_BODY=$(jbody "$DN_RESP")
DN_ID=$(jget "$DN_BODY" item id)
DN_UPDATED_AT=$(jget "$DN_BODY" item updated_at)
check "$([[ "$(jget "$DN_BODY" item has_pin)" == "True" ]]; echo $?)" "A1: has_pin=true, PIN o'zi javobda yo'q"
check "$(echo "$DN_BODY" | grep -q '"pin"'; [[ $? -ne 0 ]]; echo $?)" "A1: javobda 'pin' kaliti umuman yo'q"

BAD_TARGET=$(api POST /day-night "{\"name\":\"M12DayNightBad\",\"code\":\"8\",\"day_target_id\":\"00000000-0000-0000-0000-000000000000\",\"night_target_id\":\"$BUSY_ID\"}")
check "$(err_is "$BAD_TARGET" 422 invalid_target; echo $?)" "A1: noto'g'ri day_target_id -> 422 invalid_target" "$BAD_TARGET"

echo "=== A1: POST /{id}/toggle (admin API, PIN'siz) ==="
TOGGLE1=$(api POST "/day-night/$DN_ID/toggle" "")
check "$([[ "$(jcode "$TOGGLE1")" == "200" && "$(jget "$(jbody "$TOGGLE1")" item mode)" == "night" ]]; echo $?)" "A1: toggle -> night" "$TOGGLE1"
TOGGLE2=$(api POST "/day-night/$DN_ID/toggle" "")
check "$([[ "$(jget "$(jbody "$TOGGLE2")" item mode)" == "day" ]]; echo $?)" "A1: qayta toggle -> day" "$TOGGLE2"

echo "=== A1: dialplan — t1-dest-<target_id> (kun/tun marshrutlash) ==="
DN_TARGET_ID=$(day_night_target_id "$DN_ID")
# `t1-dest-<target_id>` konteksti FAQAT shu target_id biror joyda MANZIL sifatida
# ko'rsatilsa compile qilinadi (`_all_dest_ids()` — `time_condition`/`ivr` BILAN
# BIR XIL qolip: "destination" bo'lgan target_id'lar, "satellite"ning o'zi EMAS).
# Shu sabab sinov uchun bitta kiruvchi marshrutni ushbu kun/tun qoidasiga yo'naltiramiz.
DN_WIRE=$(api POST /inbound-routes "{\"name\":\"M12DnWire\",\"did\":\"998712200071\",\"target_id\":\"$DN_TARGET_ID\"}")
check "$([[ "$(jcode "$DN_WIRE")" == "201" ]]; echo $?)" "A1: kun/tun qoidasini kiruvchi marshrutga ulash" "$DN_WIRE"
DN_DEST=$(ast "dialplan show t1-dest-$DN_TARGET_ID")
check "$(echo "$DN_DEST" | grep -q 'NoOp(Innova: kun/tun M12DayNight)'; echo $?)" "A1 dialplan: NoOp nom ko'rsatiladi"
check "$(echo "$DN_DEST" | grep -q 'CURL(.*internal/day-night/'"$DN_ID"'/state'; echo $?)" "A1 dialplan: holatni ICHKI CURL bilan o'qiydi (reload shart emas)"
check "$(echo "$DN_DEST" | grep -q 'night'; echo $?)" "A1 dialplan: tun yo'nalishi label mavjud"

echo "=== A1: dialplan — t1-from-internal (*28<code> xizmat kodi + BLF hint) ==="
FROM_INTERNAL=$(ast_wait "t1-from-internal" 'DEVICE_STATE(Custom:DAYNIGHT7)')
check "$(echo "$FROM_INTERNAL" | grep -q '\*287.*hint.*Custom:DAYNIGHT7'; echo $?)" "A1 dialplan: *287 uchun BLF hint Custom:DAYNIGHT7"
check "$(echo "$FROM_INTERNAL" | grep -q 'CURL(.*internal/day-night/'"$DN_ID"'/toggle'; echo $?)" "A1 dialplan: *287 ichki toggle CURL'ni chaqiradi"
check "$(echo "$FROM_INTERNAL" | grep -q 'DEVICE_STATE(Custom:DAYNIGHT7)'; echo $?)" "A1 dialplan: DEVICE_STATE(Custom:DAYNIGHT7) yangilanadi"

echo "=== A1: *287 ni jonli chaqirish (PIN bor -> Read so'raydi, biz PIN yubormaymiz -> xato yo'li) va ICHKI endpoint orqali toggle (dialplan CURL qiladigan XUDDI SHU so'rov) ==="
STATE_BEFORE=$(curl -s "$API_ROOT/internal/day-night/$DN_ID/state?token=$INTERNAL_TOKEN")
check "$([[ "$STATE_BEFORE" == "day" ]]; echo $?)" "A1 ichki: /state joriy holat (day)"
STATE_BAD_TOKEN=$(curl -s "$API_ROOT/internal/day-night/$DN_ID/state?token=yomon")
check "$([[ "$STATE_BAD_TOKEN" == "day" ]]; echo $?)" "A1 ichki: /state xato token -> fail-SAFE 'day' (marshrutlash to'xtamaydi)"
TOGGLE_BAD_PIN=$(curl -s "$API_ROOT/internal/day-night/$DN_ID/toggle?token=$INTERNAL_TOKEN&pin=0000")
check "$([[ "$TOGGLE_BAD_PIN" == "0" ]]; echo $?)" "A1 ichki: /toggle xato PIN -> '0' (rad etildi)" "$TOGGLE_BAD_PIN"
TOGGLE_OK_PIN=$(curl -s "$API_ROOT/internal/day-night/$DN_ID/toggle?token=$INTERNAL_TOKEN&pin=2468")
check "$([[ "$TOGGLE_OK_PIN" == "night" ]]; echo $?)" "A1 ichki: /toggle to'g'ri PIN -> 'night'"
curl -s "$API_ROOT/internal/day-night/$DN_ID/toggle?token=$INTERNAL_TOKEN&pin=2468" >/dev/null  # day'ga qaytarish

echo "=== A2: DISA — PIN/allow_no_pin qoidasi ==="
DISA_NO_PIN=$(api POST /disa "{\"name\":\"M12DisaNoPin\",\"allow_no_pin\":false}")
check "$(err_is "$DISA_NO_PIN" 422 validation_error; echo $?)" "A2: PIN yo'q + allow_no_pin=false -> 422 validation_error" "$DISA_NO_PIN"

DISA_ALLOW=$(api POST /disa "{\"name\":\"M12DisaAllow\",\"allow_no_pin\":true,\"max_attempts\":3}")
check "$([[ "$(jcode "$DISA_ALLOW")" == "201" && "$(jget "$(jbody "$DISA_ALLOW")" item has_pin)" == "False" ]]; echo $?)" "A2: allow_no_pin=true + PIN yo'q -> 201 has_pin=false" "$DISA_ALLOW"
DISA_ALLOW_ID=$(jget "$(jbody "$DISA_ALLOW")" item id)

DISA_PIN=$(api POST /disa "{\"name\":\"M12DisaPin\",\"pin\":\"1357\",\"max_attempts\":3,\"cid_override\":\"998712223344\"}")
check "$([[ "$(jcode "$DISA_PIN")" == "201" && "$(jget "$(jbody "$DISA_PIN")" item has_pin)" == "True" ]]; echo $?)" "A2: PIN bilan -> 201 has_pin=true" "$DISA_PIN"
check "$(echo "$(jbody "$DISA_PIN")" | grep -q '"pin"'; [[ $? -ne 0 ]]; echo $?)" "A2: javobda 'pin' kaliti umuman yo'q"
DISA_PIN_ID=$(jget "$(jbody "$DISA_PIN")" item id)
DISA_PIN_UPDATED_AT=$(jget "$(jbody "$DISA_PIN")" item updated_at)

UPDATE_STRIP_PIN=$(api PATCH "/disa/$DISA_PIN_ID" "{\"pin_clear\":true,\"updated_at\":\"$DISA_PIN_UPDATED_AT\"}")
check "$([[ "$(jcode "$UPDATE_STRIP_PIN")" == "422" ]]; echo $?)" "A2: PIN tozalash (allow_no_pin=false holda) -> 422 pin_required" "$UPDATE_STRIP_PIN"

echo "=== A2: dialplan — t1-dest-<target_id> (DISA PIN sikli + faqat outbound-rg) ==="
DISA_TARGET_ID=$(disa_target_id "$DISA_PIN_ID")
DISA_WIRE=$(api POST /inbound-routes "{\"name\":\"M12DisaWire\",\"did\":\"998712200072\",\"target_id\":\"$DISA_TARGET_ID\"}")
check "$([[ "$(jcode "$DISA_WIRE")" == "201" ]]; echo $?)" "A2: DISA'ni kiruvchi marshrutga ulash" "$DISA_WIRE"
DISA_DEST=$(ast "dialplan show t1-dest-$DISA_TARGET_ID")
check "$(echo "$DISA_DEST" | grep -q 'NoOp(Innova: DISA M12DisaPin)'; echo $?)" "A2 dialplan: NoOp nom ko'rsatiladi"
check "$(echo "$DISA_DEST" | grep -q 'Answer()'; echo $?)" "A2 dialplan: Answer() bor"
check "$(echo "$DISA_DEST" | grep -q 'CURL(.*internal/disa/'"$DISA_PIN_ID"'/pin-check'; echo $?)" "A2 dialplan: ichki pin-check CURL chaqiriladi"
check "$(echo "$DISA_DEST" | grep -qi 'INNOVA_DISA_TRY'; echo $?)" "A2 dialplan: urinish hisoblagichi (max_attempts bilan qoyoslash) bor"
check "$(echo "$DISA_DEST" | grep -q 'Hangup()'; echo $?)" "A2 dialplan: urinishlar tugagach Hangup() bor"
check "$(echo "$DISA_DEST" | grep -q 't1-outbound-rg'; echo $?)" "A2 dialplan: muvaffaqiyatdan keyin FAQAT t1-outbound-rg'ga Goto"
check "$(echo "$DISA_DEST" | grep -q 'from-internal'; [[ $? -ne 0 ]]; echo $?)" "A2 dialplan: ichki xizmat kodlariga (-from-internal) YO'L YO'Q"
check "$(echo "$DISA_DEST" | grep -q 'CALLERID(num)=998712223344'; echo $?)" "A2 dialplan: cid_override to'g'ri qo'llanadi"

echo "=== A2: ichki /pin-check endpoint'ini jonli chaqirish (dialplan CURL qiladigan XUDDI SHU so'rov) ==="
PIN_BAD_TOKEN=$(curl -s "$API_ROOT/internal/disa/$DISA_PIN_ID/pin-check?token=yomon&pin=1357")
check "$([[ "$PIN_BAD_TOKEN" == "0" ]]; echo $?)" "A2 ichki: xato token -> '0' (fail-CLOSED)"
PIN_WRONG=$(curl -s "$API_ROOT/internal/disa/$DISA_PIN_ID/pin-check?token=$INTERNAL_TOKEN&pin=0000")
check "$([[ "$PIN_WRONG" == "0" ]]; echo $?)" "A2 ichki: xato PIN -> '0'" "$PIN_WRONG"
SEC_EVT=$(sql "select count(*) from security_events where kind='disa_pin_fail' and (details->>'disa_id')='$DISA_PIN_ID'")
check "$([[ "$SEC_EVT" -ge 1 ]]; echo $?)" "A2: xato PIN uchun security_events(kind=disa_pin_fail) yozildi"
PIN_OK=$(curl -s "$API_ROOT/internal/disa/$DISA_PIN_ID/pin-check?token=$INTERNAL_TOKEN&pin=1357")
check "$([[ "$PIN_OK" == "1" ]]; echo $?)" "A2 ichki: to'g'ri PIN -> '1'"
ALLOW_OK=$(curl -s "$API_ROOT/internal/disa/$DISA_ALLOW_ID/pin-check?token=$INTERNAL_TOKEN&pin=")
check "$([[ "$ALLOW_OK" == "1" ]]; echo $?)" "A2 ichki: allow_no_pin=true + PIN yo'q -> '1' (ruxsat)"

echo "=== Sanitizatsiya: Asterisk maxsus belgilar Pydantic'dan O'TADI, render vaqtida OLIB TASHLANADI ==="
INJECT_NAME='M12Inj${SHELL(touch /tmp/pwned)}'
INJECT_RESP=$(api POST /day-night "{\"name\":\"$INJECT_NAME\",\"code\":\"9\",\"day_target_id\":\"$HANGUP_ID\",\"night_target_id\":\"$BUSY_ID\"}")
check "$([[ "$(jcode "$INJECT_RESP")" == "201" ]]; echo $?)" "sanitizatsiya: \${...} nomli yozuv Pydantic validatsiyasidan O'TADI (201)" "$INJECT_RESP"
INJECT_ID=$(jget "$(jbody "$INJECT_RESP")" item id)
INJECT_TARGET_ID=$(day_night_target_id "$INJECT_ID")
INJECT_WIRE=$(api POST /inbound-routes "{\"name\":\"M12InjWire\",\"did\":\"998712200073\",\"target_id\":\"$INJECT_TARGET_ID\"}")
check "$([[ "$(jcode "$INJECT_WIRE")" == "201" ]]; echo $?)" "sanitizatsiya: inj yozuvini kiruvchi marshrutga ulash"
INJECT_DEST=$(ast "dialplan show t1-dest-$INJECT_TARGET_ID")
check "$(echo "$INJECT_DEST" | grep -q '\${SHELL('; [[ $? -ne 0 ]]; echo $?)" "sanitizatsiya: render vaqtida '\${SHELL(' YO'Q (sanitize_dialplan_text olib tashladi)"
check "$(echo "$INJECT_DEST" | grep -q 'M12Inj'; echo $?)" "sanitizatsiya: xavfsiz qism (M12Inj) qolgan"

echo "=== L3: render vaqtida CODE_RE qayta tekshiruvi (API'ni chetlab o'tib DB'ga to'g'ridan-to'g'ri yozilgan buzilgan kod) ==="
T1_TENANT=$(sql "select id from tenants where code='t1'")
ORIG_VM_OTHER_CODE=$(sql "select code from feature_codes where tenant_id='$T1_TENANT' and feature='voicemail_other'")
# `feature_codes.code` ustida ALLAQACHON DB CHECK bor (`feature_codes_code_check`,
# aynan shu CODE_RE shakli bilan) — "*98X" kabi qiymat ODDIY UPDATE orqali
# kirmaydi (0035'dan OLDIN ham mavjud, M12 doirasidan tashqari). L3'ni jonli
# isbotlash uchun CHECK'ni VAQTINCHA olib tashlaymiz (eski/zaxiradan tiklangan
# ma'lumot CHECK'siz bo'lishi mumkin degan stsenariyni simulyatsiya qiladi),
# buzilgan qatorni yozamiz, tekshiramiz, ASL qiymatga qaytaramiz, SO'NGRA CHECK'ni
# qayta qo'shamiz (shu tartibda — aks holda ADD CONSTRAINT buzilgan qatorda xato beradi).
sql "alter table feature_codes drop constraint if exists feature_codes_code_check" >/dev/null
sql "update feature_codes set code='*98X' where tenant_id='$T1_TENANT' and feature='voicemail_other'" >/dev/null
# recompile'ni ishga tushirish uchun zararsiz mutatsiya (apply_config har CRUD'dan keyin chaqiriladi;
# DN_ID shu skript oxirida o'chiriladi, mode flip'ning o'zi muhim emas — faqat recompile kerak).
api POST "/day-night/$DN_ID/toggle" "" >/dev/null
FROM_INTERNAL_BAD=$(ast "dialplan show t1-from-internal")
check "$(echo "$FROM_INTERNAL_BAD" | grep -q '\*98X'; [[ $? -ne 0 ]]; echo $?)" "L3: buzilgan kod (*98X) dialplan'ga YOZILMAGAN"
check "$(docker logs "$API_CTR" 2>&1 | tail -n 400 | grep -q "feature_code_lines: noto'g'ri kod"; echo $?)" "L3: API logiga ogohlantirish yozilgan"
# tiklash: avval ASL qiymat, SO'NGRA CHECK qaytariladi
sql "update feature_codes set code='$ORIG_VM_OTHER_CODE' where tenant_id='$T1_TENANT' and feature='voicemail_other'" >/dev/null
sql "alter table feature_codes add constraint feature_codes_code_check check (code ~ '^\*[0-9*#]{1,6}\$')" >/dev/null
api POST "/day-night/$DN_ID/toggle" "" >/dev/null
FROM_INTERNAL_FIXED=$(ast_wait "t1-from-internal" "${ORIG_VM_OTHER_CODE//\*/\\*}")
check "$(echo "$FROM_INTERNAL_FIXED" | grep -q "${ORIG_VM_OTHER_CODE//\*/\\*}"; echo $?)" "L3: tiklangach original kod ($ORIG_VM_OTHER_CODE) dialplan'da qayta mavjud"

echo "=== Audit jurnali ==="
# ESLATMA: `app/services/audit.py::normalize_action()` DB'ga yozishdan OLDIN
# "<entity>.<fe'l>" shaklni m1b-contract.md bo'lim 6'dagi 8 umumiy fe'lga
# tushiradi ("day_night.create" -> "create", "day_night.toggle" -> "update"
# fallback, chunki "toggle" ro'yxatda/aliasda yo'q) — `entity` ustunida ANIQ
# "day_night"/"disa" saqlanadi, shu sabab filtr `entity` bo'yicha, tekshiruv
# NORMALLASHGAN fe'l bo'yicha.
AUDIT_DN=$(jbody "$(api GET "/audit?entity=day_night&size=100")")
check "$(python3 -c "
import json,sys
d=json.load(sys.stdin)
actions={i['action'] for i in d['items'] if i.get('entity_id') in ('$DN_ID','$INJECT_ID')}
print(0 if {'create','update'} <= actions else 1)
" <<<"$AUDIT_DN")" "audit: day_night (create+toggle->update) yozilgan"
AUDIT_DISA=$(jbody "$(api GET "/audit?entity=disa&size=100")")
check "$(python3 -c "
import json,sys
d=json.load(sys.stdin)
actions={i['action'] for i in d['items'] if i.get('entity_id')=='$DISA_PIN_ID'}
print(0 if 'create' in actions else 1)
" <<<"$AUDIT_DISA")" "audit: disa.create yozilgan"

echo "=== Tenant izolyatsiyasi (eslatma) ==="
echo "    Tenant izolyatsiyasi (day_night._get_or_404/disa._get_or_404 tenant_id filtri) jonli ikkinchi"
echo "    tenant yaratib QAYTA ISBOTLANMADI — backend unit testlarida (test_day_night_routes_unit.py,"
echo "    test_disa_routes_unit.py) allaqachon qoplangan, risk/murakkablik sabab shu yerda takrorlanmadi."

echo "=== tozalash ==="
api DELETE "/day-night/$DN_ID" >/dev/null 2>&1
api DELETE "/day-night/$INJECT_ID" >/dev/null 2>&1
api DELETE "/disa/$DISA_ALLOW_ID" >/dev/null 2>&1
api DELETE "/disa/$DISA_PIN_ID" >/dev/null 2>&1

echo "=== YAKUN: PASS=$PASS FAIL=$FAIL ==="
[[ $FAIL -eq 0 ]]
