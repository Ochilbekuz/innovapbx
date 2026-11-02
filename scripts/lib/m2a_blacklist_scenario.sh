# shellcheck shell=bash
# Innova PBX — M2a ssenariy 4: Qora ro'yxat (m2a-contract.md §5, §6.4).
#
# BU FAYL MUSTAQIL ISHLAMAYDI: `scripts/m2a-proof.sh` ichida `source` qilinadi
# (shartli — fayl mavjud bo'lsa) va chaqiruvchi skriptda ALLAQACHON mavjud
# bo'lgan global o'zgaruvchi/funksiyalarga tayanadi: `pass`/`fail`/`check`,
# `api`/`jbody`/`jcode`/`jget`, `wait_for_sql`, `invites`/`final_of`,
# `AUTH`/`API_BASE`, `PG`.
#
# Oqim:
#   1. Ichki raqam 203'ga yo'nalgan kiruvchi DID marshrut yaratiladi.
#   2. Hali bloklanmagan raqamdan kiruvchi chaqiruv -> 203'ga yetib boradi (200 OK).
#   3. `POST /blacklist` (bezab yozilgan raqam -> normalizatsiya) -> darhol
#      (reload/apply YO'Q) xuddi shu raqamdan kiruvchi chaqiruv rad etiladi,
#      203'ga INVITE YETMAYDI, CDR `userfield=blacklisted`.
#   4. `DELETE /blacklist/{raqam}` -> chaqiruv yana o'tadi.
#   5. `anonymous` maxsus kalit so'zi ham xuddi shunday bloklanadi.

echo "--- 4. qora ro'yxat ---"

BL_DID="555010020"
BL_NUM="998900000777"
BL_NUM_RAW="+998 (90) 000-07-77"   # normalizatsiya isboti uchun bezab yozilgan

BL_TARGET=$(jbody "$(api GET "/targets?kind=extension&q=203")" | python3 -c "
import json,sys
d = json.load(sys.stdin)
items = [i for i in d['items'] if i.get('number') == '203']
print(items[0]['id'] if items else '')
")
BL_ROUTE=$(api POST /inbound-routes "{\"name\":\"M2aBlacklistDid\",\"did\":\"$BL_DID\",\"target_id\":\"$BL_TARGET\",\"enabled\":true}")
check "$( [[ -n "$BL_TARGET" && "$(jcode "$BL_ROUTE")" == "201" && "$(jget "$(jbody "$BL_ROUTE")" apply status)" == "applied" ]]; echo $?)" \
  "4: POST /inbound-routes $BL_DID -> 203, apply=applied" "$BL_TARGET / $BL_ROUTE"

mode 203 answer

send_inbound() { # caller_num dialed -> $INBOUND_OUT, final kod `final_of "$INBOUND_OUT"` orqali
  CALL_N=$((CALL_N + 1))
  local port=$((5500 + CALL_N))
  INBOUND_OUT=$(docker exec -i m2a-proof-trunk python3 - "$1" "$2" "$port" <<'PYEOF'
import sys, time
sys.path.insert(0, "/tmp")
from outbound_invite import OutboundCaller
user, dialed, port = sys.argv[1], sys.argv[2], int(sys.argv[3])
c = OutboundCaller("asterisk", 5060, port, user, "unused")
try:
    responses = c.invite(dialed)
    final = responses[-1] if responses else "SIP/2.0 000 NO_RESPONSE"
    print("INVITE_FINAL:", final.splitlines()[0])
    code = int(final.split(" ", 2)[1])
    c.ack()
    if code == 200:
        time.sleep(1.5)
        c.bye()
finally:
    c.close()
PYEOF
)
}

# --------------------------------------------------- 1) hali bloklanmagan
B203=$(invites 203)
send_inbound "$BL_NUM" "$BL_DID"
check "$( [[ "$(final_of "$INBOUND_OUT")" == "200" && "$(invites 203)" == "$((B203 + 1))" ]]; echo $?)" \
  "4: hali bloklanmagan $BL_NUM -> $BL_DID -> 203 javob berdi" "$INBOUND_OUT"

# --------------------------------------------------- 2) bloklash (realtime)
BL_ADD=$(api POST /blacklist "{\"number\":\"$BL_NUM_RAW\",\"reason\":\"spam-test\"}")
check "$( [[ "$(jcode "$BL_ADD")" == "201" && "$(jget "$(jbody "$BL_ADD")" item number)" == "$BL_NUM" ]]; echo $?)" \
  "4: POST /blacklist (bezab yozilgan) -> normalizatsiya $BL_NUM" "$BL_ADD"
BL_LIST=$(jbody "$(api GET "/blacklist?q=$BL_NUM")")
check "$(python3 -c "
import json,sys
d=json.load(sys.stdin)
sys.exit(0 if any(i['number']=='$BL_NUM' for i in d['items']) else 1)" <<<"$BL_LIST"; echo $?)" \
  "4: GET /blacklist?q=$BL_NUM -> ro'yxatda ko'rinadi" "$BL_LIST"

B203=$(invites 203)
send_inbound "$BL_NUM" "$BL_DID"
check "$( [[ "$(final_of "$INBOUND_OUT")" != "200" && "$(invites 203)" == "$B203" ]]; echo $?)" \
  "4: bloklangan $BL_NUM -> $BL_DID rad etildi (203'ga INVITE yetmadi)" "$INBOUND_OUT"
BL_CDR=$(wait_for_sql "select userfield from cdr where dst='$BL_DID' and userfield='blacklisted' order by calldate desc limit 1" 6)
check "$( [[ "$BL_CDR" == "blacklisted" ]]; echo $?)" "4: CDR userfield=blacklisted" "$BL_CDR"

# --------------------------------------------------- 3) olib tashlash
BL_DEL=$(api DELETE "/blacklist/$BL_NUM")
check "$( [[ "$(jcode "$BL_DEL")" == "204" ]]; echo $?)" "4: DELETE /blacklist/$BL_NUM -> 204" "$BL_DEL"
BL_DEL2=$(api DELETE "/blacklist/$BL_NUM")
check "$( [[ "$(jcode "$BL_DEL2")" == "404" ]]; echo $?)" "4: ikkinchi DELETE -> 404" "$BL_DEL2"

B203=$(invites 203)
send_inbound "$BL_NUM" "$BL_DID"
check "$( [[ "$(final_of "$INBOUND_OUT")" == "200" && "$(invites 203)" == "$((B203 + 1))" ]]; echo $?)" \
  "4: olib tashlangach $BL_NUM -> $BL_DID yana o'tdi" "$INBOUND_OUT"

# --------------------------------------------------- 4) anonymous
BL_ANON_ADD=$(api POST /blacklist '{"number":"restricted","reason":"yashirin"}')
check "$( [[ "$(jcode "$BL_ANON_ADD")" == "201" && "$(jget "$(jbody "$BL_ANON_ADD")" item number)" == "anonymous" ]]; echo $?)" \
  "4: POST /blacklist 'restricted' -> 'anonymous'" "$BL_ANON_ADD"
B203=$(invites 203)
send_inbound "anonymous" "$BL_DID"
check "$( [[ "$(final_of "$INBOUND_OUT")" != "200" && "$(invites 203)" == "$B203" ]]; echo $?)" \
  "4: anonymous -> $BL_DID rad etildi" "$INBOUND_OUT"
api DELETE "/blacklist/anonymous" >/dev/null
