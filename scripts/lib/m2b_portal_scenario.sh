# shellcheck shell=bash
# M2b §4 (Operator portali /me) — `scripts/m2b-proof.sh` ssenariy 2 (DND/forward +
# ruxsatlar). `operator102` (ext 102ga bog'langan) 1-ssenariyda
# (`m2b_users_scenario.sh`) yaratilgan va eksport qilingan ($OPERATOR102_LOGIN/
# $OPERATOR102_PASSWORD) — shu yerda `login_as`/`api_as` (m2a_common.sh) orqali
# o'zi nomidan `/me/*` chaqiriladi (admin $AUTH ga TEGILMAYDI).

if [[ -z "${OPERATOR102_LOGIN:-}" ]]; then
  echo "SKIP: 2 — OPERATOR102_LOGIN yo'q (ssenariy 1, m2b_users_scenario.sh ishlamagan)"
else
  OP_TOKEN=$(login_as "$OPERATOR102_LOGIN" "$OPERATOR102_PASSWORD")
  check "$( [[ -n "$OP_TOKEN" ]]; echo $?)" "2: login_as operator102 -> access token oldi"

  OV_J=$(api_as "$OP_TOKEN" GET /me/overview)
  OV_B=$(jbody "$OV_J")
  check "$( [[ "$(jcode "$OV_J")" == "200" && "$(jget "$OV_B" extension number)" == "102" \
    && "$(jget "$OV_B" user username)" == "$OPERATOR102_LOGIN" ]]; echo $?)" \
    "2: GET /me/overview (operator102) -> extension=102, user=operator102" "$OV_J"
  check "$(python3 -c "
import json,sys
d=json.load(sys.stdin)
names={q['name'] for q in d['queues']}
sys.exit(0 if 'M2bQueue' in names else 1)" <<<"$OV_B"; echo $?)" \
    "2: GET /me/overview -> queues'da M2bQueue (102 a'zo)" "$OV_B"

  EXT_STAMP=$(jget "$OV_B" extension updated_at)

  DND_ON_J=$(api_as "$OP_TOKEN" PATCH /me/extension "{\"dnd\":true,\"updated_at\":\"$EXT_STAMP\"}")
  DND_ON_B=$(jbody "$DND_ON_J")
  check "$( [[ "$(jcode "$DND_ON_J")" == "200" && "$(jget "$DND_ON_B" item dnd)" == "True" ]]; echo $?)" \
    "2: PATCH /me/extension dnd=true -> 200" "$DND_ON_J"
  check "$(python3 -c "import json,sys;sys.exit(0 if 'apply' not in json.load(sys.stdin) else 1)" <<<"$DND_ON_B"; echo $?)" \
    "2: PATCH /me/extension javobida 'apply' YO'Q (realtime, §4)" "$DND_ON_B"

  EXT_STAMP=$(jget "$DND_ON_B" item updated_at)
  BAD_FWD_J=$(api_as "$OP_TOKEN" PATCH /me/extension "{\"forward_always\":\"abc\",\"updated_at\":\"$EXT_STAMP\"}")
  check "$( [[ "$(jcode "$BAD_FWD_J")" == "422" && "$(jget "$(jbody "$BAD_FWD_J")" error code)" == "bad_number" ]]; echo $?)" \
    "2: PATCH /me/extension forward_always='abc' -> 422 bad_number (admin bilan BIR XIL tekshiruv)" "$BAD_FWD_J"

  FWD_ON_J=$(api_as "$OP_TOKEN" PATCH /me/extension "{\"forward_busy\":\"0937012345\",\"updated_at\":\"$EXT_STAMP\"}")
  FWD_ON_B=$(jbody "$FWD_ON_J")
  check "$( [[ "$(jcode "$FWD_ON_J")" == "200" && "$(jget "$FWD_ON_B" item forward_busy)" == "0937012345" ]]; echo $?)" \
    "2: PATCH /me/extension forward_busy=0937012345 -> 200" "$FWD_ON_J"

  EXT_STAMP=$(jget "$FWD_ON_B" item updated_at)
  RESET_J=$(api_as "$OP_TOKEN" PATCH /me/extension "{\"dnd\":false,\"forward_busy\":null,\"updated_at\":\"$EXT_STAMP\"}")
  RESET_B=$(jbody "$RESET_J")
  check "$( [[ "$(jcode "$RESET_J")" == "200" && "$(jget "$RESET_B" item dnd)" == "False" \
    && -z "$(jget "$RESET_B" item forward_busy)" ]]; echo $?)" \
    "2: PATCH /me/extension dnd=false, forward_busy=null (tiklash, 3-band uchun) -> 200" "$RESET_J"

  # --- operator admin-only marshrutga kira olmaydi (403) ---
  FORBIDDEN_J=$(api_as "$OP_TOKEN" GET /users)
  check "$( [[ "$(jcode "$FORBIDDEN_J")" == "403" ]]; echo $?)" \
    "2: operator102 -> GET /users (admin-only) -> 403" "$FORBIDDEN_J"

  # --- admin ham o'z ichki raqami (103) bilan /me dan foydalana oladi ---
  ADMIN_OV_J=$(api GET /me/overview)
  check "$( [[ "$(jcode "$ADMIN_OV_J")" == "200" && "$(jget "$(jbody "$ADMIN_OV_J")" extension number)" == "103" ]]; echo $?)" \
    "2: GET /me/overview (admin, o'z ext=103 bilan) -> 200" "$ADMIN_OV_J"
fi
