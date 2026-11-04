#!/usr/bin/env bash
# Innova PBX — M9 Bo'lak A isboti (replica/m9-freepbx-gaps-contract.md Bo'lak A):
#   A1. E'lonlar: audio yuklash -> e'lon (answer=true) -> kiruvchi marshrut (DID) ->
#       e'lon javob beradi -> next_target (221/222/223'dan biri) ga o'tadi (Goto).
#   A2. Boshqa manzil (misc_destinations, kiruvchi marshrut orqali, dial=ichki raqam) +
#       boshqa ilova (misc_applications, `code` to'g'ridan-to'g'ri ichkaridan terish) +
#       `code` to'qnashuvi -> 409 code_taken (aka/feature kodi bilan).
#   A3. Park sozlamalari: PUT /parking/settings (CUSTOM lot/slot/timeout) -> 409
#       number_taken (ichki raqam bilan to'qnashuv) -> `##<lot>`/`<slot>` JONLI (sukut
#       emas, bazadan).
#   A4. Paging guruhi (raqam terilsa a'zolarga INVITE) + intercom `*80<ext>` (Alert-Info/
#       Call-Info sarlavhasi — `m2a_phone.py`ning HDR qatori orqali).
#   A5. Call Waiting: sukut (true) -> band ext ga 2-INVITE YETADI; `*57` (cw_off, ext
#       bo'sh bo'lganda) -> 2-INVITE YUBORILMAYDI; `*56` (cw_on) bilan qaytariladi.
#
# Foydalanish:
#   scripts/m9a-proof.sh            # joriy `innova-m0` stackka qarshi
#   scripts/m9a-proof.sh --fresh    # avval `docker compose down -v` + qayta build + up -d
#
# MUHIM: faqat `innova-m0` compose loyihasiga tegadi; o'z konteynerlarini (m9a-proof-*) oxirida o'chiradi.
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

declare -A IP=([221]="172.28.0.230" [222]="172.28.0.231" [223]="172.28.0.232" [trunk]="172.28.0.233")
DID1=712099701   # A1: e'lon
DID2=712099702   # A2: boshqa manzil

# shellcheck source=lib/m2a_common.sh
source "$LIB_DIR/m2a_common.sh"

ADMIN_PASSWORD="${PROOF_ADMIN_PASSWORD:-$(grep -E '^PROOF_ADMIN_PASSWORD=' "$DEPLOY_DIR/.env" | cut -d= -f2-)}"
[[ -n "$ADMIN_PASSWORD" ]] || { echo "PROOF_ADMIN_PASSWORD deploy/.env da yo'q"; exit 2; }

CONTAINERS=(m9a-proof-221 m9a-proof-222 m9a-proof-223 m9a-proof-trunk)
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

# Oldingi (muvaffaqiyatsiz tugagan) ishga tushirishdan M9a* qoldiqlarini
# tozalash — `--fresh` ISHLATILMAYDI (stack umumiy, B/C agentlari ishlatadi),
# shu sabab skript o'zi idempotent bo'lishi SHART. Tartib: avval bog'liq
# bo'lgan narsalar (inbound-routes), keyin resurslar.
del_ids() { # path prefix -> `name` shu prefiks bilan boshlanganlarni DELETE qiladi
  # ESLATMA: ba'zi ro'yxat marshrutlari (`/trunks`, `/audio`, `/inbound-routes`)
  # `?q=` filtrini SERVERDA qo'llamaydi (hammasini qaytaradi) — shu sabab
  # prefiksni mijoz (python) tomonda tekshiramiz, server filtrini mo'ljal olmaymiz.
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
echo "=== oldingi M9a qoldiqlarini tozalash (bo'lsa) ==="
del_ids /inbound-routes M9aRoute
del_ids /misc-applications M9a
del_ids /page-groups M9a
del_ids /misc-destinations M9a
del_ids /announcements M9a
del_ids /extensions M9a
del_ids /trunks M9a
del_ids /audio M9aTone

target_id_by_kind_name() { # kind name -> call_targets id (label aynan name)
  local kind="$1" name="$2" r
  r=$(curl -s "$API_BASE/targets?kind=$kind&q=$name" "${AUTH[@]}")
  python3 -c "
import json,sys
d=json.load(sys.stdin)
items=[i for i in d['items'] if i['label']=='$name']
print(items[0]['id'] if items else '')
" <<<"$r"
}
ext_target_id() { # raqam -> call_targets id ('<raqam> · M9a<raqam>' labelidan `q=` filtri yetarli)
  jbody "$(api GET "/targets?kind=extension&q=$1")" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print(d['items'][0]['id'] if d['items'] else '')"
}

# ---------------------------------------------------------------- resurslar
echo "=== resurslar ==="
declare -A EXT_ID SECRET
for n in 221 222 223; do
  j=$(jbody "$(api POST /extensions "{\"number\":\"$n\",\"name\":\"M9a$n\"}")")
  EXT_ID[$n]=$(jget "$j" item id); SECRET[$n]=$(jget "$j" sip password)
done
[[ -n "${EXT_ID[221]}" && -n "${EXT_ID[222]}" && -n "${EXT_ID[223]}" ]] \
  && pass "POST /extensions -> 221, 222, 223" || fail "extensions -> ${EXT_ID[*]}"

TRUNK=$(jbody "$(api POST /trunks "{\"name\":\"M9aTrunk\",\"host\":\"${IP[trunk]}\",\"port\":5060,\"match\":[\"${IP[trunk]}/32\"],\"codecs\":[\"ulaw\"],\"max_channels\":5,\"enabled\":true}")")
TRUNK_ID=$(jget "$TRUNK" item id)
check "$( [[ -n "$TRUNK_ID" ]]; echo $?)" "POST /trunks -> M9aTrunk" "$TRUNK"

echo "=== telefonlar ==="
for c in 221 222 223 trunk; do
  docker run -d --name "m9a-proof-$c" --network "$NET" --ip "${IP[$c]}" "$PY_IMAGE" sleep infinity >/dev/null
  for f in outbound_invite.py vm_caller.py m2a_phone.py; do docker cp "$SIPP_DIR/$f" "m9a-proof-$c:/tmp/$f"; done
done
for n in 221 222 223; do
  docker exec -d "m9a-proof-$n" sh -c "cd /tmp && python3 m2a_phone.py serve $n '${SECRET[$n]}' 5070 12000 /tmp/mode 520 > /tmp/phone.log 2>&1"
done
docker exec m9a-proof-trunk sh -c "echo answer > /tmp/mode"
docker exec -d m9a-proof-trunk sh -c "cd /tmp && python3 m2a_phone.py serve trunk - 5060 12000 /tmp/mode 520 > /tmp/phone.log 2>&1"
registered() { for n in 221 222 223; do docker exec "m9a-proof-$n" grep -q 'REGISTER_RESULT: OK' /tmp/phone.log 2>/dev/null || return 1; done; }
wait_until 15 registered && pass "221, 222, 223 REGISTER -> 200 OK" || fail "REGISTER -> $(docker exec m9a-proof-221 cat /tmp/phone.log)"

# M9a jonli isbotda topilgan nozik muammo (dialplandan EMAS): `qualify_frequency=60`
# — biz REGISTER qilgandan keyin ko'p ketma-ket API chaqiruvi (audio, e'lon,
# marshrut, ...) o'tadi; agar birinchi avtomatik OPTIONS qualify shu oraliqda
# bitta safar o'tkazib yuborilsa (Unavail), KEYINGI 60s gacha Asterisk
# `PJSIP/<ext>`ga Dial() qila OLMAYDI ("Could not create dialog ... invalid
# URI"). Har qoldirilgan tekshiruv OLDIDAN `pjsip qualify` bilan majburiy
# OPTIONS yuborib, "Avail" bo'lishini kutamiz (haqiqiy telefonlar buni avtomatik
# tez-tez REGISTER bilan hal qiladi — bu test-stub REGISTER'ni faqat 1 marta
# yuboradi, shu sabab qo'lda qualify kerak).
qualify_wait() { # ext... -> har biriga `pjsip qualify` + "Avail" bo'lguncha kutish
  local n
  for n in "$@"; do docker exec "$AST" asterisk -rx "pjsip qualify $n" >/dev/null 2>&1; done
  for n in "$@"; do
    wait_until 8 sh -c "docker exec $AST asterisk -rx 'pjsip show contacts' | grep \"  Contact:  $n/\" | grep -q Avail" || true
  done
}
mode() { docker exec "m9a-proof-$1" sh -c "echo '$2' > /tmp/mode"; }
plog() { docker exec "m9a-proof-$1" cat /tmp/phone.log 2>/dev/null; }
invites() { plog "$1" | grep -c '^INVITE '; }
last_invite() { plog "$1" | grep '^INVITE ' | tail -1; }
count_of() { plog "$1" | grep -c "^$2"; }
CALL_N=0
place_call() { # ext dialed talk_s [dtmf] -> $OUT (sinxron)
  CALL_N=$((CALL_N + 1))
  OUT=$(docker exec "m9a-proof-$1" sh -c "cd /tmp && python3 m2a_phone.py call $1 '${SECRET[$1]}' $((5100 + CALL_N)) $((13000 + CALL_N * 2)) '$2' $3 '${4:-}'" 2>&1)
}
place_call_bg() { # nom ext dialed talk_s [dtmf] -> /tmp/<nom>.log (fon)
  CALL_N=$((CALL_N + 1))
  docker exec -d "m9a-proof-$2" sh -c "cd /tmp && python3 m2a_phone.py call $2 '${SECRET[$2]}' $((5100 + CALL_N)) $((13000 + CALL_N * 2)) '$3' $4 '${5:-}' > /tmp/$1.log 2>&1"
}
call_log() { docker exec "m9a-proof-$1" cat "/tmp/$2.log" 2>/dev/null; }
call_done() { call_log "$1" "$2" | grep -Eq 'BYE_SENT|REMOTE_BYE|INVITE_FINAL: SIP/2.0 [3-6]'; }
final_of() { sed -n 's/^INVITE_FINAL: SIP\/2.0 \([0-9]*\).*/\1/p' <<<"$1"; }
TRUNK_CALL_N=0
trunk_call() { # DID talk_s -> $OUT (sinxron, trunk konteyneridan kiruvchi chaqiruv sifatida)
  # ESLATMA: `serve` jarayoni (trunk UAS) allaqachon 5060'da tinglaydi —
  # chiquvchi (UAC) tomon BOSHQA portda bo'lishi kerak (Errno 98 oldini olish).
  TRUNK_CALL_N=$((TRUNK_CALL_N + 1))
  OUT=$(docker exec m9a-proof-trunk sh -c "cd /tmp && python3 m2a_phone.py call trunk - $((5160 + TRUNK_CALL_N)) $((12100 + TRUNK_CALL_N * 2)) '$1' $2" 2>&1)
}
ext_item() { # raqam -> GET /extensions dagi item JSON
  jbody "$(api GET "/extensions?q=M9a$1")" | python3 -c "
import json,sys
print(json.dumps(next(i for i in json.load(sys.stdin)['items'] if i['number']==sys.argv[1])))" "$1"
}
ext_field() { jget "$(ext_item "$1")" "$2"; }
ext_patch() { # raqam json_qismi -> $PATCH_OUT
  local stamp
  stamp=$(ext_field "$1" updated_at)
  PATCH_OUT=$(api PATCH "/extensions/${EXT_ID[$1]}" "{${2},\"updated_at\":\"$stamp\"}")
}

# ---------------------------------------------------------------- A1: e'lonlar
echo "--- A1. e'lonlar ---"
python3 - <<'PY'
import wave, struct, math
with wave.open('/tmp/m9a-tone.wav', 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
    frames = b''.join(struct.pack('<h', int(3000 * math.sin(2 * math.pi * 440 * i / 8000))) for i in range(8000))
    w.writeframes(frames)
PY
AUDIO=$(curl -s -w '\n%{http_code}' -X POST "$API_BASE/audio" "${AUTH[@]}" -F "name=M9aTone" -F "file=@/tmp/m9a-tone.wav;type=audio/wav")
AUDIO_ID=$(jget "$(jbody "$AUDIO")" item id)
check "$( [[ "$(jcode "$AUDIO")" == "201" && -n "$AUDIO_ID" ]]; echo $?)" "POST /audio -> M9aTone yuklandi" "$AUDIO"

EXT223_TARGET=$(ext_target_id 223)
ANN=$(api POST /announcements "{\"name\":\"M9aAnn\",\"audio_file_id\":\"$AUDIO_ID\",\"answer\":true,\"allow_skip\":false,\"next_target_id\":\"$EXT223_TARGET\"}")
check "$( [[ "$(jcode "$ANN")" == "201" ]]; echo $?)" "POST /announcements -> M9aAnn (answer=true, next=223)" "$ANN"
ANN_TARGET=$(target_id_by_kind_name announcement M9aAnn)
check "$( [[ -n "$ANN_TARGET" ]]; echo $?)" "GET /targets?kind=announcement -> M9aAnn topildi" "$ANN_TARGET"

R1=$(api POST /inbound-routes "{\"name\":\"M9aRoute1\",\"did\":\"$DID1\",\"target_id\":\"$ANN_TARGET\",\"enabled\":true}")
check "$( [[ "$(jcode "$R1")" == "201" && "$(jget "$(jbody "$R1")" apply status)" == "applied" ]]; echo $?)" \
  "POST /inbound-routes -> $DID1 (e'lon) applied" "$R1"

mode 223 answer
qualify_wait 223
B223=$(invites 223)
trunk_call "$DID1" 6
check "$( [[ "$(final_of "$OUT")" == "200" ]]; echo $?)" "A1: trunk -> $DID1 -> e'lon javob berdi (200)" "$OUT"
wait_until 10 sh -c "[ \$(docker exec m9a-proof-223 grep -c '^INVITE ' /tmp/phone.log) -gt $B223 ]"
check "$( [[ "$(invites 223)" -gt "$B223" ]]; echo $?)" "A1: e'londan keyin next_target (223) ga Goto bo'ldi (INVITE)" "$(last_invite 223)"

# ---------------------------------------------------------------- A2: boshqa manzil/ilova
echo "--- A2. boshqa manzil/ilova ---"
MD=$(api POST /misc-destinations '{"name":"M9aMisc","dial":"222"}')
check "$( [[ "$(jcode "$MD")" == "201" ]]; echo $?)" "POST /misc-destinations -> M9aMisc (dial=222)" "$MD"
MD_TARGET=$(target_id_by_kind_name misc M9aMisc)
R2=$(api POST /inbound-routes "{\"name\":\"M9aRoute2\",\"did\":\"$DID2\",\"target_id\":\"$MD_TARGET\",\"enabled\":true}")
check "$( [[ "$(jcode "$R2")" == "201" && "$(jget "$(jbody "$R2")" apply status)" == "applied" ]]; echo $?)" \
  "POST /inbound-routes -> $DID2 (boshqa manzil) applied" "$R2"
mode 222 answer
qualify_wait 222
trunk_call "$DID2" 3
check "$( [[ "$(final_of "$OUT")" == "200" ]] && grep -q "from=trunk" <<<"$(last_invite 222)"; echo $?)" \
  "A2: trunk -> $DID2 -> boshqa manzil -> 222 javob berdi" "$OUT / $(last_invite 222)"

EXT221_TARGET=$(ext_target_id 221)
MA=$(api POST /misc-applications "{\"name\":\"M9aApp\",\"code\":\"*55\",\"target_id\":\"$EXT221_TARGET\"}")
check "$( [[ "$(jcode "$MA")" == "201" ]]; echo $?)" "POST /misc-applications -> M9aApp (*55 -> 221)" "$MA"
mode 221 answer
qualify_wait 221
B221=$(invites 221)
place_call 222 '*55' 3
check "$( [[ "$(final_of "$OUT")" == "200" && "$(invites 221)" == "$((B221 + 1))" ]]; echo $?)" \
  "A2: 222 '*55' -> 221 javob berdi (misc_application to'g'ridan-to'g'ri terilganda)" "$OUT"

MA_DUP=$(api POST /misc-applications "{\"name\":\"M9aApp2\",\"code\":\"*55\",\"target_id\":\"$EXT221_TARGET\"}")
check "$( [[ "$(jcode "$MA_DUP")" == "409" && "$(jget "$(jbody "$MA_DUP")" error code)" == "code_taken" ]]; echo $?)" \
  "A2: *55 takror -> 409 code_taken (aka bilan)" "$MA_DUP"
MA_FC=$(api POST /misc-applications "{\"name\":\"M9aApp3\",\"code\":\"*80\",\"target_id\":\"$EXT221_TARGET\"}")
check "$( [[ "$(jcode "$MA_FC")" == "409" && "$(jget "$(jbody "$MA_FC")" error code)" == "code_taken" ]]; echo $?)" \
  "A2: *80 (intercom xususiyat kodi) -> 409 code_taken" "$MA_FC"

# ---------------------------------------------------------------- A3: park sozlamalari
echo "--- A3. park sozlamalari ---"
PS=$(jbody "$(api GET /parking/settings)")
PS_UPDATED=$(jget "$PS" updated_at)
TAKEN=$(api PUT /parking/settings "{\"first_slot\":221,\"slot_count\":3,\"updated_at\":\"$PS_UPDATED\"}")
check "$( [[ "$(jcode "$TAKEN")" == "409" && "$(jget "$(jbody "$TAKEN")" error code)" == "number_taken" ]]; echo $?)" \
  "A3: first_slot=221 (ichki raqam bilan to'qnashadi) -> 409 number_taken" "$TAKEN"

PUT1=$(api PUT /parking/settings "{\"lot_number\":\"800\",\"first_slot\":821,\"slot_count\":5,\"timeout_s\":15,\"updated_at\":\"$PS_UPDATED\"}")
# ESLATMA: `apply.status` qayta ishga tushirishda (qiymatlar OLDINGI yurishdan
# bazada allaqachon bir xil bo'lsa) "unchanged" bo'lishi MUMKIN — bu TO'G'RI
# natija (apply_config sha256 solishtiradi, M0/architecture.md), xato EMAS.
APPLY1_STATUS=$(jget "$(jbody "$PUT1")" apply status)
check "$( [[ "$(jcode "$PUT1")" == "200" && "$(jget "$(jbody "$PUT1")" item lot_number)" == "800" \
  && ( "$APPLY1_STATUS" == "applied" || "$APPLY1_STATUS" == "unchanged" ) ]]; echo $?)" \
  "A3: PUT /parking/settings -> lot 800, slot 821-825, timeout 15s (CUSTOM)" "$PUT1"
check "$(ast "parking show t1-park" | grep -q "821-825"; echo $?)" "A3: Asterisk: park lot t1-park (821-825, bazadan)" "$(ast "parking show t1-park")"

# ESLATMA: `821` — slotni QAYTA OLISH (`ParkedCall`, pastda 222 shuni qiladi),
# PARKLASH uchun lot kengaytmasi `800` (`Park(t1-park)`) terilishi SHART — u
# navbatdagi BO'SH slotni (821) o'zi tanlaydi. (M9a ishlab chiqishda topilgan
# skript xatosi: avval noto'g'ri `821`ga blind-transfer qilingan edi.)
mode 221 'answer:##,,800'
qualify_wait 221
parked_n() { jbody "$(api GET /parking/calls)" | python3 -c "import json,sys;print(len(json.load(sys.stdin)['parked']))"; }
parked_is() { [[ "$(parked_n)" == "$1" ]]; }
place_call_bg a3 223 221 40
wait_until 15 parked_is 1
PARK=$(jbody "$(api GET /parking/calls)")
check "$(python3 -c "
import json,sys
d=json.load(sys.stdin); p=d['parked']
ok = d['lot']=='800' and d['slots']=='821-825' and len(p)==1 and p[0]['slot']=='821'
sys.exit(0 if ok else 1)" <<<"$PARK"; echo $?)" "A3: ##821 -> GET /parking/calls: lot 800, slot 821 (CUSTOM, bazadan)" "$PARK"
place_call_bg r3 222 821 4
wait_until 10 bridged 223 222 && pass "A3: 222 '821' -> 223 bilan ulandi (CUSTOM slot)" \
  || fail "A3: 821 -> bridge yo'q ($(ast 'core show channels concise'))"
wait_until 5 parked_is 0
wait_until 15 call_done 223 a3

# ESLATMA (muhim, umumiy stek): park sozlamalari TENANT DARAJASIDA YAGONA
# (singleton) qator — yuqoridagi CUSTOM qiymat (800/821-825/15s) shu yerda
# QOLSA, boshqa regressiya skriptlari (`m2a-proof.sh` §7/7b — default
# 700/701-720ga tayangan) keyinroq ishga tushganda FAIL beradi (M9a rejimida
# topilgan kross-skript nuqsoni: sozlama bazada QOLADI, test izidan
# tozalanmaydi). Shu sabab A3 yakunida DEFAULT (`app/db/models.py`:
# lot_number="700", first_slot=701, slot_count=20, timeout_s=60) ga qaytaramiz.
PS_RESTORE_UPDATED=$(jget "$(jbody "$(api GET /parking/settings)")" updated_at)
RESTORE=$(api PUT /parking/settings "{\"lot_number\":\"700\",\"first_slot\":701,\"slot_count\":20,\"timeout_s\":60,\"updated_at\":\"$PS_RESTORE_UPDATED\"}")
check "$( [[ "$(jcode "$RESTORE")" == "200" && "$(jget "$(jbody "$RESTORE")" item lot_number)" == "700" ]]; echo $?)" \
  "A3: PUT /parking/settings -> DEFAULT (700/701-720/60s) ga qaytarildi (umumiy stek uchun tozalash)" "$RESTORE"

# ---------------------------------------------------------------- A4: paging/intercom
echo "--- A4. paging/intercom ---"
PG_JSON=$(api POST /page-groups "{\"name\":\"M9aPage\",\"number\":\"651\",\"member_extension_ids\":[\"${EXT_ID[222]}\",\"${EXT_ID[223]}\"]}")
check "$( [[ "$(jcode "$PG_JSON")" == "201" && "$(jget "$(jbody "$PG_JSON")" apply status)" == "applied" ]]; echo $?)" \
  "POST /page-groups -> M9aPage (651, a'zo 222/223)" "$PG_JSON"
mode 222 ring; mode 223 ring
qualify_wait 222 223
B222=$(invites 222); B223=$(invites 223)
place_call 221 651 2
wait_until 5 sh -c "[ \$(docker exec m9a-proof-222 grep -c '^INVITE ' /tmp/phone.log) -gt $B222 ]"
check "$( [[ "$(invites 222)" -gt "$B222" && "$(invites 223)" -gt "$B223" ]]; echo $?)" \
  "A4: 221 '651' -> 222 VA 223 ga INVITE (Page guruhi)" "$(last_invite 222) / $(last_invite 223)"

mode 222 answer
qualify_wait 222
place_call 221 '*80222' 2
check "$( [[ "$(final_of "$OUT")" == "200" ]]; echo $?)" "A4: 221 '*80222' (intercom) -> 222 javob berdi" "$OUT"
check "$(plog 222 | grep -q '^HDR ' && plog 222 | tail -3 | grep -q 'HDR'; echo $?)" \
  "A4: intercom INVITE'da Alert-Info/Call-Info sarlavhasi bor" "$(plog 222 | tail -5)"
echo "ESLATMA (chegara): Page() guruh a'zolari uchun sarlavha KAFOLATLANMAYDI (Dial b() qo'llamaydi, dialplan_features.py::page_group_lines docstring) — faqat intercom (*80) uchun tekshirildi."

# ---------------------------------------------------------------- A5: call waiting
echo "--- A5. call waiting ---"
check "$( [[ "$(ext_field 221 call_waiting)" == "True" ]]; echo $?)" "A5: sukut call_waiting=true (221)" "$(ext_field 221 call_waiting)"
mode 221 answer
qualify_wait 221
B221=$(invites 221)
place_call_bg a5a 223 221 10
wait_until 10 sh -c "[ \$(docker exec m9a-proof-221 grep -c '^INVITE ' /tmp/phone.log) -gt $B221 ]"
B221_2=$(invites 221)
place_call 222 221 2
check "$( [[ "$(invites 221)" == "$((B221_2 + 1))" ]]; echo $?)" \
  "A5: sukut (true) -> 221 band bo'lsa ham 2-INVITE YETDI" "$OUT / invites=$(invites 221)"
wait_until 15 call_done 223 a5a

place_call 221 '*57' 3
check "$( [[ "$(final_of "$OUT")" == "200" && "$(ext_field 221 call_waiting)" == "False" ]]; echo $?)" \
  "A5: 221 '*57' (cw_off, bo'sh holatda) -> call_waiting=false" "$OUT"

mode 221 answer
qualify_wait 221
B221=$(invites 221)
place_call_bg a5b 223 221 10
wait_until 10 sh -c "[ \$(docker exec m9a-proof-221 grep -c '^INVITE ' /tmp/phone.log) -gt $B221 ]"
B221_2=$(invites 221)
place_call 222 221 2
check "$( [[ "$(invites 221)" == "$B221_2" && "$(final_of "$OUT")" != "200" ]]; echo $?)" \
  "A5: call_waiting=false -> 221 band bo'lsa 2-INVITE YUBORILMADI ($(final_of "$OUT"))" "$OUT / invites=$(invites 221)"
wait_until 15 call_done 223 a5b

place_call 221 '*56' 3
check "$( [[ "$(final_of "$OUT")" == "200" && "$(ext_field 221 call_waiting)" == "True" ]]; echo $?)" \
  "A5: 221 '*56' (cw_on) -> call_waiting=true (qaytarildi)" "$OUT"

echo "=== NATIJA: PASS=$PASS FAIL=$FAIL ==="
[[ "$FAIL" -eq 0 ]]
