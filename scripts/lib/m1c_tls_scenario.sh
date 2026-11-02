#!/usr/bin/env bash
# Innova PBX — M1c bo'lim 3 (SIP TLS) isbot ssenariysi.
#
# BU FAYL MUSTAQIL ISHLAMAYDI: `scenario_tls` funksiyasi `scripts/m1b-proof.sh`
# da aniqlangan yordamchilarga tayanadi — `pass`, `fail`, `ast`, `api`,
# `jbody`, `jcode`, `jget`, `AUTH`, `API_BASE` global o'zgaruvchi/funksiyalari
# chaqiruvchi skriptda (masalan `scripts/m1c-proof.sh`) ALLAQACHON mavjud
# bo'lishi SHART — bu fayl faqat `source` qilinadi, keyin `scenario_tls`
# chaqiriladi.
#
# Oqim (m1c-contract.md bo'lim 3):
#   1. POST /settings/sip/tls/self-signed {"common_name": CN} -> 200,
#      javobda restart_required=true va certificate.subject'da CN bor.
#   2. GET /settings/sip/tls -> enabled=true.
#   3. POST /settings/sip/restart -> 200 (Asterisk qayta ishga tushadi).
#   4. `pjsip show transport transport-tls` mavjud.
#   5. `openssl s_client -connect <asterisk>:5061` — haqiqiy TLS tinglovchi,
#      taqdim etilgan sertifikatning CN'ini ko'rsatadi.
#   6. Mos kelmaydigan kalit bilan sertifikat yuklash -> 422 bad_certificate,
#      details.reason=key_mismatch.
#
# Foydalanish: `source scripts/lib/m1c_tls_scenario.sh; scenario_tls [asterisk_container] [tls_port]`

scenario_tls() {
  local ast_container="${1:-innova-m0-asterisk-1}"
  local tls_port="${2:-5061}"
  local cn="pbx.innova-m1c-proof.test"

  echo "=== ssenariy TLS: SIP TLS sertifikati (m1c-contract.md bo'lim 3) ==="

  local R BODY
  R=$(api POST /settings/sip/tls/self-signed "{\"common_name\":\"$cn\"}")
  BODY=$(jbody "$R")
  [[ "$(jcode "$R")" == "200" ]] && pass "tls: self-signed yaratildi -> 200" || fail "tls: self-signed -> $R"
  [[ "$(jget "$BODY" restart_required)" == "True" ]] \
    && pass "tls: self-signed -> restart_required" || fail "tls: self-signed javobida restart_required yo'q -> $R"
  [[ "$(jget "$BODY" certificate subject)" == *"$cn"* ]] \
    && pass "tls: javobdagi sertifikat subject'da CN bor" || fail "tls: subject'da CN yo'q -> $R"

  R=$(api GET /settings/sip/tls)
  [[ "$(jget "$(jbody "$R")" enabled)" == "True" ]] \
    && pass "tls: GET /settings/sip/tls -> enabled=true" || fail "tls: GET /settings/sip/tls -> $R"

  R=$(api POST /settings/sip/restart)
  [[ "$(jcode "$R")" == "200" ]] && pass "tls: restart -> 200" || fail "tls: restart -> $R"

  local TRANSPORT_OUT
  TRANSPORT_OUT=$(ast "pjsip show transport transport-tls")
  grep -qi "transport-tls" <<<"$TRANSPORT_OUT" \
    && pass "tls: pjsip show transport transport-tls mavjud" || fail "tls: transport-tls topilmadi -> $TRANSPORT_OUT"

  local SCLIENT_OUT CN_LINE
  SCLIENT_OUT=$(docker exec "$ast_container" sh -c \
    "echo | openssl s_client -connect 127.0.0.1:$tls_port -servername '$cn' 2>&1")
  CN_LINE=$(grep -o "CN *= *[^ ,/\"]*" <<<"$SCLIENT_OUT" | head -1)
  [[ -n "$CN_LINE" ]] && pass "tls: openssl s_client -> $CN_LINE" || fail "tls: s_client'da CN topilmadi -> $SCLIENT_OUT"

  R=$(api GET /settings/sip)
  [[ "$(jget "$(jbody "$R")" restart_required)" == "False" ]] \
    && pass "tls: restartdan keyin restart_required tozalandi" || fail "tls: GET /settings/sip -> $R"

  # Mos kelmaydigan sertifikat/kalit juftligi -> 422 bad_certificate/key_mismatch
  local tmp
  tmp=$(mktemp -d)
  openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes -days 1 \
    -subj "/CN=mismatch-a.test" -keyout "$tmp/a.key" -out "$tmp/a.crt" >/dev/null 2>&1
  openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes -days 1 \
    -subj "/CN=mismatch-b.test" -keyout "$tmp/b.key" -out "$tmp/b.crt" >/dev/null 2>&1

  local UPLOAD_RAW UPLOAD_CODE UPLOAD_BODY
  UPLOAD_RAW=$(curl -s -w '\n%{http_code}' -X POST "$API_BASE/settings/sip/tls/certificate" "${AUTH[@]}" \
    -F "cert=@$tmp/a.crt" -F "key=@$tmp/b.key")
  UPLOAD_CODE=$(jcode "$UPLOAD_RAW")
  UPLOAD_BODY=$(jbody "$UPLOAD_RAW")
  [[ "$UPLOAD_CODE" == "422" && "$(jget "$UPLOAD_BODY" error code)" == "bad_certificate" \
     && "$(jget "$UPLOAD_BODY" error details reason)" == "key_mismatch" ]] \
    && pass "tls: mos kelmaydigan kalit -> 422 bad_certificate/key_mismatch" \
    || fail "tls: mos kelmaydigan kalit -> $UPLOAD_RAW"
  rm -rf "$tmp"
}
