# shellcheck shell=bash
# M2c §5 — ssenariy 7: trunk monitoringi fon vazifasi (`app/services/
# trunk_monitor.py`). FAQAT register-rejim trunk ishlatiladi — `ip` rejim
# trunk uchun jonli signal manbai yo'q (passiv qualify, `trunk_health.py`
# BOSHQA agent ishi, SHU PROOFDA tekshirilmaydi, M2c-contract.md'da ochiq
# muammo sifatida qoldirilgan). `scripts/m2c-proof.sh` DAVOM ETTIRADI —
# umumiy o'zgaruvchilar: API_BASE, NET, SIPP_IMAGE, SIPP_DIR, CONTAINERS,
# AST(=innova-m0-asterisk-1), api/jget/jbody/jcode/check/pass/fail/wait_until,
# tg_is_decoded/tg_count_decoded (m1b-proof.sh'dagi register-trunk qolipi
# BILAN BIR XIL — dryer: isbotlangan naqsh qayta ishlatildi).
TM_IP="172.28.0.205"  # register-rejim trunk peer (EXT/TRUNK/TG/SG_*dan ALOHIDA)

TM_TRUNK_J=$(api POST /trunks "{\"name\":\"M2cRegTrunk\",\"host\":\"$TM_IP\",\"port\":5060,\"auth_mode\":\"register\",\"username\":\"m2cregtrunk\",\"password\":\"M2cRegTrunkPass123\",\"codecs\":[\"ulaw\"],\"max_channels\":5,\"enabled\":true}")
TM_TRUNK_ID=$(jget "$(jbody "$TM_TRUNK_J")" item id)
check "$( [[ -n "$TM_TRUNK_ID" ]]; echo $?)" "7: POST /trunks -> M2cRegTrunk (register) yaratildi" "$TM_TRUNK_J"

tm_registration() { # -> stdout: health.registration ("registered"/"rejected"/...)
  jbody "$(api GET /trunks)" | python3 -c "
import json,sys
d=json.load(sys.stdin)
items=[i for i in d['items'] if i['id']=='$TM_TRUNK_ID']
print(items[0]['health']['registration'] if items else '')"
}
tm_is_registered() { [[ "$(tm_registration)" == "registered" ]]; }

if [[ -n "$TM_TRUNK_ID" ]] && command -v docker >/dev/null; then
  CONTAINERS+=(m2c-proof-regtrunk)
  docker run -d --name m2c-proof-regtrunk --network "$NET" --ip "$TM_IP" "$SIPP_IMAGE" sleep infinity >/dev/null
  docker cp "$SIPP_DIR/test_registrar.py" m2c-proof-regtrunk:/tmp/test_registrar.py
  docker exec -d m2c-proof-regtrunk sh -c "python3 -u /tmp/test_registrar.py $TM_IP 5060 60 > /tmp/out.log 2>&1"
  sleep 0.5
  # m1b-proof.sh'da topilgan: trunk yaratilgandayoq Asterisk DARHOL birinchi
  # REGISTER urinishini qiladi (soxta registrar hali tinglamagan bo'ladi) va
  # keyingi urinishni FAQAT retry_interval'dan keyin qiladi — shu sabab
  # `pjsip send register` bilan DARHOL majburiy qayta registratsiya.
  docker exec "$AST" asterisk -rx "pjsip send register t1-trunk-$TM_TRUNK_ID" >/dev/null 2>&1 || true
  wait_until 20 tm_is_registered
  check "$(tm_is_registered; echo $?)" "7: M2cRegTrunk <=20s ichida registered holatiga o'tdi" "$(tm_registration)"

  # Fon vazifaning OWN jarayon-xotirasidagi `last_state` kamida bir marta
  # "ok" sifatida kuzatishi SHART (birinchi kuzatuv HECH QACHON ogohlantirmaydi,
  # `transition_kind(None, _) -> None`) — TRUNK_MONITOR_INTERVAL_S qisqa bo'lsa
  # ham bir nechta aylanish uchun zahira bilan kutamiz.
  sleep 8

  echo "--- 7: trunk peer konteyner to'xtatilgan -> trunk_down ---"
  docker stop m2c-proof-regtrunk >/dev/null 2>&1
  docker exec "$AST" asterisk -rx "pjsip send register t1-trunk-$TM_TRUNK_ID" >/dev/null 2>&1 || true

  wait_until 40 tg_is_decoded "M2cRegTrunk» ishlamayapti" 1
  check "$(tg_is_decoded "M2cRegTrunk» ishlamayapti" 1; echo $?)" \
    "7: Telegram'ga trunk_down ogohlantirishi keldi (M2cRegTrunk)" "$(tg_count_decoded "M2cRegTrunk» ishlamayapti")"

  TM_EV_J=$(api "GET" "/alerts?kind=trunk_down&limit=20")
  check "$(echo "$(jbody "$TM_EV_J")" | python3 -c "
import json,sys
d=json.load(sys.stdin)
sys.exit(0 if any(i['key']=='$TM_TRUNK_ID' and i['status']=='sent' for i in d['items']) else 1)"; echo $?)" \
    "7: GET /alerts kind=trunk_down -> M2cRegTrunk uchun 'sent' yozuvi bor" "$(jbody "$TM_EV_J")"

  echo "--- 7: trunk peer konteyner qayta ishga tushirilgan -> trunk_up ---"
  docker start m2c-proof-regtrunk >/dev/null 2>&1
  docker exec -d m2c-proof-regtrunk sh -c "python3 -u /tmp/test_registrar.py $TM_IP 5060 60 > /tmp/out.log 2>&1"
  sleep 0.5
  docker exec "$AST" asterisk -rx "pjsip send register t1-trunk-$TM_TRUNK_ID" >/dev/null 2>&1 || true

  wait_until 40 tg_is_decoded "M2cRegTrunk» tiklandi" 1
  check "$(tg_is_decoded "M2cRegTrunk» tiklandi" 1; echo $?)" \
    "7: Telegram'ga trunk_up ogohlantirishi keldi (M2cRegTrunk)" "$(tg_count_decoded "M2cRegTrunk» tiklandi")"

  TM_UP_J=$(api "GET" "/alerts?kind=trunk_up&limit=20")
  check "$(echo "$(jbody "$TM_UP_J")" | python3 -c "
import json,sys
d=json.load(sys.stdin)
sys.exit(0 if any(i['key']=='$TM_TRUNK_ID' and i['status']=='sent' for i in d['items']) else 1)"; echo $?)" \
    "7: GET /alerts kind=trunk_up -> M2cRegTrunk uchun 'sent' yozuvi bor" "$(jbody "$TM_UP_J")"
else
  fail "7: docker topilmadi yoki trunk yaratilmadi, trunk monitoring isboti o'tkazib yuborildi"
fi
