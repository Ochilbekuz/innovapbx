#!/usr/bin/env bash
# Innova PBX — M1b proof skripti. replica/m1b-contract.md bo'lim 9'dagi 8
# ssenariy + qo'shimcha MOH (bo'lim 8) ssenariysini ishga tushiradi:
#   1. 101 -> 0901234567 -> marshrut UZ -> trunk A (503) -> trunk B (javob).
#      UAS B: Request-URI=998901234567, From/PAI'da route CallerID. CDR
#      direction=out, trunk=B, ANSWERED.
#   2. Xalqaro: 101 -> 0044201234567, international=false -> rad (0 INVITE
#      trunkka), CDR failed/congestion.
#   3. outbound_allowed=false ichki raqam -> rad. PIN marshrut: xato PIN bilan
#      rad, to'g'ri PIN bilan o'tadi.
#   4. /outbound-routes/simulate -- 1-3'dagi natijalar bilan BIR XIL.
#   5. Ring group tashqi a'zo -> kiruvchi DID -> guruh -> tashqi raqam trunk
#      orqali terildi.
#   6. Revision restore: A -> B -> A tiklandi -> dialplan show A matnini
#      ko'rsatadi; audit'da restore bor.
#   7. Register-trunk: test registrar (REGISTER->401->200) -> health.registration=registered.
#   8. Audit: trunk paroli o'zgartirildi -> diff'da "***", ochiq parol yo'q.
#   9. MOH: navbatga moh_class_id biriktirilgan -> `moh show classes`da ko'rinadi.
#  10. S32: RTP oralig'i restart'siz qo'llanadi; tashqi IP -> restart_required; faol qo'ng'iroqda
#      restart 409; restart -> Asterisk qayta ishga tushdi, transport'da tashqi IP; null bilan tozalash.
#
# Foydalanish:
#   scripts/m1b-proof.sh            # joriy `innova-m0` stackka qarshi (M1b qoldiqlari bo'lsa — exit 2)
#   scripts/m1b-proof.sh --fresh    # avval `docker compose down -v` + qayta build + up -d
#
# MUHIM: bu skript faqat `innova-m0` compose loyihasiga tegadi.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"
SIPP_DIR="$ROOT_DIR/tests/sipp"
API_BASE="${API_BASE:-http://127.0.0.1:8710/api/v1}"
PROJECT="innova-m0"
NET="${PROJECT}_innova-net"
SIPP_IMAGE="python:3.12-slim"

EXT_IP="172.21.0.150"       # 101/109 (ichki raqam, chiquvchi qo'ng'iroqlar)
TRUNKA_IP="172.21.0.151"    # trunk A (503 rad)
TRUNKB_IP="172.21.0.152"    # trunk B (javob beradi, log qiladi)
TRUNKRG_IP="172.21.0.153"   # ring group tashqi a'zo trunk
INBOUND_UAC_IP="172.21.0.154"  # kiruvchi DID'ni simulyatsiya qiluvchi UAC
REGTRUNK_IP="172.21.0.155"  # register-rejim trunk (test registrar)

ADMIN_PASSWORD="${PROOF_ADMIN_PASSWORD:-$(grep -E '^PROOF_ADMIN_PASSWORD=' "$DEPLOY_DIR/.env" | cut -d= -f2-)}"
[[ -n "$ADMIN_PASSWORD" ]] || { echo "PROOF_ADMIN_PASSWORD deploy/.env da yo'q"; exit 2; }

PASS=0
FAIL=0
pass() { echo "PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); }

# `cdr.conf`'da batch=no bo'lsa ham, CDR yozuvi H-kontekst/ikkinchi (trunk)
# oyoq tugashidan SO'NG yoziladi -- qattiq `sleep N` noaniq (muhitga qarab
# yetarli/yetarsiz) bo'lgani uchun, kutilgan qatorni topguncha qisqa
# intervalda qayta so'raymiz (sinovda topilgan: `sleep 1` ba'zan CDR
# yozilishidan OLDIN so'rov yuborib bo'sh natija qaytarardi, garchi qator
# bir necha soniyadan keyin bazada TO'G'RI ko'rinsa ham).
wait_for_sql() { # sql max_seconds -> stdout: oxirgi natija (bo'sh bo'lsa ham)
  local sql="$1" max_seconds="${2:-5}" tries out="" i=0
  tries=$(( max_seconds * 2 ))
  while (( i < tries )); do
    out=$(docker exec innova-m0-postgres-1 psql -U innova -d innova -tAc "$sql" 2>/dev/null)
    [[ -n "$out" ]] && { echo "$out"; return 0; }
    sleep 0.5
    i=$((i + 1))
  done
  echo "$out"
}

CONTAINERS=(m1b-proof-ext m1b-proof-trunka m1b-proof-trunkb m1b-proof-trunkrg m1b-proof-inbound m1b-proof-regtrunk)
cleanup_sipp() {
  docker rm -f "${CONTAINERS[@]}" >/dev/null 2>&1 || true
}
trap cleanup_sipp EXIT
cleanup_sipp

if [[ "${1:-}" == "--fresh" ]]; then
  echo "--- --fresh: stack qayta quriladi ---"
  (cd "$DEPLOY_DIR" && docker compose down -v) || true
  (cd "$DEPLOY_DIR" && docker compose build) || { fail "docker compose build"; exit 1; }
  (cd "$DEPLOY_DIR" && docker compose up -d) || { fail "docker compose up"; exit 1; }
  echo "Konteynerlar tayyor bo'lishini kutish..."
  for i in $(seq 1 60); do
    curl -sf "${API_BASE%/api/v1}/healthz" >/dev/null 2>&1 && break
    sleep 2
  done
fi

echo "=== setup/login ==="
curl -s -o /tmp/m1bproof_setup.json -X POST "$API_BASE/setup" -H 'Content-Type: application/json' \
  -d '{"admin":{"login":"admin","password":"'"$ADMIN_PASSWORD"'","full_name":"Admin"},"language":"uz","timezone":"Asia/Tashkent"}' >/dev/null
LOGIN_JSON=$(curl -s -X POST "$API_BASE/auth/login" -H 'Content-Type: application/json' \
  -d '{"login":"admin","password":"'"$ADMIN_PASSWORD"'"}')
TOKEN=$(echo "$LOGIN_JSON" | python3 -c "import json,sys;print(json.load(sys.stdin).get('access',''))" 2>/dev/null)
if [[ -z "$TOKEN" ]]; then fail "login -> token yo'q ($LOGIN_JSON)"; exit 1; fi
AUTH=(-H "Authorization: Bearer $TOKEN")
echo "login OK"

# Oldindan tekshiruv: skript resurslarni (101, M1bTrunkA, ...) noldan yaratadi. Stekda oldingi
# isbot qoldiqlari bo'lsa, o'nlab chalg'ituvchi FAIL o'rniga aniq sabab bilan to'xtaymiz.
LEFTOVER=$(curl -s "$API_BASE/trunks" "${AUTH[@]}" | python3 -c "
import json,sys
print(','.join(t['name'] for t in json.load(sys.stdin).get('items', []) if t['name'].startswith('M1b')))")
if [[ -n "$LEFTOVER" ]]; then
  echo "Stekda oldingi M1b isbot qoldiqlari bor ($LEFTOVER) — 'scripts/m1b-proof.sh --fresh' bilan ishga tushiring."
  exit 2
fi

api() { # method path [data]
  local method="$1" path="$2" data="${3:-}"
  if [[ -n "$data" ]]; then
    curl -s -w '\n%{http_code}' -X "$method" "$API_BASE$path" "${AUTH[@]}" -H 'Content-Type: application/json' -d "$data"
  else
    curl -s -w '\n%{http_code}' -X "$method" "$API_BASE$path" "${AUTH[@]}"
  fi
}
jbody() { echo "$1" | sed '$d'; }
jcode() { echo "$1" | tail -1; }
jget() { python3 -c "import json,sys;d=json.load(sys.stdin)
cur=d
for k in sys.argv[1:]:
    cur = cur[int(k)] if k.lstrip('-').isdigit() else cur.get(k)
print('' if cur is None else cur)" "${@:2}" <<<"$1"; }

target_id_by_kind_name() { # kind name -> call_targets id
  local kind="$1" name="$2"
  local r; r=$(curl -s "$API_BASE/targets?kind=$kind&q=$name" "${AUTH[@]}")
  python3 -c "
import json,sys
d=json.load(sys.stdin)
items=[i for i in d['items'] if i['label']=='$name']
print(items[0]['id'] if items else '')
" <<<"$r"
}

echo "=== resurslarni tayyorlash ==="
EXT101_JSON=$(api POST /extensions '{"number":"101","name":"M1bAgent101"}')
EXT101_SECRET=$(jget "$(jbody "$EXT101_JSON")" sip password)
EXT101_ID=$(jget "$(jbody "$EXT101_JSON")" item id)
EXT101_UPDATED=$(jget "$(jbody "$EXT101_JSON")" item updated_at)
[[ -n "$EXT101_ID" ]] && pass "POST /extensions -> 101 yaratildi" || fail "POST /extensions 101 -> $EXT101_JSON"

EXT109_JSON=$(api POST /extensions '{"number":"109","name":"M1bBlocked109"}')
EXT109_ID=$(jget "$(jbody "$EXT109_JSON")" item id)
EXT109_UPDATED=$(jget "$(jbody "$EXT109_JSON")" item updated_at)
[[ -n "$EXT109_ID" ]] && pass "POST /extensions -> 109 yaratildi" || fail "POST /extensions 109 -> $EXT109_JSON"
BLOCK_JSON=$(api PATCH "/extensions/$EXT109_ID" "{\"outbound_allowed\":false,\"updated_at\":\"$EXT109_UPDATED\"}")
BLOCK_ALLOWED=$(jget "$(jbody "$BLOCK_JSON")" item outbound_allowed)
[[ "$BLOCK_ALLOWED" == "False" ]] && pass "PATCH /extensions/109 -> outbound_allowed=false" || fail "PATCH /extensions/109 -> $BLOCK_JSON"

HANGUP_TARGET=$(python3 -c "
import json,sys
d=json.load(sys.stdin)
items=[i for i in d['items'] if i['kind']=='hangup']
print(items[0]['id'] if items else '')
" <<<"$(curl -s "$API_BASE/targets?kind=hangup" "${AUTH[@]}")")
[[ -n "$HANGUP_TARGET" ]] && pass "hangup tizim manzili topildi" || fail "hangup tizim manzili topilmadi"

# --- Trunklar ---
TRUNKA_JSON=$(api POST /trunks "{\"name\":\"M1bTrunkA\",\"host\":\"$TRUNKA_IP\",\"port\":5060,\"match\":[\"$TRUNKA_IP/32\"],\"codecs\":[\"ulaw\"],\"max_channels\":5,\"enabled\":true}")
TRUNKA_ID=$(jget "$(jbody "$TRUNKA_JSON")" item id)
[[ -n "$TRUNKA_ID" ]] && pass "POST /trunks -> M1bTrunkA yaratildi" || fail "POST /trunks TrunkA -> $TRUNKA_JSON"

TRUNKB_JSON=$(api POST /trunks "{\"name\":\"M1bTrunkB\",\"host\":\"$TRUNKB_IP\",\"port\":5060,\"match\":[\"$TRUNKB_IP/32\"],\"codecs\":[\"ulaw\"],\"max_channels\":5,\"enabled\":true}")
TRUNKB_ID=$(jget "$(jbody "$TRUNKB_JSON")" item id)
[[ -n "$TRUNKB_ID" ]] && pass "POST /trunks -> M1bTrunkB yaratildi" || fail "POST /trunks TrunkB -> $TRUNKB_JSON"

TRUNKRG_JSON=$(api POST /trunks "{\"name\":\"M1bTrunkRG\",\"host\":\"$TRUNKRG_IP\",\"port\":5060,\"match\":[\"$TRUNKRG_IP/32\"],\"codecs\":[\"ulaw\"],\"max_channels\":5,\"enabled\":true}")
TRUNKRG_ID=$(jget "$(jbody "$TRUNKRG_JSON")" item id)
[[ -n "$TRUNKRG_ID" ]] && pass "POST /trunks -> M1bTrunkRG yaratildi" || fail "POST /trunks TrunkRG -> $TRUNKRG_JSON"

# --- kiruvchi (trunk-identify) UAC uchun ham trunk kerak ([from-trunk] IP orqali aniqlanadi) ---
TRUNKIN_JSON=$(api POST /trunks "{\"name\":\"M1bTrunkInbound\",\"host\":\"$INBOUND_UAC_IP\",\"port\":5060,\"match\":[\"$INBOUND_UAC_IP/32\"],\"codecs\":[\"ulaw\"],\"max_channels\":5,\"enabled\":true}")
TRUNKIN_ID=$(jget "$(jbody "$TRUNKIN_JSON")" item id)
[[ -n "$TRUNKIN_ID" ]] && pass "POST /trunks -> M1bTrunkInbound yaratildi" || fail "POST /trunks TrunkInbound -> $TRUNKIN_JSON"

# --- Marshrutlar: tartib MUHIM (priority 1 avval tekshiriladi) ---
# RGRoute (priority1, 5XXXXXXXXX, faqat TrunkRG) -> ring group tashqi a'zosi uchun ajratilgan.
RGROUTE_JSON=$(api POST /outbound-routes "{\"name\":\"M1bRGRoute\",\"priority\":1,\"patterns\":[{\"pattern\":\"5XXXXXXXXX\"}],\"trunk_ids\":[\"$TRUNKRG_ID\"],\"international\":false}")
RGROUTE_ID=$(jget "$(jbody "$RGROUTE_JSON")" item id)
[[ -n "$RGROUTE_ID" ]] && pass "POST /outbound-routes -> M1bRGRoute (p1) yaratildi" || fail "POST /outbound-routes RGRoute -> $RGROUTE_JSON"

# PINRoute (priority2, 7XXXXXXXXX, PIN=1357, faqat TrunkB)
PINROUTE_JSON=$(api POST /outbound-routes "{\"name\":\"M1bPinRoute\",\"priority\":2,\"patterns\":[{\"pattern\":\"7XXXXXXXXX\"}],\"trunk_ids\":[\"$TRUNKB_ID\"],\"pin\":\"1357\",\"international\":false}")
PINROUTE_ID=$(jget "$(jbody "$PINROUTE_JSON")" item id)
[[ -n "$PINROUTE_ID" ]] && pass "POST /outbound-routes -> M1bPinRoute (p2, PIN) yaratildi" || fail "POST /outbound-routes PinRoute -> $PINROUTE_JSON"

# UZRoute (priority3, strip 1 raqam + XXXXXXXXX + 998 prefiks, TrunkA->TrunkB, callerid override)
UZROUTE_JSON=$(api POST /outbound-routes "{\"name\":\"M1bUZRoute\",\"priority\":3,\"patterns\":[{\"strip_prefix\":\"0\",\"pattern\":\"XXXXXXXXX\",\"add_prefix\":\"998\"}],\"trunk_ids\":[\"$TRUNKA_ID\",\"$TRUNKB_ID\"],\"callerid\":\"999000111\",\"override_extension_callerid\":true,\"international\":false}")
UZROUTE_ID=$(jget "$(jbody "$UZROUTE_JSON")" item id)
[[ -n "$UZROUTE_ID" ]] && pass "POST /outbound-routes -> M1bUZRoute (p3, A->B, CID override) yaratildi" || fail "POST /outbound-routes UZRoute -> $UZROUTE_JSON"

# --- Ring group (tashqi a'zo, RGRoute pattern'iga mos raqam) ---
RGEXT_NUMBER="5550001112"
RG_JSON=$(api POST /ring-groups "{\"name\":\"M1bRingGroup\",\"strategy\":\"ringall\",\"ring_seconds\":15,\"members\":[{\"external_number\":\"$RGEXT_NUMBER\"}],\"no_answer_target_id\":\"$HANGUP_TARGET\"}")
RG_ID=$(jget "$(jbody "$RG_JSON")" item id)
[[ -n "$RG_ID" ]] && pass "POST /ring-groups -> M1bRingGroup (tashqi a'zo $RGEXT_NUMBER) yaratildi" || fail "POST /ring-groups -> $RG_JSON"
RG_TARGET=$(target_id_by_kind_name ring_group M1bRingGroup)

DID_RG=712099501
RGDID_JSON=$(api POST /inbound-routes "{\"name\":\"M1bRingGroupDid\",\"did\":\"$DID_RG\",\"target_id\":\"$RG_TARGET\",\"enabled\":true}")
RGDID_CODE=$(jcode "$RGDID_JSON"); RGDID_APPLY=$(jget "$(jbody "$RGDID_JSON")" apply status)
[[ "$RGDID_CODE" == "201" && "$RGDID_APPLY" == "applied" ]] && pass "POST /inbound-routes -> $DID_RG (ring group) applied" || fail "POST /inbound-routes $DID_RG -> $RGDID_CODE/$RGDID_APPLY"

# --- Navbat (MOH ssenariysi uchun) ---
# `res_musiconhold` 0 faylli sinfni `moh show classes`da UMUMAN ko'rsatmaydi
# (kutilgan Asterisk xatti-harakati, `app/services/moh.py`da izohlangan) --
# shu sabab KAMIDA bitta audio fayl biriktiriladi.
AUDIO_ID=$(python3 -c "
import json,sys
d=json.load(sys.stdin)
print(d['items'][0]['id'] if d['items'] else '')
" <<<"$(curl -s "$API_BASE/audio" "${AUTH[@]}")")
[[ -n "$AUDIO_ID" ]] && pass "tizim audio namunasi topildi" || fail "tizim audio namunasi topilmadi"
MOH_JSON=$(api POST /moh-classes "{\"name\":\"m1bmoh\",\"shuffle\":false,\"file_ids\":[\"$AUDIO_ID\"]}")
MOH_ID=$(jget "$(jbody "$MOH_JSON")" item id)
[[ -n "$MOH_ID" ]] && pass "POST /moh-classes -> m1bmoh yaratildi" || fail "POST /moh-classes -> $MOH_JSON"
QUEUE_JSON=$(api POST /queues "{\"name\":\"M1bQueue\",\"strategy\":\"ringall\",\"members\":[{\"extension_id\":\"$EXT101_ID\"}],\"timeout_target_id\":\"$HANGUP_TARGET\",\"moh_class_id\":\"$MOH_ID\"}")
QUEUE_ID=$(jget "$(jbody "$QUEUE_JSON")" item id)
[[ -n "$QUEUE_ID" ]] && pass "POST /queues -> M1bQueue (moh_class_id=m1bmoh) yaratildi" || fail "POST /queues -> $QUEUE_JSON"

echo "=== ssenariy 2: xalqaro rad (international=false, hech qanday trunkka INVITE bormaydi) ==="
INTL_SIM=$(curl -s -X POST "$API_BASE/outbound-routes/simulate" "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d "{\"extension\":\"101\",\"number\":\"0044201234567\"}")
INTL_ALLOWED=$(jget "$INTL_SIM" allowed)
[[ "$INTL_ALLOWED" == "False" ]] && pass "ssenariy4/2: simulate 0044201234567 -> allowed=false" || fail "simulate 0044201234567 -> $INTL_SIM"

echo "=== ssenariy 3a: outbound_allowed=false (109) -> simulate rad ==="
BLOCKED_SIM=$(curl -s -X POST "$API_BASE/outbound-routes/simulate" "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d '{"extension":"109","number":"0901234567"}')
BLOCKED_ALLOWED=$(jget "$BLOCKED_SIM" allowed)
BLOCKED_REASON=$(jget "$BLOCKED_SIM" reason)
[[ "$BLOCKED_ALLOWED" == "False" ]] && pass "ssenariy4/3a: simulate (109, outbound_allowed=false) -> allowed=false ($BLOCKED_REASON)" || fail "simulate 109 -> $BLOCKED_SIM"

echo "=== ssenariy 1/4: simulate 101 -> 0901234567 (UZRoute, trunk A->B) ==="
UZ_SIM=$(curl -s -X POST "$API_BASE/outbound-routes/simulate" "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d '{"extension":"101","number":"0901234567"}')
UZ_ALLOWED=$(jget "$UZ_SIM" allowed)
UZ_DIALED=$(jget "$UZ_SIM" dialed)
UZ_ROUTE_NAME=$(jget "$UZ_SIM" route name)
UZ_CALLERID=$(jget "$UZ_SIM" callerid)
UZ_TRUNK0=$(jget "$UZ_SIM" trunks 0 name)
if [[ "$UZ_ALLOWED" == "True" && "$UZ_DIALED" == "998901234567" && "$UZ_ROUTE_NAME" == "M1bUZRoute" && "$UZ_CALLERID" == "999000111" && "$UZ_TRUNK0" == "M1bTrunkA" ]]; then
  pass "ssenariy4/1: simulate 0901234567 -> dialed=998901234567, route=M1bUZRoute, cid=999000111, trunk0=A"
else
  fail "simulate 0901234567 -> $UZ_SIM"
fi

echo "=== ssenariy 3b: simulate 7001234567 (PINRoute, PIN talab qilinadi) ==="
PIN_SIM=$(curl -s -X POST "$API_BASE/outbound-routes/simulate" "${AUTH[@]}" -H 'Content-Type: application/json' \
  -d '{"extension":"101","number":"7001234567"}')
PIN_ROUTE_NAME=$(jget "$PIN_SIM" route name)
[[ "$PIN_ROUTE_NAME" == "M1bPinRoute" ]] && pass "ssenariy4: simulate 7001234567 -> route=M1bPinRoute" || fail "simulate 7001234567 -> $PIN_SIM"

echo "=== HAQIQIY SIP qo'ng'iroqlar (ssenariy 1,2,3,5,9) ==="
if ! command -v docker >/dev/null; then
  fail "docker topilmadi, SIP isbotlari o'tkazib yuborildi"
else
  docker network inspect "$NET" >/dev/null 2>&1 || fail "tarmoq $NET topilmadi"

  docker run -d --name m1b-proof-ext --network "$NET" --ip "$EXT_IP" "$SIPP_IMAGE" sleep infinity >/dev/null
  docker run -d --name m1b-proof-trunka --network "$NET" --ip "$TRUNKA_IP" "$SIPP_IMAGE" sleep infinity >/dev/null
  docker run -d --name m1b-proof-trunkb --network "$NET" --ip "$TRUNKB_IP" "$SIPP_IMAGE" sleep infinity >/dev/null
  docker run -d --name m1b-proof-trunkrg --network "$NET" --ip "$TRUNKRG_IP" "$SIPP_IMAGE" sleep infinity >/dev/null
  docker run -d --name m1b-proof-inbound --network "$NET" --ip "$INBOUND_UAC_IP" "$SIPP_IMAGE" sleep infinity >/dev/null

  docker cp "$SIPP_DIR/outbound_invite.py" m1b-proof-ext:/tmp/outbound_invite.py
  docker cp "$SIPP_DIR/uas_reject.py" m1b-proof-trunka:/tmp/uas_reject.py
  docker cp "$SIPP_DIR/uas_log_and_answer.py" m1b-proof-trunkb:/tmp/uas_log_and_answer.py
  docker cp "$SIPP_DIR/uas_log_and_answer.py" m1b-proof-trunkrg:/tmp/uas_log_and_answer.py

  # MUHIM (jonli isbotda topilgan UCHTA mustaqil sinov-skript xatosi, mahsulot
  # kodida EMAS):
  #   1. `docker logs <konteyner>` FAQAT PID1 (bu yerda `sleep infinity`)
  #      oqimini ko'rsatadi -- `docker exec -d` orqali ishga tushirilgan
  #      JARAYONning stdout/stderr'i UMUMAN unda ko'rinMAYDI. Shu sabab har
  #      bir UAS skripti natijasini konteyner ICHIDAGI faylga (`/tmp/out.log`)
  #      yo'naltirib, keyin `docker exec ... cat` bilan o'qiymiz.
  #   2. Python stdout fayl/pipega yo'naltirilganda (TTY emas) TO'LIQ
  #      BUFERLANADI -- jarayon BYE kutib "osilib qolgan" paytda bufer hali
  #      diskka yozilmagan bo'lishi mumkin. `python3 -u` (unbuffered) bilan
  #      tuzatiladi.
  #   3. Asterisk IP-rejim trunk kontaktini davriy OPTIONS ("qualify") bilan
  #      probe qiladi -- agar probe paytida hali hech kim tinglamagan bo'lsa,
  #      kontakt "Unavailable"ga o'tadi va HAQIQIY Dial() keyinchalik PJSIP
  #      darajasida "Could not create dialog to invalid URI ..." bilan
  #      DARHOL (simdan chiqmasdan) muvaffaqiyatsiz bo'ladi. Tuzatish: har bir
  #      test chaqiruvidan oldin tinglovchini qayta ishga tushirib, DARHOL
  #      `pjsip qualify` buyurtma qilamiz (m1a-proof.sh'dagi bilan bir xil
  #      naqsh); `uas_reject.py`/`uas_log_and_answer.py` endi OPTIONS'larni
  #      200 OK bilan o'zi e'tiborsiz qoldiradi (ikkalasi ham shu segmentda
  #      tuzatildi).
  start_uas() { # container script ip max_seconds
    # Oldingi chaqiruvdan qolgan tinglovchi (agar hali ACK/BYE kutib
    # "osilib" turgan bo'lsa) portni band qilib qolmasin -- yangisini
    # ishga tushirishdan oldin DOIM tozalaymiz ("pkill -x", "-f" EMAS).
    # MUHIM (sinovda topilgan race): shunchaki `pkill` + qattiq `sleep 0.2`
    # YETARLI EMAS -- eski jarayon hali signalni qabul qilib chiqib
    # ulgurmasdan YANGI jarayon `/tmp/out.log`ni TRUNC qilib ochsa, eski
    # jarayonning o'zi ESKI (katta) fayl-offset bilan keyinroq yozishga
    # urinib, NOL-baytlardan iborat "siyrak" (sparse) blok hosil qiladi --
    # natijada keyingi o'qishda yangi jarayonning o'z yozuvi yo'qolib
    # qoladi yoki NUL-bayt ogohlantirishi chiqadi. Shu sabab eski jarayon
    # HAQIQATAN chiqib ketganini (`pgrep` bo'sh natija qaytarguncha) faol
    # kutamiz, qattiq sleep'ga ishonmaymiz.
    docker exec "$1" pkill -x python3 >/dev/null 2>&1 || true
    local waited=0
    while docker exec "$1" pgrep -x python3 >/dev/null 2>&1; do
      sleep 0.1
      waited=$((waited + 1))
      (( waited > 20 )) && break  # ~2s dan keyin voz kechib davom etamiz
    done
    docker exec -d "$1" sh -c "python3 -u /tmp/$2 $3 5060 $4 > /tmp/out.log 2>&1"
  }
  uas_log() { docker exec "$1" cat /tmp/out.log 2>/dev/null; }
  qualify_trunk() { docker exec innova-m0-asterisk-1 asterisk -rx "pjsip qualify t1-trunk-$1" >/dev/null 2>&1; }
  # MUHIM (bu segmentda topilgan va tuzatilgan isbot-skript xatosi, jonli
  # qayta ishlab chiqarish orqali TASDIQLANGAN, 2026-10-28): BITTA
  # `qualify_trunk` chaqiruvi -- OPTIONS'ni FAQAT BIR MARTA jo'natadi.
  # `start_uas` tinglovchini ORQA FONDA (`docker exec -d`) qayta ishga
  # tushiradi va DARHOL qaytadi -- yangi `python3` jarayoni UDP socket'ni
  # BOG'LAGUNCHA (interpreter ishga tushishi + import, odatda o'nlab
  # millisekund, lekin `--fresh` davomidagi yuklama ostida ko'proq cho'zilishi
  # mumkin) o'tgan BIRDAN-BIR OPTIONS probe portga YETIB BORMAYDI (ICMP
  # port-unreachable/yo'qolish) va Asterisk kontaktni "Unavail" deb
  # BELGILAB QO'YADI -- keyingi `qualify_frequency` (30s) gacha QAYTA
  # TEKSHIRILMAYDI. Shunchaki kontakt holatini PASSIV kutish (bitta qualify
  # + status pollash) YETARLI EMAS -- kontakt hali "Unavail" bo'lib qolaveradi,
  # Dial() keyin "Could not create dialog to invalid URI" bilan
  # muvaffaqiyatsiz tugaydi (hatto PIN TO'G'RI tekshirilgan bo'lsa ham).
  # Tuzatish: har bir pollash iteratsiyasida QAYTA `qualify_trunk` chaqiramiz
  # (passiv kutish o'rniga FAOL qayta-probe) -- tinglovchi ulgurib
  # bog'langanidan keyingi birinchi probe muvaffaqiyatli bo'ladi.
  wait_for_aor_avail() { # trunk_id max_seconds
    # MUHIM (bu segmentda topilgan, YUQORIDAGI izohdagi gipotezani
    # TUZATGAN kashfiyot): har pollash iteratsiyasida QAYTA `qualify_trunk`
    # chaqirish (ilk urinish) YANADA YOMONLASHTIRDI -- `pjsip qualify` CLI
    # buyrug'i ASINXRON (OPTIONS javobini KUTMAY qaytadi); uni tez-tez
    # (0.1s'da) qayta chaqirish HAR SAFAR oldingi probe'ni besh baridan
    # TUGATILMAY qoldirib, holatni "NonQual"da MANGU osilib qolishiga olib
    # keldi (jonli qayta ishlab chiqarishda tasdiqlangan: 30 marta qayta
    # probe qilingandan keyin ham "NonQual", hech qachon "Avail"GA
    # O'TMAGAN). Tuzatish: FAQAT BITTA probe'ni (chaqiruvchi tomonidan
    # oldin, bir marta) BOSHLASH VAQTINI BERAMIZ -- bu funksiya endi
    # shunchaki PASSIV kutadi (status "Avail" bo'lguncha), qayta
    # qualify ChaqirMAYDI.
    local tries=$(( ${2:-3} * 10 )) i=0
    while (( i < tries )); do
      docker exec innova-m0-asterisk-1 asterisk -rx "pjsip show aor t1-trunk-$1" 2>/dev/null | grep -q "Avail" && return 0
      sleep 0.1
      i=$((i + 1))
    done
    return 1
  }
  # UAS jurnali kutilgan naqshni yozguncha qisqa intervalda qayta o'qiymiz
  # (chaqiruv TUGAgani UAS jurnalining DISKKA to'liq yozilgani bilan BIR
  # xil lahza ekanligiga kafolat yo'q -- qattiq `sleep`ga ishonmaymiz).
  wait_for_uas_log() { # container pattern max_seconds
    local out="" i=0 tries=$(( ${3:-3} * 10 ))
    while (( i < tries )); do
      out=$(uas_log "$1")
      echo "$out" | grep -q "$2" && { echo "$out"; return 0; }
      sleep 0.1
      i=$((i + 1))
    done
    echo "$out"
  }

  REG_OUT=$(docker exec -i m1b-proof-ext python3 - 101 "$EXT101_SECRET" 5090 <<'PYEOF'
import sys
sys.path.insert(0, "/tmp")
from outbound_invite import OutboundCaller
c = OutboundCaller("asterisk", 5060, int(sys.argv[3]), sys.argv[1], sys.argv[2])
ok = c.register()
print("REGISTER_RESULT:", "OK" if ok else "FAIL")
c.close()
PYEOF
)
  if echo "$REG_OUT" | grep -q "REGISTER_RESULT: OK"; then
    pass "REGISTER 101 -> 200 OK"
  else
    fail "REGISTER 101 muvaffaqiyatsiz: $REG_OUT"
  fi
  sleep 1

  echo "--- ssenariy 1: 101 -> 0901234567, trunk A 503, trunk B javob beradi ---"
  start_uas m1b-proof-trunka uas_reject.py "$TRUNKA_IP" 20
  start_uas m1b-proof-trunkb uas_log_and_answer.py "$TRUNKB_IP" 20
  sleep 0.5
  qualify_trunk "$TRUNKA_ID"; qualify_trunk "$TRUNKB_ID"
  sleep 0.5
  S1_OUT=$(docker exec m1b-proof-ext python3 /tmp/outbound_invite.py asterisk 5060 5091 101 "$EXT101_SECRET" 0901234567 --hold-ms 1500 --no-register 2>&1)
  echo "$S1_OUT" | grep -q "FINAL: 200" && pass "ssenariy1: INVITE 0901234567 -> 200 OK (trunk B javob berdi)" || { fail "ssenariy1: kutilmagan natija"; echo "$S1_OUT"; }
  TRUNKB_LOG=$(wait_for_uas_log m1b-proof-trunkb "REQUEST_LINE" 3)
  if echo "$TRUNKB_LOG" | grep -q "998901234567"; then
    pass "ssenariy1: UAS B Request-URI'da 998901234567 (prefiks qo'shilgan)"
  else
    fail "ssenariy1: UAS B Request-URI'da 998901234567 topilmadi"; echo "$TRUNKB_LOG"
  fi
  if echo "$TRUNKB_LOG" | grep -q "999000111"; then
    pass "ssenariy1: UAS B From/PAI'da marshrut CallerID (999000111) ko'rinadi"
  else
    fail "ssenariy1: UAS B From/PAI'da 999000111 topilmadi"; echo "$TRUNKB_LOG"
  fi
  # direction — xom CDR ustuni EMAS (API darajasida channel/dstchannel'dan
  # hisoblanadi, `app/services/call_direction.py`); chiquvchi qo'ng'iroqda
  # `userfield` = HAQIQIY ishlatilgan trunk NOMI (`compiler.py`
  # `Set(CDR(userfield)={trunk.name})`, failover bo'lsa HAR trunk urinishidan
  # oldin qayta yoziladi -- shu sabab oxirgi (muvaffaqiyatli) urinish nomi
  # qoladi).
  S1_CDR=$(wait_for_sql \
    "select userfield, dstchannel, disposition from cdr where dst='0901234567' and disposition='ANSWERED' order by calldate desc limit 1" 6)
  if echo "$S1_CDR" | grep -qi "M1bTrunkB" && echo "$S1_CDR" | grep -qi "ANSWERED"; then
    pass "ssenariy1: CDR userfield(trunk)=M1bTrunkB, ANSWERED ($S1_CDR)"
  else
    fail "ssenariy1: CDR kutilgan shaklda emas ($S1_CDR)"
  fi

  echo "--- ssenariy 2: 101 -> 0044201234567 (xalqaro rad, 0 INVITE trunkka) ---"
  start_uas m1b-proof-trunka uas_reject.py "$TRUNKA_IP" 8
  start_uas m1b-proof-trunkb uas_log_and_answer.py "$TRUNKB_IP" 8
  sleep 0.5
  qualify_trunk "$TRUNKA_ID"; qualify_trunk "$TRUNKB_ID"
  sleep 0.3
  S2_OUT=$(docker exec m1b-proof-ext python3 /tmp/outbound_invite.py asterisk 5060 5092 101 "$EXT101_SECRET" 0044201234567 --hold-ms 500 --no-register 2>&1)
  echo "$S2_OUT" | grep -qE "FINAL: (4|5)[0-9][0-9]" && pass "ssenariy2: INVITE 0044201234567 -> rad etildi (${S2_OUT##*FINAL: })" || { fail "ssenariy2: kutilmagan natija"; echo "$S2_OUT"; }
  # MUHIM (bu segmentda jonli isbotda topilgan poyga -- test-skript xatosi,
  # mahsulot EMAS): `uas_reject.py`/`uas_log_and_answer.py` ichidagi
  # `socket.settimeout(8)` HAR bir `recvfrom()` chaqiruvidan boshlab qayta
  # sanaladi -- oxirgi qabul qilingan paket (qualify OPTIONS, taxminan shu
  # yerdan ~0.8s oldin) dan 8s keyin "TIMEOUT" yoziladi. Avvalgi `sleep 7`
  # bu bilan <1s farq bilan POYGA qilardi (host/docker exec kechikishiga
  # qarab "TIMEOUT" hali yozilmagan bo'lishi mumkin edi) -- shu sabab
  # xavfsiz zahira bilan 9s kutamiz.
  sleep 9
  TRUNKA_LOG2=$(uas_log m1b-proof-trunka)
  TRUNKB_LOG2=$(uas_log m1b-proof-trunkb)
  if echo "$TRUNKA_LOG2" | grep -q "TIMEOUT" && echo "$TRUNKB_LOG2" | grep -q "TIMEOUT"; then
    pass "ssenariy2: trunk A va B'ga HECH QANDAY INVITE kelmadi (0 INVITE)"
  else
    fail "ssenariy2: trunk(lar)ga kutilmagan INVITE keldi"; echo "A: $TRUNKA_LOG2"; echo "B: $TRUNKB_LOG2"
  fi
  S2_CDR=$(wait_for_sql \
    "select disposition from cdr where dst='0044201234567' order by calldate desc limit 1" 6)
  if [[ -n "$S2_CDR" ]] && ! echo "$S2_CDR" | grep -qi "ANSWERED"; then
    pass "ssenariy2: CDR disposition!=ANSWERED ($S2_CDR)"
  else
    fail "ssenariy2: CDR kutilmagan ($S2_CDR)"
  fi

  echo "--- ssenariy 3: PIN marshrut (xato PIN rad, to'g'ri PIN o'tadi) ---"
  # MUHIM (bu segmentda aniqlangan va TUZATILGAN mahsulot xatosi):
  # ILGARI `Read(INNOVA_PIN,beep,8)` mavjud bo'lmagan "beep" tovush faylini
  # ishlatardi -- `ast_app_getdata_terminator()` fayl topilmasa raqam terish
  # tsikliga UMUMAN kirmasdan "User disconnected" bilan chiqib ketardi, PIN
  # (to'g'ri yoki xato) hech qachon tekshirilmasdi. `compiler.py`da
  # `Read(INNOVA_PIN,,8)` (bo'sh fayl nomi) bilan tuzatildi. Haqiqiy signal --
  # trunk B'ga INVITE BORDI/BORMADI (PIN qabul qilinsagina Dial()
  # chaqiriladi, aks holda Congestion()+Hangup()). "#" -- Read()ning
  # standart terminatori. `outbound_invite.py`dagi CSeq-tartib va
  # raqamlar orasidagi tanaffus xatolari ham shu segmentda tuzatildi
  # (isbot-skript darajasida, mahsulot kodida EMAS) -- tafsilotlar
  # o'sha fayldagi izohlarda.
  start_uas m1b-proof-trunkb uas_log_and_answer.py "$TRUNKB_IP" 4
  sleep 0.5
  qualify_trunk "$TRUNKB_ID"
  wait_for_aor_avail "$TRUNKB_ID" 3
  S3W_OUT=$(docker exec m1b-proof-ext python3 /tmp/outbound_invite.py asterisk 5060 5093 101 "$EXT101_SECRET" 7001234567 --dtmf "9999#" --hold-ms 1000 --no-register 2>&1)
  TRUNKB_LOG3W=$(wait_for_uas_log m1b-proof-trunkb "TIMEOUT\|REQUEST_LINE" 5)
  if echo "$TRUNKB_LOG3W" | grep -q "TIMEOUT"; then
    pass "ssenariy3: xato PIN (9999) bilan trunk B'ga INVITE bormadi (rad etildi)"
  else
    fail "ssenariy3: xato PIN bilan ham trunk B'ga INVITE keldi (kutilmagan)"; echo "$TRUNKB_LOG3W"; echo "$S3W_OUT"
  fi

  # MUHIM (bu segmentda jonli qayta ishlab chiqarish orqali TOPILGAN
  # ikkinchi, chuqurroq race): hatto BITTA `qualify_trunk` + passiv
  # "Avail" kutish ham ba'zan YETARLI EMAS -- AOR holati "NonQual"da
  # (hali birorta probe tsikli TUGAMAGAN) qolib ketishi mumkin, chunki
  # trunk B kontakti ssenariy 1'da ALLAQACHON bir marta qualify qilingan
  # va PJSIP'ning o'z AVTOMATIK `qualify_frequency=30s` taymeri shu payt
  # atrofida qayta ishga tushishi mumkin -- bizning QO'LDA chaqirgan
  # probe bilan TO'QNASHIB, ikkalasi ham to'liq tugamay qolishi mumkin
  # (shu segmentda aniqlangan: qayta-qayta `qualify_trunk` chaqirish
  # buni YANADA yomonlashtiradi -- har bir yangi chaqiruv avvalgi
  # probe'ni tugamay qoldiradi). Buning o'rniga butun urinishni (yangi
  # tinglovchi + qualify + INVITE) CHEKLANGAN marta QAYTA SINAYMIZ --
  # UAS jurnali "REQUEST_LINE" ko'rsatguncha (jonli SIP sinovidagi
  # vaqt o'zgaruvchanligiga qarshi standart, mavjud `wait_for_*` naqshlar
  # bilan BIR XIL g'oyadagi chidamlilik choras).
  TRUNKB_LOG3C=""
  for attempt in 1 2 3; do
    start_uas m1b-proof-trunkb uas_log_and_answer.py "$TRUNKB_IP" 10
    sleep 0.5
    qualify_trunk "$TRUNKB_ID"
    wait_for_aor_avail "$TRUNKB_ID" 3
    S3C_OUT=$(docker exec m1b-proof-ext python3 /tmp/outbound_invite.py asterisk 5060 "$((5093 + attempt))" 101 "$EXT101_SECRET" 7001234567 --dtmf "1357#" --hold-ms 2000 --no-register 2>&1)
    TRUNKB_LOG3C=$(wait_for_uas_log m1b-proof-trunkb "REQUEST_LINE" 5)
    echo "$TRUNKB_LOG3C" | grep -q "REQUEST_LINE" && break
    echo "ssenariy3: urinish $attempt muvaffaqiyatsiz (NonQual/CHANUNAVAIL ehtimoli) -- qayta urinamiz"
  done
  if echo "$TRUNKB_LOG3C" | grep -q "REQUEST_LINE"; then
    pass "ssenariy3: to'g'ri PIN (1357) bilan trunk B'ga INVITE bordi (o'tdi)"
  else
    fail "ssenariy3: to'g'ri PIN bilan trunk B'ga INVITE kelmadi"; echo "$TRUNKB_LOG3C"; echo "$S3C_OUT"
  fi

  echo "--- ssenariy 5: ring group tashqi a'zo -> kiruvchi DID -> tashqi raqam trunk orqali terildi ---"
  start_uas m1b-proof-trunkrg uas_log_and_answer.py "$TRUNKRG_IP" 20
  sleep 0.5
  qualify_trunk "$TRUNKRG_ID"
  sleep 0.3
  docker cp "$SIPP_DIR/outbound_invite.py" m1b-proof-inbound:/tmp/outbound_invite.py
  INBOUND_OUT=$(docker exec -i m1b-proof-inbound python3 - "$DID_RG" <<'PYEOF'
import sys
sys.path.insert(0, "/tmp")
from outbound_invite import OutboundCaller
c = OutboundCaller("asterisk", 5060, 5095, "trunk-caller", "unused")
try:
    import time
    responses = c.invite(sys.argv[1])
    final = responses[-1] if responses else "SIP/2.0 000 NO_RESPONSE"
    print("INVITE_FINAL:", final.splitlines()[0])
    code = int(final.split(" ", 2)[1])
    if code == 200:
        c.ack()
        time.sleep(3)
        c.bye()
finally:
    c.close()
PYEOF
)
  echo "$INBOUND_OUT" | grep -q "INVITE_FINAL: SIP/2.0 200" && pass "ssenariy5: kiruvchi $DID_RG -> ring group -> 200 OK" || { fail "ssenariy5: kiruvchi $DID_RG natijasi kutilmagan"; echo "$INBOUND_OUT"; }
  TRUNKRG_LOG=$(wait_for_uas_log m1b-proof-trunkrg "REQUEST_LINE" 3)
  echo "$TRUNKRG_LOG" | grep -q "$RGEXT_NUMBER" && pass "ssenariy5: tashqi a'zo UAS INVITE oldi (Request-URI=$RGEXT_NUMBER)" || { fail "ssenariy5: tashqi a'zo UAS INVITE olmadi"; echo "$TRUNKRG_LOG"; }

  echo "--- ssenariy 9: MOH -- navbatga biriktirilgan sinf Asterisk'da ko'rinadi ---"
  # Asterisk'dagi haqiqiy sinf nomi `t1-moh-<moh_id>` (asterisk_class_name(),
  # "m1bmoh" faqat API darajasidagi ko'rsatma nom, Asterisk CLI'da ko'rinmaydi).
  MOH_ASTERISK_NAME="t1-moh-$MOH_ID"
  MOH_SHOW=$(docker exec innova-m0-asterisk-1 asterisk -rx "moh show classes" 2>&1)
  echo "$MOH_SHOW" | grep -qi "$MOH_ASTERISK_NAME" && pass "ssenariy9: 'moh show classes' -> $MOH_ASTERISK_NAME ko'rinadi" || { fail "ssenariy9: $MOH_ASTERISK_NAME 'moh show classes'da topilmadi"; echo "$MOH_SHOW"; }
  # MUHIM: `queue show` CLI format'ida musicclass UMUMAN chiqarilmaydi (Asterisk
  # standart xatti-harakati) -- shu sabab haqiqiy realtime qiymatni `realtime
  # load queues name <queue>` orqali tekshiramiz (bu segmentda aniqlangan
  # isbot-skript xatosi, mahsulot kodida EMAS: wiring `realtime load`da
  # musicclass=$MOH_ASTERISK_NAME ekani to'g'ridan-to'g'ri tasdiqlangan).
  QUEUE_SHOW=$(docker exec innova-m0-asterisk-1 asterisk -rx "realtime load queues name t1-q-$QUEUE_ID" 2>&1)
  echo "$QUEUE_SHOW" | grep -qi "musicclass.*$MOH_ASTERISK_NAME" && pass "ssenariy9: navbat realtime musicclass=$MOH_ASTERISK_NAME" || { fail "ssenariy9: navbatning musicclass'i $MOH_ASTERISK_NAME emas"; echo "$QUEUE_SHOW"; }
fi

echo "=== ssenariy 6: revision restore (A -> B -> A, dialplan matni + audit) ==="
HEALTH_A=$(curl -s "$API_BASE/system/health" "${AUTH[@]}")
REV_A=$(jget "$HEALTH_A" revision)
[[ -n "$REV_A" && "$REV_A" != "None" ]] && pass "ssenariy6: revision A (=$REV_A) topildi" || fail "ssenariy6: revision A topilmadi ($HEALTH_A)"

# MUHIM: faqat ring group QATORI yaratish YETARLI EMAS -- `compiler.py`
# `_all_dest_ids()` faqat BOSHQA narsa (inbound route/IVR/boshqa) ANIQ
# ishora qilgan target_id'lar uchun `[t1-dest-*]` kontekst yozadi; hech kim
# ishora qilmagan "yetim" obyekt dialplan matnini UMUMAN o'zgartirmaydi
# (to'g'ri — kerak bo'lmagan narsa kompilyatsiya qilinmaydi), shuning uchun
# B holatni KAFOLATLI o'zgartirish uchun YANGI KIRUVCHI MARSHRUT (DID)
# qo'shiladi -- bu har doim `[t1-from-trunk]` matnini o'zgartiradi.
DID_PROBE=712099601
NEWROUTE_JSON=$(api POST /inbound-routes "{\"name\":\"M1bRevisionProbe\",\"did\":\"$DID_PROBE\",\"target_id\":\"$HANGUP_TARGET\",\"enabled\":true}")
NEWROUTE_ID=$(jget "$(jbody "$NEWROUTE_JSON")" item id)
[[ -n "$NEWROUTE_ID" ]] && pass "ssenariy6: B holat uchun yangi kiruvchi marshrut ($DID_PROBE) yaratildi" || fail "ssenariy6: B holat yaratilmadi ($NEWROUTE_JSON)"

HEALTH_B=$(curl -s "$API_BASE/system/health" "${AUTH[@]}")
REV_B=$(jget "$HEALTH_B" revision)
[[ -n "$REV_B" && "$REV_B" != "$REV_A" ]] && pass "ssenariy6: revision B (=$REV_B) != A" || fail "ssenariy6: revision B kutilmagan ($HEALTH_B)"

DIALPLAN_B=$(docker exec innova-m0-asterisk-1 asterisk -rx "dialplan show t1-from-trunk" 2>&1)
echo "$DIALPLAN_B" | grep -q "$DID_PROBE" && pass "ssenariy6: dialplan B holatda $DID_PROBE DID'ini o'z ichiga oladi" || fail "ssenariy6: dialplan B holatda kutilgan DID'ni topmadi"

RESTORE_JSON=$(api POST "/config/revisions/$REV_A/restore" '{}')
RESTORE_CODE=$(jcode "$RESTORE_JSON")
[[ "$RESTORE_CODE" == "200" ]] && pass "ssenariy6: POST /config/revisions/$REV_A/restore -> 200" || fail "ssenariy6: restore -> $RESTORE_JSON"

DIALPLAN_RESTORED=$(docker exec innova-m0-asterisk-1 asterisk -rx "dialplan show t1-from-trunk" 2>&1)
if ! echo "$DIALPLAN_RESTORED" | grep -q "$DID_PROBE"; then
  pass "ssenariy6: restore'dan keyin dialplan A matnini ko'rsatadi ($DID_PROBE YO'Q)"
else
  fail "ssenariy6: restore'dan keyin dialplan hali B holatda ($DID_PROBE bor)"
fi

AUDIT_RESTORE=$(curl -s "$API_BASE/audit?entity=config_revision&action=restore" "${AUTH[@]}")
AUDIT_FOUND=$(python3 -c "
import json,sys
d=json.load(sys.stdin)
print('yes' if any(i.get('entity_id')=='$REV_A' for i in d.get('items',[])) else 'no')
" <<<"$AUDIT_RESTORE")
[[ "$AUDIT_FOUND" == "yes" ]] && pass "ssenariy6: audit jurnalida restore (entity_id=$REV_A) bor" || fail "ssenariy6: audit jurnalida restore topilmadi ($AUDIT_RESTORE)"

echo "=== ssenariy 7: register-trunk -> health.registration=registered ==="
REGTRUNK_JSON=$(api POST /trunks "{\"name\":\"M1bRegTrunk\",\"host\":\"$REGTRUNK_IP\",\"port\":5060,\"auth_mode\":\"register\",\"username\":\"m1breguser\",\"password\":\"m1bregpass123\",\"codecs\":[\"ulaw\"],\"max_channels\":5,\"enabled\":true}")
REGTRUNK_ID=$(jget "$(jbody "$REGTRUNK_JSON")" item id)
[[ -n "$REGTRUNK_ID" ]] && pass "ssenariy7: POST /trunks -> M1bRegTrunk (register) yaratildi" || fail "ssenariy7: POST /trunks RegTrunk -> $REGTRUNK_JSON"

if [[ -n "$REGTRUNK_ID" ]] && command -v docker >/dev/null; then
  docker run -d --name m1b-proof-regtrunk --network "$NET" --ip "$REGTRUNK_IP" "$SIPP_IMAGE" sleep infinity >/dev/null
  docker cp "$SIPP_DIR/test_registrar.py" m1b-proof-regtrunk:/tmp/test_registrar.py
  docker exec -d m1b-proof-regtrunk sh -c "python3 -u /tmp/test_registrar.py $REGTRUNK_IP 5060 30 > /tmp/out.log 2>&1"
  sleep 0.5
  # MUHIM (bu segmentda topilgan, isbot-skript xatosi): trunk API orqali
  # yaratilgandayoq Asterisk DARHOL o'zining birinchi REGISTER urinishini
  # qiladi -- bu paytda soxta registrar HALI tinglamagan bo'ladi, shuning
  # uchun registratsiya "Rejected"ga o'tib, Asterisk keyingi urinishni
  # FAQAT `retry_interval` (60s) dan keyin qiladi -- bizning qisqa kutish
  # oynamiz (oldin 10x2=20s) hech qachon yetarli bo'lmaydi. Tuzatish:
  # `pjsip send register <registration-id>` bilan DARHOL majburiy qayta
  # registratsiya (m1a-proof.sh/qualify_trunk bilan BIR XIL naqsh);
  # registration-id -- `t1-trunk-<id>` (username "m1breguser" EMAS).
  docker exec innova-m0-asterisk-1 asterisk -rx "pjsip send register t1-trunk-$REGTRUNK_ID" >/dev/null 2>&1 || true
  sleep 3
  for i in $(seq 1 10); do
    TRUNK_HEALTH=$(curl -s "$API_BASE/trunks" "${AUTH[@]}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
items=[i for i in d['items'] if i['name']=='M1bRegTrunk']
print(items[0]['health']['registration'] if items else '')
")
    [[ "$TRUNK_HEALTH" == "registered" ]] && break
    sleep 2
  done
  [[ "$TRUNK_HEALTH" == "registered" ]] && pass "ssenariy7: GET /trunks -> M1bRegTrunk health.registration=registered" || fail "ssenariy7: health.registration=$TRUNK_HEALTH (registered kutilgan)"
fi

echo "=== ssenariy 8: audit -- parol o'zgartirish '***' bilan maskalanadi ==="
if [[ -n "$REGTRUNK_ID" ]]; then
  REGTRUNK_GET=$(curl -s "$API_BASE/trunks" "${AUTH[@]}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
items=[i for i in d['items'] if i['id']=='$REGTRUNK_ID']
print(items[0]['updated_at'] if items else '')
")
  NEWPASS="m1bSuperSecret987"
  UPD_JSON=$(api PATCH "/trunks/$REGTRUNK_ID" "{\"password\":\"$NEWPASS\",\"updated_at\":\"$REGTRUNK_GET\"}")
  UPD_CODE=$(jcode "$UPD_JSON")
  [[ "$UPD_CODE" == "200" ]] && pass "ssenariy8: PATCH /trunks/{id} parol yangilandi (200)" || fail "ssenariy8: parol yangilash -> $UPD_JSON"

  AUDIT_PW=$(curl -s "$API_BASE/audit?entity=trunk&q=$REGTRUNK_ID" "${AUTH[@]}")
  AUDIT_MASKED=$(python3 -c "
import json,sys
d=json.load(sys.stdin)
rows=[i for i in d.get('items',[]) if i.get('entity_id')=='$REGTRUNK_ID' and i.get('diff',{}).get('password')]
print(rows[0]['diff']['password'] if rows else 'NOTFOUND')
" <<<"$AUDIT_PW")
  [[ "$AUDIT_MASKED" == "***" ]] && pass "ssenariy8: audit_log.diff.password = '***' (maskalangan)" || fail "ssenariy8: audit_log.diff.password = '$AUDIT_MASKED' (kutilgan '***')"

  PLAINTEXT_IN_AUDIT=$(docker exec innova-m0-postgres-1 psql -U innova -d innova -tAc \
    "select count(*) from audit_log where diff::text like '%$NEWPASS%'")
  [[ "${PLAINTEXT_IN_AUDIT:-1}" -eq 0 ]] && pass "ssenariy8: ochiq parol audit_log bazasida YO'Q" || fail "ssenariy8: ochiq parol audit_log'da topildi!"

  PLAINTEXT_IN_TRUNK=$(docker exec innova-m0-postgres-1 psql -U innova -d innova -tAc \
    "select count(*) from trunks where password_enc like '%$NEWPASS%'")
  [[ "${PLAINTEXT_IN_TRUNK:-1}" -eq 0 ]] && pass "ssenariy8: ochiq parol trunks.password_enc'da YO'Q (shifrlangan)" || fail "ssenariy8: ochiq parol trunks jadvalida topildi!"
fi

echo "=== ssenariy10: SIP/RTP sozlamalari (S32) ==="
ast() { docker exec innova-m0-asterisk-1 asterisk -rx "$1" 2>/dev/null; }
uptime_s() { ast "core show uptime seconds" | sed -n 's/System uptime: *\([0-9]*\).*/\1/p'; }
sip_patch() { api PATCH /settings/sip "{\"item\":$1,\"apply\":true}"; }
# Sehrgar local_nets'i image standartidan (BOOT_DEFAULT) farq qiladi -> restart_required sehrgardan beri.
R=$(api GET /settings/sip)
[[ "$(jget "$(jbody "$R")" restart_required)" == "True" ]] \
  && pass "ssenariy10: sehrgar tarmog'i standartdan farqli -> restart_required" || fail "ssenariy10: sehrgardan keyin GET -> $R"
UP0=$(uptime_s)
R=$(sip_patch '{"rtp_start":12000,"rtp_end":12999}')
[[ "$(jcode "$R")" == "200" ]] && pass "ssenariy10: RTP PATCH -> 200" || fail "ssenariy10: RTP PATCH -> $R"
RTP_OUT=$(ast "rtp show settings")
grep -q "Port start: *12000" <<<"$RTP_OUT" && grep -q "Port end: *12999" <<<"$RTP_OUT" \
  && pass "ssenariy10: rtp show settings -> 12000-12999" || fail "ssenariy10: rtp show settings -> $RTP_OUT"
UP1=$(uptime_s)
[[ -n "$UP0" && -n "$UP1" && "$UP1" -ge "$UP0" ]] && pass "ssenariy10: RTP uchun restart bo'lmadi (uptime $UP0 -> $UP1)" \
  || fail "ssenariy10: RTP o'zgarishida uptime $UP0 -> $UP1"

R=$(sip_patch '{"external_ip":"203.0.113.7"}')
[[ "$(jget "$(jbody "$R")" apply status)" == "restart_required" && "$(jget "$(jbody "$R")" item restart_required)" == "True" ]] \
  && pass "ssenariy10: tashqi IP -> restart_required" || fail "ssenariy10: tashqi IP PATCH -> $R"
docker exec innova-m0-asterisk-1 grep -q "external_signaling_address = 203.0.113.7" /srv/dialplan/pjsip_transports_innova.conf \
  && pass "ssenariy10: transport fayli yangi IP bilan yozildi" || fail "ssenariy10: transport faylida 203.0.113.7 yo'q"

ast "channel originate Local/700@parkedcalls application Wait 30" >/dev/null
sleep 1
R=$(api POST /settings/sip/restart)
[[ "$(jcode "$R")" == "409" && "$(jget "$(jbody "$R")" error code)" == "active_calls" ]] \
  && pass "ssenariy10: faol qo'ng'iroqda restart -> 409 active_calls" || fail "ssenariy10: faol qo'ng'iroqda restart -> $R"
ast "channel request hangup all" >/dev/null
sleep 1

UP2=$(uptime_s)
R=$(api POST /settings/sip/restart)
[[ "$(jcode "$R")" == "200" ]] && pass "ssenariy10: restart -> 200" || fail "ssenariy10: restart -> $R"
UP3=$(uptime_s)
[[ -n "$UP3" && -n "$UP2" && "$UP3" -lt "$UP2" ]] && pass "ssenariy10: Asterisk haqiqatan qayta ishga tushdi (uptime $UP2 -> $UP3)" \
  || fail "ssenariy10: uptime $UP2 -> $UP3"
ast "pjsip show transport transport-udp" | grep -q "external_signaling_address *: *203.0.113.7" \
  && pass "ssenariy10: transport-udp external_signaling_address=203.0.113.7" || fail "ssenariy10: transport'da tashqi IP yo'q"
R=$(api GET /settings/sip)
[[ "$(jget "$(jbody "$R")" restart_required)" == "False" ]] && pass "ssenariy10: restart_required tozalandi" || fail "ssenariy10: GET -> $R"
AUD=$(curl -s "$API_BASE/audit?entity=sip_settings&action=restart" "${AUTH[@]}")
[[ "$(jget "$AUD" total)" -ge 1 ]] && pass "ssenariy10: audit'da restart yozuvi bor" || fail "ssenariy10: audit -> $AUD"

R=$(sip_patch '{"external_ip":null}')
[[ "$(jget "$(jbody "$R")" item external_ip)" == "" ]] && pass "ssenariy10: external_ip null bilan tozalandi" || fail "ssenariy10: tozalash -> $R"

echo
echo "=== NATIJA: PASS=$PASS FAIL=$FAIL ==="
[[ "$FAIL" -eq 0 ]]
