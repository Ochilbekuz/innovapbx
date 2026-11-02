# shellcheck shell=bash
# M2a proof umumiy yordamchilari (m2a-proof.sh va 4/8-ssenariy fayllari `source` qiladi).
# Talab qilinadi: API_BASE, PG, AST o'zgaruvchilari. PASS/FAIL hisoblagichlari shu yerda.

PASS=0
FAIL=0
pass() { echo "PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); }
check() { # shart_natijasi(0/1) xabar [tafsilot]
  if [[ "$1" == "0" ]]; then pass "$2"; else fail "$2${3:+ -> $3}"; fi
}

sql() { docker exec "$PG" psql -U innova -d innova -tAc "$1" 2>/dev/null; }

# `cdr.conf`'da batch=no bo'lsa ham, CDR yozuvi kanal tugashidan SO'NG (biroz
# kechikib) yoziladi — qattiq `sleep N` noaniq, shu sabab topilguncha qisqa
# intervalda qayta so'raymiz (`m1b-proof.sh`dagi BILAN BIR XIL qolip).
wait_for_sql() { # sql max_seconds -> stdout: oxirgi natija (bo'sh bo'lsa ham)
  local sql_text="$1" max_seconds="${2:-5}" tries out="" i=0
  tries=$(( max_seconds * 2 ))
  while (( i < tries )); do
    out=$(sql "$sql_text")
    [[ -n "$out" ]] && { echo "$out"; return 0; }
    sleep 0.5
    i=$((i + 1))
  done
  echo "$out"
}
ast() { docker exec "$AST" asterisk -rx "$1" 2>/dev/null; }
wait_until() { # max_seconds buyruq... -> buyruq 0 qaytarguncha (0.5 s oraliq)
  local max="$1"; shift
  local i=0
  while (( i < max * 2 )); do
    "$@" && return 0
    sleep 0.5; i=$((i + 1))
  done
  return 1
}

wait_api() {
  for _ in $(seq 1 60); do
    curl -sf "${API_BASE%/api/v1}/healthz" >/dev/null 2>&1 && return 0
    sleep 2
  done
  return 1
}

login_as() { # login parol -> stdout: access token (AUTH massiviga TEGMAYDI,
  # m2b §3/§4 isbotlarida operator/boshqa foydalanuvchi sifatida kirish uchun)
  local login_json
  login_json=$(curl -s -X POST "$API_BASE/auth/login" -H 'Content-Type: application/json' \
    -d "{\"login\":\"$1\",\"password\":\"$2\"}")
  echo "$login_json" | python3 -c "import json,sys;print(json.load(sys.stdin).get('access',''))" 2>/dev/null
}
refresh_token_of() { # login parol -> stdout: refresh token
  local login_json
  login_json=$(curl -s -X POST "$API_BASE/auth/login" -H 'Content-Type: application/json' \
    -d "{\"login\":\"$1\",\"password\":\"$2\"}")
  echo "$login_json" | python3 -c "import json,sys;print(json.load(sys.stdin).get('refresh',''))" 2>/dev/null
}
api_as() { # token method path [data] -> body + "\n" + http_code (`api()` bilan
  # BIR XIL, faqat global $AUTH o'rniga aniq token — boshqa foydalanuvchi nomidan)
  local token="$1" method="$2" path="$3" data="${4:-}"
  if [[ -n "$data" ]]; then
    curl -s -w '\n%{http_code}' -X "$method" "$API_BASE$path" -H "Authorization: Bearer $token" \
      -H 'Content-Type: application/json' -d "$data"
  else
    curl -s -w '\n%{http_code}' -X "$method" "$API_BASE$path" -H "Authorization: Bearer $token"
  fi
}

login() { # parol -> AUTH massivi
  # 1.0.4: o'rnatish kodi — `deploy/.env`da bo'lsa yuboramiz (bo'lmasa bo'sh, server
  # settings.setup_code bo'sh bo'lsa baribir tekshirmaydi — orqaga moslik).
  local setup_code=""
  [[ -z "${DEPLOY_DIR:-}" ]] || setup_code=$(grep -E '^SETUP_CODE=' "$DEPLOY_DIR/.env" 2>/dev/null | cut -d= -f2-)
  curl -s -o /dev/null -X POST "$API_BASE/setup" -H 'Content-Type: application/json' \
    -d '{"admin":{"login":"admin","password":"'"$1"'","full_name":"Admin"},"language":"uz","timezone":"Asia/Tashkent","code":"'"$setup_code"'"}'
  local login_json token
  login_json=$(curl -s -X POST "$API_BASE/auth/login" -H 'Content-Type: application/json' \
    -d '{"login":"admin","password":"'"$1"'"}')
  token=$(echo "$login_json" | python3 -c "import json,sys;print(json.load(sys.stdin).get('access',''))" 2>/dev/null)
  [[ -n "$token" ]] || { echo "login -> token yo'q ($login_json)"; return 1; }
  AUTH=(-H "Authorization: Bearer $token")
}

api() { # method path [data] -> body + "\n" + http_code
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

# Ikki ext kanali (PJSIP/A-…, PJSIP/B-…) bitta bridge'da (core show channels concise, 13-ustun).
bridged() {
  ast "core show channels concise" | python3 -c '
import sys
a, b = sys.argv[1], sys.argv[2]
bridges = {}
for line in sys.stdin:
    f = line.strip().split("!")
    if len(f) > 12 and f[12]:
        bridges.setdefault(f[12], []).append(f[0])
ok = any(any(c.startswith(f"PJSIP/{a}-") for c in v) and any(c.startswith(f"PJSIP/{b}-") for c in v)
         for v in bridges.values())
sys.exit(0 if ok else 1)' "$1" "$2"
}
