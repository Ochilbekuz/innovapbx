#!/usr/bin/env bash
# Innova PBX — M10 Bo'lak A isboti (replica/m10-onlinepbx-contract.md Bo'lak A):
#   A1. Qayta chaqirish vidjeti: admin API (vidjet CRUD, kalit aylantirish) + ommaviy
#       endpoint'lar (/widget/{key}.js, /api/public/widget/{key}/config|callback) —
#       404 (o'chirilgan/noma'lum), Origin ruxsati 403, honeypot, tezlik cheklovi,
#       telefon formati 422, xalqaro bloklash 422, qora ro'yxat, dublikat himoyasi —
#       so'ngra fon dialer AMI Originate qiladi: operator (201) javob beradi ->
#       mijoz (trunk) teriladi -> ikkisi ham javob -> so'rov "connected".
#   A2. O'tkazib yuborilgan qo'ng'iroq: qoida (Telegram) -> /test endpoint sinov
#       xabari soxta Telegram serverga yetadi; parol/token audit'da "***".
#   A3. TTS (Yandex SpeechKit): /settings/tts konfiguratsiyasi (API kalit shifrlangan,
#       GET javobida yo'q), sozlanmagan -> 409 tts_not_configured, sozlangan (lekin
#       bu proof muhitida haqiqiy Yandex yo'q) -> 502 tts_failed, javobda kalit
#       SIZMAYDI. (Haqiqiy LPCM muvaffaqiyat yo'li — soxta `httpx` transport bilan
#       `tests/test_m10a_unit.py::test_synthesize_lpcm_success_with_fake_transport`
#       da isbotlangan — bu live-proof muhitida haqiqiy Yandex kalit/karta yo'q,
#       ataylab soddalashtirish, pastda ham qayd etiladi.)
#
# Foydalanish:
#   scripts/m10a-proof.sh            # joriy `innova-m0` stackka qarshi
#   scripts/m10a-proof.sh --fresh    # avval `docker compose down -v` + qayta build + up -d
#
# MUHIM: faqat `innova-m0` compose loyihasiga tegadi; o'z konteynerlarini (m10a-proof-*) oxirida o'chiradi.
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

# .234/.235/.236 — `docker network inspect innova-m0_innova-net` bilan bo'sh ekani
# tasdiqlangan (boshqa proof skriptlari .233 gacha ishlatadi).
declare -A IP=([268]="172.21.0.234" [trunk]="172.21.0.235" [tg]="172.21.0.236")
OPERATOR_NUM="268"            # 101-104/201-203/221-223 boshqa proof'larning doimiy
                              # qoldiq fixturalari bilan to'qnashmasin (M2a/M9a/M3b/M6)
#   DIQQAT: haqiqiy "rate-limit" bloklanishning aybdori IP limiteri (60s oyna) EMAS
# edi — public_widget.py'da ALOHIDA `phone:{dialed}` limiteri bor
# (PHONE_LIMIT_PER_HOUR=3, window_s=3600, BIR XIL umumiy "Juda ko'p so'rov..."
# xabari bilan). Qotgan CUSTOMER_NUM bu skriptning HAR BIR qayta ishga tushirilishida
# (--fresh'siz, bir soat ichida bir nechta marta) bitta telefon bucket'ini to'ldirib
# qo'yardi -> 60s/75s kutish befoyda edi (oyna 1 SOAT). Fix: raqamni har safar
# noyob qilish (vaqt tamg'asi bilan) — 998 + 9 raqam = outbound 998XXXXXXXXX bilan mos.
CUSTOMER_NUM="998$(printf '%09d' $(( $(date +%s) % 1000000000 )))"  # har ishga tushirishda noyob

FOREIGN_NUM="+1234567890"     # "998" bilan boshlanmaydi -> xalqaro bloklash
BLACK_NUM="998900099001"

source "$LIB_DIR/m2a_common.sh"
source "$LIB_DIR/m3b_common.sh"   # http_code(), PUBLIC_BASE (shu skriptda ishlatilmaydi, lekin umumiy)

ADMIN_PASSWORD="${PROOF_ADMIN_PASSWORD:-$(grep -E '^PROOF_ADMIN_PASSWORD=' "$DEPLOY_DIR/.env" | cut -d= -f2-)}"
[[ -n "$ADMIN_PASSWORD" ]] || { echo "PROOF_ADMIN_PASSWORD deploy/.env da yo'q"; exit 2; }

CONTAINERS=(m10a-proof-268 m10a-proof-trunk m10a-proof-tg)
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

# A1 ommaviy callback'da IP bo'yicha tezlik cheklovi (5/daq) API JARAYONI
# ICHIDA xotirada (`services/rate_limit.py` — jarayon qayta ishga tushmaguncha
# nolga tushmaydi). `--fresh`siz BIR XIL hostdan (shu skript) ketma-ket
# ishga tushirilsa oldingi urinishning hitlari hali oynada qolib, "to'g'ri
# raqam"/"dublikat" tekshiruvlarini YOLG'ON "rate_limited" bilan yiqitadi —
# mahsulot xatosi EMAS (haqiqiy mijoz ham shunday cheklanardi). Belgi vaqti
# haqiqiy hit'lar boshlanadigan joyga (honeypot bo'limi, pastda) ko'chirilgan —
# shu yerda faqat o'qiymiz, 75 s hoshiya (60 s oyna + ishlov vaqti marjasi).
RATE_WINDOW_S=75
LAST_RUN_FILE="/tmp/.m10a-proof-last-run"
if [[ -f "$LAST_RUN_FILE" ]]; then
  ELAPSED=$(( $(date +%s) - $(cat "$LAST_RUN_FILE") ))
  if (( ELAPSED < RATE_WINDOW_S )); then
    echo "oldingi ishga tushirishdan $ELAPSED s o'tdi -> IP tezlik oynasi tozalanishi uchun $((RATE_WINDOW_S - ELAPSED)) s kutish"
    sleep $((RATE_WINDOW_S - ELAPSED))
  fi
fi

# Stek umumiy (M10 Bo'lak B/C bilan parallel) — `--fresh` har doim ishlatilavermaydi,
# shu sabab skript o'zi idempotent: oldingi (muvaffaqiyatsiz tugagan) M10a* qoldiqlarini
# avval o'chiradi (m9a-proof.sh'dagi BILAN BIR XIL qolip). Tartib MUHIM: avval
# `callback-widgets` (ext -> `call_targets` FK RESTRICT) va `missed-call-rules`/
# `outbound-routes`, SO'NGRA `trunks`/`extensions`.
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
echo "=== oldingi M10a qoldiqlarini tozalash (bo'lsa) ==="
del_ids /callback-widgets M10a
del_ids /missed-call-rules M10a
del_ids /outbound-routes M10a
del_ids /trunks M10a
del_ids /extensions M10a

# `tts_settings` — tenant bo'yicha YAGONA qator (M10a-prefiksli resurs emas,
# `del_ids()` uni tozalay olmaydi). A3'ning birinchi tekshiruvi "sozlanmagan ->
# 409" holatini talab qiladi — oldingi (shu skriptning o'zidan qolgan) ishga
# tushirishda `provider=yandex` bo'lib qolgan bo'lsa, qayta "none"ga tushiramiz.
TTS_CUR=$(jbody "$(api GET /settings/tts)")
if [[ "$(jget "$TTS_CUR" provider)" != "none" ]]; then
  TTS_CUR_UPDATED_AT=$(jget "$TTS_CUR" updated_at)
  api PATCH /settings/tts "{\"provider\":\"none\",\"api_key\":\"\",\"updated_at\":\"$TTS_CUR_UPDATED_AT\"}" >/dev/null
fi

target_id_by_kind_name() { # kind name -> call_targets id
  # DIQQAT: `label` = "{raqam} · {nom}" (extensions.py: CallTarget(label=f"{number} · {name}")),
  # shu sabab ANIQ TENGLIK emas — `label` nomi bilan TUGASHI (endswith) tekshiriladi.
  local kind="$1" name="$2"
  local r; r=$(curl -s "$API_BASE/targets?kind=$kind&q=$name" "${AUTH[@]}")
  python3 -c "
import json,sys
d=json.load(sys.stdin)
items=[i for i in d['items'] if i['label'].endswith('$name')]
print(items[0]['id'] if items else '')
" <<<"$r"
}

echo "=== resurslar: operator + trunk ==="
EXT_JSON=$(jbody "$(api POST /extensions "{\"number\":\"$OPERATOR_NUM\",\"name\":\"M10aOperator\"}")")
EXT_ID=$(jget "$EXT_JSON" item id); SECRET=$(jget "$EXT_JSON" sip password)
OPERATOR_TARGET=$(target_id_by_kind_name extension M10aOperator)
TRUNK_ID=$(jget "$(jbody "$(api POST /trunks "{\"name\":\"M10aTrunk\",\"host\":\"${IP[trunk]}\",\"port\":5060,\"match\":[\"${IP[trunk]}/32\"],\"codecs\":[\"ulaw\"],\"max_channels\":5,\"enabled\":true}")")" item id)
ROUTE=$(api POST /outbound-routes "{\"name\":\"M10aRoute\",\"priority\":1,\"patterns\":[{\"pattern\":\"998XXXXXXXXX\"}],\"trunk_ids\":[\"$TRUNK_ID\"],\"international\":false}")
check "$( [[ -n "$EXT_ID" && -n "$OPERATOR_TARGET" && -n "$TRUNK_ID" && "$(jcode "$ROUTE")" == "201" ]]; echo $?)" \
  "A1 setup: 201 + nishon + trunk + marshrut 998XXXXXXXXX" "$ROUTE"
check "$(ast "dialplan show t1-callback-dial" | grep -q "hangup_handler_push"; ast "dialplan show t1-callback-answer" | grep -q "Goto(t1-outbound-rg"; echo $?)" \
  "A1: Asterisk: t1-callback-dial/-answer kontekstlari yuklangan"

echo "=== telefonlar (operator + trunk) ==="
for c in 268 trunk; do
  docker run -d --name "m10a-proof-$c" --network "$NET" --ip "${IP[$c]}" "$PY_IMAGE" sleep infinity >/dev/null
  # `m2a_phone.py` -> `vm_caller.py` -> `outbound_invite.py` import qiladi
  # (m9a-proof.sh BILAN BIR XIL qolip) — faqat birinchisini ko'chirish
  # ModuleNotFoundError bilan jarayonni darhol yiqitadi (REGISTER urinilmaydi).
  for f in outbound_invite.py vm_caller.py m2a_phone.py; do
    docker cp "$SIPP_DIR/$f" "m10a-proof-$c:/tmp/$f"
  done
done
docker exec m10a-proof-268 sh -c "echo answer > /tmp/mode"
docker exec -d m10a-proof-268 sh -c "cd /tmp && python3 m2a_phone.py serve $OPERATOR_NUM '$SECRET' 5070 12000 /tmp/mode 900 > /tmp/phone.log 2>&1"
docker exec m10a-proof-trunk sh -c "echo answer > /tmp/mode"
docker exec -d m10a-proof-trunk sh -c "cd /tmp && python3 m2a_phone.py serve trunk - 5060 12000 /tmp/mode 900 > /tmp/phone.log 2>&1"
registered() { docker exec m10a-proof-268 grep -q 'REGISTER_RESULT: OK' /tmp/phone.log 2>/dev/null; }
wait_until 15 registered || fail "$OPERATOR_NUM ro'yxatdan o'tmadi"
# DIQQAT: SIPp REGISTER 200 OK qaytarishi hali Asterisk uni "Reachable" deb
# BILISHINI anglatmaydi — AOR'ning `qualify_frequency=60` OPTIONS so'rovi
# REGISTER'dan DARHOL EMAS, Asterisk'ning o'z ichki jadvali (grid) bo'yicha
# 0-60 s kechikib yuboriladi; shu oraliqda kontakt holati "Unknown"/"Unavail"
# qolishi mumkin, VA shu holatda `Dial(PJSIP/268,...)` "Could not create
# dialog to invalid URI '268'" bilan DARHOL yiqiladi (qo'lda tasdiqlangan:
# `pjsip show aor 268` ikkala kontakt ham Unavail bo'lganida aniq xato
# takrorlandi). Fon dialer (2s siklda) so'rovni REGISTER'dan ko'p o'tmay
# ushlab olishi mumkin — shu sabab OK1/mijoz so'rovini yaratishdan OLDIN
# "Reachable" bo'lguncha kutish SHART (mahsulot xatosi EMAS — Asterisk/PJSIP
# qualify grid'ining tabiiy xususiyati; haqiqiy foydalanishda operator
# telefoni ancha oldin ro'yxatdan o'tgan bo'ladi).
# DIQQAT: `pjsip show aor` jadvalida holat ustuni "Avail"/"Unavail" (qisqa)
# ko'rinishda, "Reachable" so'zi FAQAT asterisk logidagi voqea xabarida
# ("Endpoint ... is now Reachable") chiqadi — CLI jadvalida YO'Q. Avval
# noto'g'ri "Reachable" so'zini qidirib har doim 65s to'liq kutib FAIL
# berardi (keyingi bosqichlar baribir o'tgan — chunki ular yetarlicha
# kechikish bilan ishladi). "Avail" so'zi "Unavail"da UCHRAMAYDI (katta "A"
# faqat "Avail" holatida, "Unavail"da kichik "a") — xavfsiz ajratish.
aor_reachable() { ast "pjsip show aor $OPERATOR_NUM" | grep -q "Avail"; }
wait_until 65 aor_reachable || fail "$OPERATOR_NUM qualify (Avail) bo'lmadi"

echo "=== A1: admin API — vidjet CRUD ==="
# retry_interval_s >= 60 shart (schema `ge=60`) — bu proof faqat 1-urinishni
# tekshiradi (operator darhol javob beradi), shu sabab son ahamiyatsiz, sukut (120) yetarli.
W_JSON=$(jbody "$(api POST /callback-widgets "{\"name\":\"M10aWidget\",\"target_id\":\"$OPERATOR_TARGET\",\"allowed_origins\":[\"https://good.example\"],\"offhours_mode\":\"reject\",\"max_attempts\":2,\"allow_international\":false}")")
W_CODE=$(jcode "$(api GET /callback-widgets)")
WIDGET_ID=$(jget "$W_JSON" item id)
PUBLIC_KEY=$(jget "$W_JSON" item public_key)
check "$( [[ -n "$WIDGET_ID" && -n "$PUBLIC_KEY" && "$(jget "$W_JSON" apply status)" == "applied" ]]; echo $?)" \
  "A1: POST /callback-widgets -> 201, public_key, apply=applied" "$W_JSON"

ROTATE=$(jbody "$(api POST "/callback-widgets/$WIDGET_ID/rotate-key" '{}')")
OLD_KEY="$PUBLIC_KEY"
PUBLIC_KEY=$(jget "$ROTATE" item public_key)
check "$( [[ -n "$PUBLIC_KEY" && "$PUBLIC_KEY" != "$OLD_KEY" ]]; echo $?)" "A1: rotate-key -> yangi public_key" "$ROTATE"
OLD_KEY_CODE=$(http_code "$API_ROOT/widget/$OLD_KEY.js")
check "$( [[ "$OLD_KEY_CODE" == "404" ]]; echo $?)" \
  "A1: eski kalit bilan /widget/*.js -> 404 (kalit aylantirilgan)" "code=$OLD_KEY_CODE"

echo "=== A1: ommaviy endpoint — skript/konfiguratsiya ==="
UNKNOWN_KEY_CODE=$(http_code "$API_ROOT/widget/yoq-bunday-kalit.js")
check "$( [[ "$UNKNOWN_KEY_CODE" == "404" ]]; echo $?)" "A1: noma'lum kalit -> 404" "code=$UNKNOWN_KEY_CODE"
JS=$(curl -s "$API_ROOT/widget/$PUBLIC_KEY.js")
check "$(grep -q "innova-callback-widget" <<<"$JS"; echo $?)" "A1: /widget/{key}.js -> JS tanasi (innova-callback-widget)"

CFG_OK=$(curl -s -w '\n%{http_code}' "$API_ROOT/api/public/widget/$PUBLIC_KEY/config")
check "$( [[ "$(jcode "$CFG_OK")" == "200" && "$(jget "$(jbody "$CFG_OK")" name)" == "M10aWidget" ]]; echo $?)" \
  "A1: GET config (Origin'siz) -> 200, name" "$CFG_OK"
CFG_BAD_ORIGIN=$(curl -s -w '\n%{http_code}' -H 'Origin: https://evil.example' "$API_ROOT/api/public/widget/$PUBLIC_KEY/config")
check "$(err_is "$CFG_BAD_ORIGIN" 403 origin_not_allowed; echo $?)" "A1: GET config (yot Origin) -> 403 origin_not_allowed" "$CFG_BAD_ORIGIN"
CFG_GOOD_ORIGIN=$(curl -s -w '\n%{http_code}' -H 'Origin: https://good.example' "$API_ROOT/api/public/widget/$PUBLIC_KEY/config")
check "$( [[ "$(jcode "$CFG_GOOD_ORIGIN")" == "200" ]]; echo $?)" "A1: GET config (ruxsatli Origin) -> 200"

api PATCH "/callback-widgets/$WIDGET_ID" "{\"enabled\":false,\"updated_at\":\"$(jget "$ROTATE" item updated_at)\"}" >/dev/null
DISABLED_CODE=$(http_code "$API_ROOT/api/public/widget/$PUBLIC_KEY/config")
check "$( [[ "$DISABLED_CODE" == "404" ]]; echo $?)" "A1: o'chirilgan vidjet -> config 404" "code=$DISABLED_CODE"
RE_ENABLE=$(jbody "$(api GET "/callback-widgets")")
ENABLED_UPDATED_AT=$(python3 -c "import json,sys;d=json.load(sys.stdin);print([i for i in d['items'] if i['id']=='$WIDGET_ID'][0]['updated_at'])" <<<"$RE_ENABLE")
api PATCH "/callback-widgets/$WIDGET_ID" "{\"enabled\":true,\"updated_at\":\"$ENABLED_UPDATED_AT\"}" >/dev/null

date +%s > "$LAST_RUN_FILE"   # IP tezlik oynasi shu yerdan boshlab hisoblanadi (keyingi ishga tushirish uchun)
echo "=== A1: ommaviy endpoint — callback qabul qilish, xavfsizlik qatlamlari ==="
cb() { curl -s -w '\n%{http_code}' -H 'Content-Type: application/json' -H 'Origin: https://good.example' \
  -X POST "$API_ROOT/api/public/widget/$PUBLIC_KEY/callback" -d "$1"; }

HP=$(cb "{\"phone\":\"998901234599\",\"hp\":\"bot\"}")
check "$( [[ "$(jcode "$HP")" == "200" && "$(jget "$(jbody "$HP")" accepted)" == "True" ]]; echo $?)" \
  "A1: honeypot to'lgan -> 200 accepted=true (botga signal yo'q)" "$HP"
check "$( [[ "$(sql "select count(*) from callback_requests where phone='998901234599'")" == "0" ]]; echo $?)" \
  "A1: honeypot -> yozuv YARATILMAGAN"

BAD_ORIGIN_CB=$(curl -s -w '\n%{http_code}' -H 'Content-Type: application/json' -H 'Origin: https://evil.example' \
  -X POST "$API_ROOT/api/public/widget/$PUBLIC_KEY/callback" -d '{"phone":"998901234567"}')
check "$(err_is "$BAD_ORIGIN_CB" 403 origin_not_allowed; echo $?)" "A1: callback (yot Origin) -> 403" "$BAD_ORIGIN_CB"

BAD_PHONE=$(cb '{"phone":"xyz"}')
check "$(err_is "$BAD_PHONE" 422 invalid_number; echo $?)" "A1: telefon formati noto'g'ri -> 422 invalid_number" "$BAD_PHONE"

FOREIGN=$(cb "{\"phone\":\"$FOREIGN_NUM\"}")
check "$(err_is "$FOREIGN" 422 international_blocked; echo $?)" "A1: xalqaro raqam (allow_international=false) -> 422" "$FOREIGN"

api POST /blacklist "{\"number\":\"$BLACK_NUM\",\"reason\":\"m10a\"}" >/dev/null
BLACKED=$(cb "{\"phone\":\"$BLACK_NUM\"}")
check "$( [[ "$(jcode "$BLACKED")" == "200" && "$(jget "$(jbody "$BLACKED")" accepted)" == "False" ]]; echo $?)" \
  "A1: qora ro'yxatdagi raqam -> 200 accepted=false" "$BLACKED"
check "$( [[ "$(sql "select count(*) from callback_requests where phone='$BLACK_NUM'")" == "0" ]]; echo $?)" \
  "A1: qora ro'yxat -> yozuv YARATILMAGAN"

OK1=$(cb "{\"phone\":\"$CUSTOMER_NUM\"}")
check "$( [[ "$(jcode "$OK1")" == "200" && "$(jget "$(jbody "$OK1")" accepted)" == "True" ]]; echo $?)" \
  "A1: to'g'ri raqam -> 200 accepted=true" "$OK1"
DUP=$(cb "{\"phone\":\"$CUSTOMER_NUM\"}")
check "$( [[ "$(jcode "$DUP")" == "200" && "$(jget "$(jbody "$DUP")" message)" == *"navbatdasiz"* ]]; echo $?)" \
  "A1: dublikat (hali pending) -> 'siz allaqachon navbatdasiz'" "$DUP"
check "$( [[ "$(sql "select count(*) from callback_requests where phone='$CUSTOMER_NUM'")" == "1" ]]; echo $?)" \
  "A1: dublikat -> faqat 1 yozuv"

echo "=== A1: tezlik cheklovi (IP, 5/min) ==="
for i in 1 2 3 4; do cb "{\"phone\":\"99890123450$i\"}" >/dev/null; done
RATE=$(cb '{"phone":"998901234510"}')
check "$( [[ "$(jcode "$RATE")" == "200" && "$(jget "$(jbody "$RATE")" accepted)" == "False" ]]; echo $?)" \
  "A1: IP tezlik chegarasidan oshdi -> accepted=false" "$RATE"

echo "=== A1: fon dialer — ikki bosqichli terish (operator -> mijoz) ==="
# `bash -c "..."` YANGI subshell ochadi — mahalliy `sql()` funksiyasi unga
# EKSPORT qilinmagan (`export -f` yo'q), shu sabab to'g'ridan-to'g'ri funksiya
# sifatida berish kerak (`registered()`/`tg_ready()` BILAN BIR XIL qolip).
dial_connected() { [[ "$(sql "select status from callback_requests where phone='$CUSTOMER_NUM'")" == "connected" ]]; }
# DIQQAT (test xatosi, mahsulot EMAS): `status` FAQAT mijoz tomoni (ikkinchi
# bosqich) HANGUP HANDLER'i (`t1-callback-custhang` -> record_customer_result())
# ishga tushganda "connected" ga o'zgaradi — ya'ni qo'ng'iroq haqiqatan
# TUGASHI (BYE) kerak, javob berilgan/bridge bo'lgani YETARLI EMAS.
# `m2a_phone.py serve` (UAS) rejimi — ikkala oyoq (operator 268 HAM, trunk HAM)
# — faqat kiruvchi INVITE'ga javob beradi va keyin O'ZI HECH QACHON BYE
# YUBORMAYDI (faqat masofadan BYE kelsa javob qaytaradi) — docstring/kodda
# tasdiqlangan ("UAS (`serve`) ... `REQ BYE`" faqat QABUL qilishni logga
# yozadi, BYE jo'natish YO'Q). Shu sabab haqiqiy mijoz/operator "gapini
# tugatib telefonni qo'yishi"ni BU SKRIPT o'zi simulyatsiya qilishi kerak —
# boshqa proof skriptlarida (m1b/m3a/m3b/m6-proof.sh) ALLAQACHON ishlatilgan
# "channel request hangup all" qolipi bilan (butun stekda shu paytda faqat
# shu qo'ng'iroq bor, chunki fon dialer yangi so'rov yaratmaguncha kutamiz).
both_answered() {
  docker exec m10a-proof-268 grep -q ANSWERED /tmp/phone.log 2>/dev/null \
    && docker exec m10a-proof-trunk grep -q ANSWERED /tmp/phone.log 2>/dev/null
}
wait_until 20 both_answered || fail "A1: operator/trunk hali javob bermadi (hangup oldidan)"
ast "channel request hangup all" >/dev/null
wait_until 20 dial_connected
FINAL_STATUS=$(sql "select status from callback_requests where phone='$CUSTOMER_NUM'")
LINKEDID=$(sql "select linkedid from callback_requests where phone='$CUSTOMER_NUM'")
check "$( [[ "$FINAL_STATUS" == "connected" && -n "$LINKEDID" ]]; echo $?)" \
  "A1: callback_requests.status -> connected, linkedid yozilgan" "status=$FINAL_STATUS linkedid=$LINKEDID"
check "$(docker exec m10a-proof-268 grep -q ANSWERED /tmp/phone.log; echo $?)" "A1: operator ($OPERATOR_NUM) INVITE oldi va javob berdi"
check "$(docker exec m10a-proof-trunk grep -q ANSWERED /tmp/phone.log; echo $?)" "A1: mijoz (trunk) INVITE oldi va javob berdi (2-bosqich)"

echo "=== A1: callback-requests ro'yxati (apps:read) ==="
LIST=$(jbody "$(api GET "/callback-requests?widget_id=$WIDGET_ID")")
check "$( [[ "$(jget "$LIST" total)" -ge 1 ]]; echo $?)" "A1: GET /callback-requests -> items" "$LIST"

echo "=== A2: o'tkazib yuborilgan qo'ng'iroq bildirishnomasi ==="
docker run -d --name m10a-proof-tg --network "$NET" --ip "${IP[tg]}" "$PY_IMAGE" sleep infinity >/dev/null
docker cp "$SIPP_DIR/fake_telegram.py" m10a-proof-tg:/tmp/fake_telegram.py
docker exec -d m10a-proof-tg python3 /tmp/fake_telegram.py 0.0.0.0 8081 /tmp/tg.log
tg_ready() { docker exec m10a-proof-tg python3 -c \
  "import socket; socket.create_connection(('127.0.0.1', 8081), 1).close()" 2>/dev/null; }
wait_until 10 tg_ready || fail "soxta Telegram server 8081'da tinglamadi"
TG_TOKEN="123456:M10aProofToken"
NS=$(api PATCH /settings/notify "{\"telegram_token\":\"$TG_TOKEN\",\"telegram_api_base\":\"http://${IP[tg]}:8081\"}")
check "$( [[ "$(jcode "$NS")" == "200" ]]; echo $?)" "A2: PATCH /settings/notify (telegram) -> 200" "$NS"

MR_JSON=$(jbody "$(api POST /missed-call-rules "{\"name\":\"M10aMissedRule\",\"scope_kind\":\"any\",\"telegram_chat_ids\":[\"4242\"],\"enabled\":true}")")
RULE_ID=$(jget "$MR_JSON" item id)
check "$( [[ -n "$RULE_ID" ]]; echo $?)" "A2: POST /missed-call-rules -> 201" "$MR_JSON"

TEST=$(api POST "/missed-call-rules/$RULE_ID/test" '{}')
tg_count() { docker exec m10a-proof-tg sh -c "grep -c '$1' /tmp/tg.log 2>/dev/null || true"; }
wait_until 10 bash -c "[[ \"\$(docker exec m10a-proof-tg sh -c 'grep -c sendMessage /tmp/tg.log 2>/dev/null || true')\" == '1' ]]"
check "$( [[ "$(jcode "$TEST")" == "200" && "$(jget "$(jbody "$TEST")" ok)" == "True" && "$(tg_count sendMessage)" == "1" ]]; echo $?)" \
  "A2: POST /missed-call-rules/{id}/test -> 200 ok=true, soxta Telegram sendMessage oldi" "$TEST"
check "$(docker exec m10a-proof-tg grep -q "path=/bot$TG_TOKEN/sendMessage chat_id=4242" /tmp/tg.log; echo $?)" \
  "A2: sendMessage to'g'ri token/chat_id bilan yuborilgan"
AUDIT_NS=$(jbody "$(api GET "/audit?entity=notify_settings")")
check "$(python3 -c "
import json,sys
rows=[r for r in json.load(sys.stdin).get('items',[]) if r.get('diff',{}).get('telegram_token')]
sys.exit(0 if rows and rows[0]['diff']['telegram_token']=='***' else 1)" <<<"$AUDIT_NS"; echo $?)" \
  "A2: audit notify_settings: telegram_token = '***'" "${AUDIT_NS:0:300}"

echo "=== A3: TTS (Yandex SpeechKit) sozlamalari ==="
TTS_NOTSET=$(api POST /settings/tts/test '{}')
check "$(err_is "$TTS_NOTSET" 409 tts_not_configured; echo $?)" "A3: TTS sozlanmagan -> 409 tts_not_configured" "$TTS_NOTSET"

FAKE_KEY="AQVNfake-yandex-api-key-proof"
# `updated_at` IXTIYORIY maydon (`UpdateTtsSettingsPayload.updated_at: datetime | None
# = None`) — qator hali mavjud bo'lmasa (haqiqiy `--fresh` o'rnatish) qiymat yo'q,
# qator ALLAQACHON mavjud bo'lsa (bu skript qayta-qayta, `--fresh`siz ishga tushsa —
# yuqoridagi "none"ga tushirish qatorni yaratgan bo'lishi mumkin) HAQIQIY qiymat
# yuborilishi SHART, aks holda optimistik qulf "stale" (409) qaytaradi.
TTS_BEFORE_UPDATED_AT=$(jget "$(jbody "$(api GET /settings/tts)")" updated_at)
TTS_PATCH_DATA="{\"provider\":\"yandex\",\"folder_id\":\"b1gfakefolder\",\"api_key\":\"$FAKE_KEY\""
[[ -n "$TTS_BEFORE_UPDATED_AT" ]] && TTS_PATCH_DATA+=",\"updated_at\":\"$TTS_BEFORE_UPDATED_AT\""
TTS_PATCH_DATA+="}"
TTS_PATCH=$(jbody "$(api PATCH /settings/tts "$TTS_PATCH_DATA")")
check "$( [[ "$(jget "$TTS_PATCH" item provider)" == "yandex" && "$(jget "$TTS_PATCH" item has_api_key)" == "True" ]]; echo $?)" \
  "A3: PATCH /settings/tts -> provider=yandex, has_api_key=true" "$TTS_PATCH"
check "$( ! grep -q "$FAKE_KEY" <<<"$(api GET /settings/tts)"; echo $?)" "A3: GET /settings/tts javobida api_key YO'Q"
check "$( [[ "$(sql "select count(*) from tts_settings where api_key_enc like '%$FAKE_KEY%'")" == "0" ]]; echo $?)" \
  "A3: tts_settings bazada api_key shifrlangan (ochiq matn YO'Q)"

# DIQQAT (ataylab soddalashtirish — pastda ham yakuniy hisobotda qayd etiladi): bu proof
# muhitida haqiqiy Yandex SpeechKit kaliti/tarmoq yo'q, shu sabab bu yerda FAQAT xato yo'li
# (502 tts_failed, tarmoq/HTTP xatosi) tekshiriladi — xato matnida API KALIT SIZMAYDI.
# Muvaffaqiyat yo'li (haqiqiy LPCM bayt oqimi) — soxta `httpx.MockTransport` bilan
# `tests/test_m10a_unit.py::test_synthesize_lpcm_success_with_fake_transport`da isbotlangan.
TTS_TEST=$(api POST /settings/tts/test '{}')
check "$( [[ "$(jcode "$TTS_TEST")" == "502" && "$(jget "$(jbody "$TTS_TEST")" error code)" == "tts_failed" ]]; echo $?)" \
  "A3: sozlangan (haqiqiy Yandex yo'q) -> 502 tts_failed" "$TTS_TEST"
check "$( ! grep -q "$FAKE_KEY" <<<"$TTS_TEST"; echo $?)" "A3: 502 xabarida API kalit SIZMAYDI"

echo
echo "=== YAKUN: PASS=$PASS FAIL=$FAIL ==="
[[ $FAIL -eq 0 ]]
