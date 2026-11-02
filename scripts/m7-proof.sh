#!/usr/bin/env bash
# Innova PBX — M7 proof skripti (replica/m7-roles-contract.md §5):
#   1. Admin `routing:edit`+`reports:view` ruxsatli maxsus rol yaratadi (POST /roles).
#   2. Shu rolli foydalanuvchi kiradi (login) va token bilan:
#        GET /ivrs -> 200, POST /ivrs -> 201 (routing:edit),
#        GET /trunks -> 403, POST /trunks -> 403 (boshqa hudud),
#        GET /users -> 403 (tizim guruhi, hech qachon hududga tushmaydi),
#        GET /calls -> 200 va hammasini ko'radi (reports:view == admin, faqat o'zinikini emas).
#   3. Admin rolni `routing:view`ga tushiradi (PATCH /roles/{id}) — SHU TOKEN bilan
#      (qayta login YO'Q) POST /ivrs endi 403 — ruxsat DB'dan har so'rovda o'qiladi.
#   4. Rolni o'chirish (foydalanuvchi hali biriktirilgan) -> 409 role_in_use.
#   5. Tizim rolini (`admin`) tahrirlash -> 409 system_role.
#   6. Noma'lum ruxsat (`foo:edit`) bilan rol yaratish -> 422 validation_error.
#
# Operator (tizim roli) xatti-harakati bu skript bilan O'ZGARTIRILMAGAN — buni
# tasdiqlash `scripts/m2b-proof.sh`da (0 FAIL) ALLAQACHON bor, shu sabab bu
# yerda qayta ishlatilmaydi (DRY — ikkinchi nusxa yaratish ub-mode'ga zid).
#
# Foydalanish:
#   scripts/m7-proof.sh            # joriy `innova-m0` stackka qarshi
#   scripts/m7-proof.sh --fresh    # avval `docker compose down -v` + qayta build + up -d
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"
LIB_DIR="$ROOT_DIR/scripts/lib"
API_BASE="${API_BASE:-http://127.0.0.1:8710/api/v1}"
PROJECT="innova-m0"

# shellcheck source=lib/m2a_common.sh
# login/api/login_as/api_as/jget/jbody/jcode/check — umumiy proof-infratuzilma
# (M2a'ga xos emas), qayta yozish = dryer bo'yicha takror bo'lardi.
source "$LIB_DIR/m2a_common.sh"
# shellcheck source=lib/m3b_common.sh
# Faqat `err_is()` kerak (status+error_code birgalikda tekshirish) — m3b'ga
# xos boshqa funksiyalar (updated_at_of) bu yerda ishlatilmaydi.
source "$LIB_DIR/m3b_common.sh"

ADMIN_PASSWORD="${PROOF_ADMIN_PASSWORD:-$(grep -E '^PROOF_ADMIN_PASSWORD=' "$DEPLOY_DIR/.env" 2>/dev/null | cut -d= -f2-)}"
[[ -n "$ADMIN_PASSWORD" ]] || { echo "PROOF_ADMIN_PASSWORD deploy/.env da yo'q"; exit 2; }

if [[ "${1:-}" == "--fresh" ]]; then
  echo "--- --fresh: stack qayta quriladi ---"
  (cd "$DEPLOY_DIR" && docker compose -p "$PROJECT" down -v) || true
  (cd "$DEPLOY_DIR" && docker compose -p "$PROJECT" build) || { fail "docker compose build"; exit 1; }
  (cd "$DEPLOY_DIR" && docker compose -p "$PROJECT" up -d) || { fail "docker compose up"; exit 1; }
  wait_api
fi

echo "=== setup/login (admin) ==="
login "$ADMIN_PASSWORD" || { fail "login"; exit 1; }

echo "=== resurslar (IVR uchun shart bo'lgan tizim obyektlari) ==="
AUDIO_ID=$(jget "$(jbody "$(api GET /audio)")" items 0 id)
HANGUP_TARGET=$(jget "$(jbody "$(api GET "/targets?kind=hangup")")" items 0 id)
check "$( [[ -n "$AUDIO_ID" && -n "$HANGUP_TARGET" ]]; echo $?)" \
  "tizim audiosi + hangup manzili topildi" "audio=$AUDIO_ID hangup=$HANGUP_TARGET"

echo "--- 1. rol yaratish: routing:edit + reports:view ---"
RROLE=$(api POST /roles '{"name":"M7Rol","permissions":["routing:edit","reports:view"]}')
check "$( [[ "$(jcode "$RROLE")" == "201" ]]; echo $?)" "POST /roles -> 201" "$RROLE"
ROLE_ID=$(jget "$(jbody "$RROLE")" item id)
ROLE_UPDATED_AT=$(jget "$(jbody "$RROLE")" item updated_at)

echo "--- foydalanuvchi: shu rol bilan ---"
USER_PASS="M7Parol!2026"
RUSER=$(api POST /users "{\"username\":\"m7user\",\"full_name\":\"M7 User\",\"role\":\"M7Rol\",\"password\":\"$USER_PASS\"}")
check "$( [[ "$(jcode "$RUSER")" == "201" ]]; echo $?)" "POST /users (M7Rol) -> 201" "$RUSER"

TOKEN=$(login_as m7user "$USER_PASS")
check "$( [[ -n "$TOKEN" ]]; echo $?)" "m7user kirdi (login)" "token bo'sh"

echo "--- 2. ruxsatlar: routing hududi ochiq, boshqalari yopiq ---"
check "$( [[ "$(jcode "$(api_as "$TOKEN" GET /ivrs)")" == "200" ]]; echo $?)" "GET /ivrs -> 200 (routing:view, edit orqali)"

RIVR=$(api_as "$TOKEN" POST /ivrs "{\"name\":\"M7Ivr\",\"greeting_audio_id\":\"$AUDIO_ID\",\"timeout_target_id\":\"$HANGUP_TARGET\",\"invalid_target_id\":\"$HANGUP_TARGET\"}")
check "$( [[ "$(jcode "$RIVR")" == "201" ]]; echo $?)" "POST /ivrs -> 201 (routing:edit)" "$RIVR"

check "$( [[ "$(jcode "$(api_as "$TOKEN" GET /trunks)")" == "403" ]]; echo $?)" "GET /trunks -> 403 (boshqa hudud)"
check "$( [[ "$(jcode "$(api_as "$TOKEN" POST /trunks '{}')")" == "403" ]]; echo $?)" "POST /trunks -> 403 (boshqa hudud)"
check "$( [[ "$(jcode "$(api_as "$TOKEN" GET /users)")" == "403" ]]; echo $?)" "GET /users -> 403 (tizim guruhi, hech qachon hudud emas)"

# IVR formasi tanlagichlari (boshqa hudud API'si) — routing:edit bilan forma ochilishi uchun GET 200.
for path in /audio /targets /extensions /time-groups; do
  check "$( [[ "$(jcode "$(api_as "$TOKEN" GET "$path")")" == "200" ]]; echo $?)" "tanlagich GET $path -> 200 (routing:edit)"
done
EXT_ID=$(jget "$(jbody "$(api GET /extensions)")" items 0 id)
if [[ -n "$EXT_ID" ]]; then
  check "$( [[ "$(jcode "$(api_as "$TOKEN" POST "/extensions/$EXT_ID/rotate-secret" '{}')")" == "403" ]]; echo $?)" \
    "ext SIP parolini almashtirish -> 403 (tanlagich faqat GET, sir yo'q)"
fi
check "$( [[ "$(jcode "$(api_as "$TOKEN" POST /audio '{}')")" == "403" ]]; echo $?)" "POST /audio -> 403 (tanlagich yozishga ruxsat bermaydi)"

RCALLS=$(api_as "$TOKEN" GET /calls)
check "$( [[ "$(jcode "$RCALLS")" == "200" ]]; echo $?)" "GET /calls -> 200 (reports:view == admin bilan bir xil)" "$RCALLS"

echo "--- 3. rolni routing:view'ga tushirish -> SHU TOKEN bilan darhol 403 ---"
RDOWN=$(api PATCH "/roles/$ROLE_ID" "{\"permissions\":[\"routing:view\"],\"updated_at\":\"$ROLE_UPDATED_AT\"}")
check "$( [[ "$(jcode "$RDOWN")" == "200" ]]; echo $?)" "PATCH /roles/{id} -> 200 (routing:view)" "$RDOWN"
ROLE_UPDATED_AT=$(jget "$(jbody "$RDOWN")" item updated_at)

RIVR2=$(api_as "$TOKEN" POST /ivrs "{\"name\":\"M7Ivr2\",\"greeting_audio_id\":\"$AUDIO_ID\",\"timeout_target_id\":\"$HANGUP_TARGET\",\"invalid_target_id\":\"$HANGUP_TARGET\"}")
check "$(err_is "$RIVR2" 403 forbidden; echo $?)" "qayta login'siz: POST /ivrs -> 403 (ruxsat har so'rovda DB'dan)" "$RIVR2"

echo "--- 4. rolni o'chirish (foydalanuvchi hali biriktirilgan) -> 409 role_in_use ---"
RDEL=$(api DELETE "/roles/$ROLE_ID")
check "$(err_is "$RDEL" 409 role_in_use; echo $?)" "DELETE /roles/{id} (band) -> 409 role_in_use" "$RDEL"

echo "--- 5. tizim rolini (admin) tahrirlash -> 409 system_role ---"
ADMIN_ROLE_ID=$(jget "$(jbody "$(api GET /roles)")" items 0 id)
ADMIN_ROLE_UPDATED_AT=$(jget "$(jbody "$(api GET /roles)")" items 0 updated_at)
RSYS=$(api PATCH "/roles/$ADMIN_ROLE_ID" "{\"name\":\"X\",\"updated_at\":\"$ADMIN_ROLE_UPDATED_AT\"}")
check "$(err_is "$RSYS" 409 system_role; echo $?)" "PATCH /roles/{admin} -> 409 system_role" "$RSYS"

echo "--- 6. noma'lum ruxsat -> 422 validation_error ---"
RBAD=$(api POST /roles '{"name":"BadRol","permissions":["foo:edit"]}')
check "$(err_is "$RBAD" 422 validation_error; echo $?)" "POST /roles (foo:edit) -> 422 validation_error" "$RBAD"

echo
echo "=== NATIJA: PASS=$PASS FAIL=$FAIL ==="
(( FAIL == 0 ))
