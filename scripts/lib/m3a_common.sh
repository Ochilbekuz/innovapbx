# shellcheck shell=bash
# M3a proof yordamchilari: haqiqiy Chromium boshqaruvchisi (`web/scripts/m3a-browser.mjs`) bilan
# HTTP orqali gaplashish va `/sip-ws` darvozasini stdlib WS mijozi (`tests/sipp/m3a_ws.py`) bilan sinash.
# Talab: m2a_common.sh (jget, wait_until, api_as) avval `source` qilingan; CTL, WEB_BASE, SIPP_DIR.

br() { curl -s -m 60 "$CTL/$1"; }                       # boshqaruv buyrug'i -> JSON
bget() { jget "$(br "state?who=$1")" "$2" 2>/dev/null; }  # who maydon -> qiymat
bis() { [[ "$(bget "$1" "$2")" == "$3" ]]; }              # who maydon qiymat
bok() { [[ "$(jget "$1" ok 2>/dev/null)" == "True" ]]; }
stat_of() { jget "$(br "stats?who=$1")" "$2" 2>/dev/null; }
media_flows() { # who... -> har biri uchun packetsSent>50 va packetsReceived>50
  local w s r
  for w in "$@"; do
    s=$(stat_of "$w" packetsSent); r=$(stat_of "$w" packetsReceived)
    (( ${s:-0} > 50 && ${r:-0} > 50 )) || return 1
  done
}
float_gt() { python3 -c "import sys; sys.exit(0 if float(sys.argv[1]) > float(sys.argv[2]) else 1)" "${1:-0}" "${2:-0}"; }

softphone_of() { # token -> /me/softphone body+code
  api_as "$1" GET /me/softphone
}
sp_field() { jget "$(jbody "$1")" "${@:2}" 2>/dev/null; }
ws_probe() { python3 "$SIPP_DIR/m3a_ws.py" probe "$1" 2>&1; }
ws_register() { # softphone_json parol n -> m3a_ws.py natijasi
  python3 "$SIPP_DIR/m3a_ws.py" register "$WS_BASE/sip-ws?t=$(sp_field "$1" ticket)" \
    "$(sp_field "$1" sip auth_user)" "$(sp_field "$1" sip uri)" "$2" "$3" 2>&1
}
moh_lines() { docker logs "$AST" 2>&1 | grep -c "$1"; }
# WS kontakt = Asterisk uni nginx (web konteyner) IP'si orqali ko'radi; `pjsip show contacts` URI
# ustunini qisqartiradi (";transport=ws" ko'rinmaydi) — shu sabab manzil bo'yicha ajratamiz.
ws_contact_line() { ast "pjsip show contacts" | grep -E "$1/sip:[^ ]*@${NGINX_IP//./\\.}:"; }
ws_contact() { ws_contact_line "$1" | grep -qE " (Avail|NonQual) "; }
no_ws_contact() { [[ -z "$(ws_contact_line "$1")" ]]; }
moh_gt() { (( $(moh_lines "$1") > $2 )); }
