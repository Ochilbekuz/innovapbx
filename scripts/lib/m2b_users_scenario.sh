# shellcheck shell=bash
# M2b §3 (Foydalanuvchilar) — `scripts/m2b-proof.sh` IKKI MARTA `source` qiladi:
# 1-chaqiriqda (ssenariy 1) foydalanuvchi CRUD/self_lockout/parol oqimi, 2-chaqiriqda
# (ssenariy 8, fayl ichida PASS1 bayrog'i bilan ajratiladi) faolsizlantirilgan
# foydalanuvchi kira olmasligi va refresh token bekor qilinishi tekshiriladi.
# Operator "operator102" (ext 102ga bog'langan) shu yerda yaratiladi — ssenariy 3
# (m2b-proof.sh) uni `POST /me/queues/{id}/unpause` uchun ishlatadi (§4, operator
# nomidan, admin endpoint O'RNIGA).

if [[ -z "${M2B_USERS_SCENARIO_PASS1_DONE:-}" ]]; then
  M2B_USERS_SCENARIO_PASS1_DONE=1

  OPERATOR102_LOGIN="operator102"
  OPERATOR102_INITIAL_PASSWORD="Oper102PassAbc9"
  OPERATOR102_PASSWORD="Oper102NewPassXy7"

  # --- yaratish ---
  ADMIN2_J=$(api POST /users '{"username":"admin2","full_name":"Admin Ikki","role":"admin","password":"Admin2PassAbc9"}')
  ADMIN2_ID=$(jget "$(jbody "$ADMIN2_J")" item id)
  check "$( [[ "$(jcode "$ADMIN2_J")" == "201" && -n "$ADMIN2_ID" ]]; echo $?)" \
    "1: POST /users -> admin2 (role=admin)" "$ADMIN2_J"

  OP_J=$(api POST /users "{\"username\":\"$OPERATOR102_LOGIN\",\"full_name\":\"Operator 102\",\"role\":\"operator\",\"extension_id\":\"${EXT_ID[102]}\",\"password\":\"$OPERATOR102_INITIAL_PASSWORD\"}")
  OPERATOR102_ID=$(jget "$(jbody "$OP_J")" item id)
  check "$( [[ "$(jcode "$OP_J")" == "201" && "$(jget "$(jbody "$OP_J")" item extension number)" == "102" \
    && "$(jget "$(jbody "$OP_J")" item must_change_password)" == "True" ]]; echo $?)" \
    "1: POST /users -> operator102 (ext=102, must_change_password=true)" "$OP_J"

  # --- 409 username_taken / extension_taken ---
  DUP_USERNAME_J=$(api POST /users "{\"username\":\"$OPERATOR102_LOGIN\",\"full_name\":\"X\",\"role\":\"operator\",\"password\":\"AnotherPassAbc9\"}")
  check "$( [[ "$(jcode "$DUP_USERNAME_J")" == "409" && "$(jget "$(jbody "$DUP_USERNAME_J")" error code)" == "username_taken" ]]; echo $?)" \
    "1: POST /users (takror login) -> 409 username_taken" "$DUP_USERNAME_J"

  DUP_EXT_J=$(api POST /users "{\"username\":\"operator102b\",\"full_name\":\"X\",\"role\":\"operator\",\"extension_id\":\"${EXT_ID[102]}\",\"password\":\"AnotherPassAbc9\"}")
  check "$( [[ "$(jcode "$DUP_EXT_J")" == "409" && "$(jget "$(jbody "$DUP_EXT_J")" error code)" == "extension_taken" \
    && "$(jget "$(jbody "$DUP_EXT_J")" error details username)" == "$OPERATOR102_LOGIN" ]]; echo $?)" \
    "1: POST /users (band ext=102) -> 409 extension_taken (details.username)" "$DUP_EXT_J"

  # --- ro'yxat ---
  LIST_J=$(jbody "$(api GET /users)")
  check "$(python3 -c "
import json,sys
d=json.load(sys.stdin)
names={u['username'] for u in d['items']}
sys.exit(0 if {'admin','admin2','$OPERATOR102_LOGIN'} <= names else 1)" <<<"$LIST_J"; echo $?)" \
    "1: GET /users -> admin, admin2, operator102 ro'yxatda" "$LIST_J"

  # --- PATCH: oddiy o'zgarish ---
  OP_STAMP=$(jget "$(jbody "$OP_J")" item updated_at)
  RENAME_J=$(api PATCH "/users/$OPERATOR102_ID" "{\"full_name\":\"Operator Yuzinchi Ikki\",\"updated_at\":\"$OP_STAMP\"}")
  check "$( [[ "$(jcode "$RENAME_J")" == "200" && "$(jget "$(jbody "$RENAME_J")" item full_name)" == "Operator Yuzinchi Ikki" ]]; echo $?)" \
    "1: PATCH /users/{operator102} full_name -> 200" "$RENAME_J"

  # --- self_lockout: admin o'zini faolsizlantira/pasaytira olmaydi ---
  ME_ID=$(jget "$(jbody "$(api GET /auth/me)")" id)
  ME_STAMP=$(python3 -c "
import json,sys
d=json.load(sys.stdin)
print(next(u['updated_at'] for u in d['items'] if u['id']==sys.argv[1]))" "$ME_ID" <<<"$LIST_J")
  SELF_DEACT_J=$(api PATCH "/users/$ME_ID" "{\"is_active\":false,\"updated_at\":\"$ME_STAMP\"}")
  check "$( [[ "$(jcode "$SELF_DEACT_J")" == "409" && "$(jget "$(jbody "$SELF_DEACT_J")" error code)" == "self_lockout" ]]; echo $?)" \
    "1: PATCH /users/{o'zi} is_active=false -> 409 self_lockout" "$SELF_DEACT_J"
  SELF_DOWNGRADE_J=$(api PATCH "/users/$ME_ID" "{\"role\":\"operator\",\"updated_at\":\"$ME_STAMP\"}")
  check "$( [[ "$(jcode "$SELF_DOWNGRADE_J")" == "409" && "$(jget "$(jbody "$SELF_DOWNGRADE_J")" error code)" == "self_lockout" ]]; echo $?)" \
    "1: PATCH /users/{o'zi} role=operator -> 409 self_lockout" "$SELF_DOWNGRADE_J"

  # --- DELETE: admin2 (oxirgi admin EMAS) -> muvaffaqiyatli ---
  DEL_J=$(api DELETE "/users/$ADMIN2_ID")
  check "$( [[ "$(jcode "$DEL_J")" == "204" ]]; echo $?)" "1: DELETE /users/{admin2} (oxirgi emas) -> 204" "$DEL_J"
  LIST2_J=$(jbody "$(api GET /users)")
  check "$(python3 -c "
import json,sys
d=json.load(sys.stdin)
sys.exit(1 if any(u['id']=='$ADMIN2_ID' for u in d['items']) else 0)" <<<"$LIST2_J"; echo $?)" \
    "1: GET /users -> admin2 endi yo'q" "$LIST2_J"

  # --- login/parol almashtirish (must_change_password, refresh bekor qilish) ---
  LOGIN1_J=$(curl -s -X POST "$API_BASE/auth/login" -H 'Content-Type: application/json' \
    -d "{\"login\":\"$OPERATOR102_LOGIN\",\"password\":\"$OPERATOR102_INITIAL_PASSWORD\"}")
  OP_ACCESS1=$(jget "$LOGIN1_J" access); OP_REFRESH1=$(jget "$LOGIN1_J" refresh)
  check "$( [[ -n "$OP_ACCESS1" && "$(jget "$LOGIN1_J" user must_change_password)" == "True" ]]; echo $?)" \
    "1: POST /auth/login operator102 -> must_change_password=true" "$LOGIN1_J"

  CHPW_J=$(api_as "$OP_ACCESS1" POST /auth/change-password "{\"current\":\"$OPERATOR102_INITIAL_PASSWORD\",\"new\":\"$OPERATOR102_PASSWORD\"}")
  # Javob — joriy sessiya uchun YANGI juftlik (boshqa sessiyalar bekor, bu sessiya chiqib ketmaydi).
  OP_REFRESH_NEW=$(jget "$(jbody "$CHPW_J")" refresh)
  check "$( [[ "$(jcode "$CHPW_J")" == "200" && -n "$OP_REFRESH_NEW" && -n "$(jget "$(jbody "$CHPW_J")" access)" ]]; echo $?)" \
    "1: POST /auth/change-password (operator102) -> 200 + yangi access/refresh" "$CHPW_J"

  REFRESH_AFTER_CHPW_J=$(curl -s -w '\n%{http_code}' -X POST "$API_BASE/auth/refresh" -H 'Content-Type: application/json' \
    -d "{\"refresh\":\"$OP_REFRESH1\"}")
  check "$( [[ "$(jcode "$REFRESH_AFTER_CHPW_J")" == "401" ]]; echo $?)" \
    "1: parol almashtirishdan keyin ESKI refresh -> 401 (bekor qilindi)" "$REFRESH_AFTER_CHPW_J"
  REFRESH_NEW_J=$(curl -s -w '\n%{http_code}' -X POST "$API_BASE/auth/refresh" -H 'Content-Type: application/json' \
    -d "{\"refresh\":\"$OP_REFRESH_NEW\"}")
  check "$( [[ "$(jcode "$REFRESH_NEW_J")" == "200" ]]; echo $?)" \
    "1: change-password qaytargan YANGI refresh -> 200 (joriy sessiya davom etadi)" "$REFRESH_NEW_J"

  LOGIN2_J=$(curl -s -X POST "$API_BASE/auth/login" -H 'Content-Type: application/json' \
    -d "{\"login\":\"$OPERATOR102_LOGIN\",\"password\":\"$OPERATOR102_PASSWORD\"}")
  OPERATOR102_REFRESH=$(jget "$LOGIN2_J" refresh)
  check "$( [[ -n "$OPERATOR102_REFRESH" && "$(jget "$LOGIN2_J" user must_change_password)" == "False" ]]; echo $?)" \
    "1: YANGI parol bilan login -> must_change_password=false" "$LOGIN2_J"

else
  echo "--- 8. faolsizlantirilgan foydalanuvchi ---"
  OP_LIST_J=$(jbody "$(api GET /users)")
  OP_STAMP2=$(python3 -c "
import json,sys
d=json.load(sys.stdin)
print(next(u['updated_at'] for u in d['items'] if u['id']=='$OPERATOR102_ID'))" <<<"$OP_LIST_J")
  DEACT_J=$(api PATCH "/users/$OPERATOR102_ID" "{\"is_active\":false,\"updated_at\":\"$OP_STAMP2\"}")
  check "$( [[ "$(jcode "$DEACT_J")" == "200" && "$(jget "$(jbody "$DEACT_J")" item is_active)" == "False" ]]; echo $?)" \
    "8: PATCH /users/{operator102} is_active=false -> 200" "$DEACT_J"

  LOGIN_AFTER_DEACT_J=$(curl -s -w '\n%{http_code}' -X POST "$API_BASE/auth/login" -H 'Content-Type: application/json' \
    -d "{\"login\":\"$OPERATOR102_LOGIN\",\"password\":\"$OPERATOR102_PASSWORD\"}")
  check "$( [[ "$(jcode "$LOGIN_AFTER_DEACT_J")" == "401" ]]; echo $?)" \
    "8: faolsizlantirilgan operator102 login -> 401 bad_credentials" "$LOGIN_AFTER_DEACT_J"

  REFRESH_AFTER_DEACT_J=$(curl -s -w '\n%{http_code}' -X POST "$API_BASE/auth/refresh" -H 'Content-Type: application/json' \
    -d "{\"refresh\":\"$OPERATOR102_REFRESH\"}")
  check "$( [[ "$(jcode "$REFRESH_AFTER_DEACT_J")" == "401" ]]; echo $?)" \
    "8: faolsizlantirishdan keyin refresh -> 401 (bekor qilindi)" "$REFRESH_AFTER_DEACT_J"
fi
