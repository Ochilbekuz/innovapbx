# shellcheck shell=bash
# Innova PBX — M2a ssenariy 8: Konferensiya (m2a-contract.md §4, §6.8).
#
# BU FAYL MUSTAQIL ISHLAMAYDI: `scripts/m2a-proof.sh` ichida `source` qilinadi
# va chaqiruvchi skriptda ALLAQACHON mavjud bo'lgan global
# o'zgaruvchi/funksiyalarga tayanadi: `pass`/`fail`/`check`, `api`/`jbody`/
# `jcode`/`jget`, `wait_until`, `place_call`/`place_call_bg`/`call_log`/
# `call_done`, registratsiya qilingan 201/202/203 (`SECRET[...]`), `AUTH`.
#
# Oqim:
#   1. PIN + admin PIN bilan konferensiya yaratiladi (`number=650`).
#   2. 2 ta chaqiruvchi to'g'ri (oddiy) PIN bilan BIR VAQTDA qo'shiladi ->
#      `GET /conferences/{id}` da `live.members=2`; ikkisi chiqgach 0.
#   3. Noto'g'ri PIN -> 3 urinishdan keyin Asterisk o'zi uzadi (REMOTE_BYE).
#   4. Admin PIN bilan qo'shilish ham ishlaydi (alohida profil, lekin bitta xona).

echo "--- 8. konferensiya ---"

CONF_PIN="2468"
CONF_ADMIN_PIN="1357"
CONF=$(api POST /conferences "{\"name\":\"M2aConf\",\"number\":\"650\",\"pin\":\"$CONF_PIN\",\"admin_pin\":\"$CONF_ADMIN_PIN\"}")
CONF_ID=$(jget "$(jbody "$CONF")" item id)
check "$( [[ "$(jcode "$CONF")" == "201" && -n "$CONF_ID" \
  && "$(jget "$(jbody "$CONF")" item has_pin)" == "True" \
  && "$(jget "$(jbody "$CONF")" item has_admin_pin)" == "True" \
  && "$(jget "$(jbody "$CONF")" item number)" == "650" \
  && "$(jget "$(jbody "$CONF")" apply status)" == "applied" ]]; echo $?)" \
  "8: POST /conferences 650 -> has_pin/has_admin_pin=true, apply=applied" "$CONF"

members_is() { [[ "$(jget "$(jbody "$(api GET "/conferences/$CONF_ID")")" live members)" == "$1" ]]; }
check "$(members_is 0; echo $?)" "8: hali hech kim yo'q -> live.members=0"

# ------------------------------------------------- 2 ta chaqiruvchi (oddiy PIN)
place_call_bg c1 201 650 14 "${CONF_PIN}#"
place_call_bg c2 202 650 14 "${CONF_PIN}#"
wait_until 10 members_is 2 && pass "8: 2 chaqiruvchi (oddiy PIN) -> live.members=2" \
  || fail "8: live.members=2 bo'lmadi" "$(jbody "$(api GET "/conferences/$CONF_ID")")"
wait_until 15 call_done 201 c1
wait_until 15 call_done 202 c2
check "$(wait_until 5 members_is 0; echo $?)" "8: ikkisi chiqgach live.members=0" \
  "$(jbody "$(api GET "/conferences/$CONF_ID")")"

# ------------------------------------------------- noto'g'ri PIN (3 urinish -> uziladi)
place_call 203 650 20 '0000#,0000#,0000#'
check "$(grep -q 'INVITE_FINAL: SIP/2.0 200' <<<"$OUT" && grep -q 'REMOTE_BYE' <<<"$OUT"; echo $?)" \
  "8: noto'g'ri PIN (3 urinish) -> Asterisk o'zi uzdi" "$OUT"
check "$(members_is 0; echo $?)" "8: noto'g'ri PIN -> xonaga qo'shilmadi (live.members=0)"

# ------------------------------------------------- admin PIN
place_call_bg a1 201 650 8 "${CONF_ADMIN_PIN}#"
wait_until 10 members_is 1 && pass "8: admin PIN bilan qo'shildi -> live.members=1" \
  || fail "8: admin PIN -> live.members=1 bo'lmadi" "$(jbody "$(api GET "/conferences/$CONF_ID")")"
wait_until 15 call_done 201 a1
check "$(wait_until 5 members_is 0; echo $?)" "8: admin chiqgach live.members=0"
