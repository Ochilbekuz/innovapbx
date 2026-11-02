# shellcheck shell=bash
# M3b proof yordamchilari: soxta webhook qabul qiluvchi (`tests/sipp/fake_webhook.py`), yozuvlar va ochiq API.
# Talab: m2a_common.sh (sql, jget, api, api_as, wait_until) avval `source` qilingan; WH_IP, WH_PORT, API_BASE, AST, APICONT.

PUBLIC_BASE="${API_BASE%/api/v1}/api/public/v1"

# ---------------------------------------------------------------- soxta webhook
wh() { curl -s -m 5 "http://$WH_IP:$WH_PORT/$1" "${@:2}"; }
wh_config() { # yo'l secret [fail_n]
  wh _config -X POST -H 'Content-Type: application/json' -d "{\"path\":\"$1\",\"secret\":\"$2\",\"fail\":${3:-0}}" >/dev/null
}
wh_query() { # yo'l call_id python_ifoda -> qabul qilingan so'rovlar (shu qo'ng'iroq) bo'yicha natija
  # Ifodada: `rs` — shu qo'ng'iroq so'rovlari (kelish tartibida), `ok` — 200 + sig_ok bo'lganlari.
  wh "_requests?path=$1" | python3 -c '
import json, sys
cid, expr = sys.argv[1], sys.argv[2]
rs = [r for r in json.load(sys.stdin) if ((r.get("body") or {}).get("call") or {}).get("id") == cid or cid == "*"]
ok = [r for r in rs if r["status"] == 200 and r["sig_ok"]]
print(eval(expr))' "${@:2}"
}
wh_types() { wh_query "$1" "$2" '" ".join(r["event"] for r in ok)'; }    # yo'l call_id -> "call.ringing call.answered ..."
wh_count() { wh_query "$1" "$2" 'len(rs)'; }                               # yo'l call_id -> so'rovlar soni (hammasi)
wh_has() { [[ " $(wh_types "$1" "$2") " == *" $3 "* ]]; }                  # yo'l call_id tur
wh_ended_field() { # yo'l call_id python_ifoda(c = ended call) -> qiymat
  wh_query "$1" "$2" "next((eval(sys.argv[3], {'c': r['body']['call']}) for r in ok if r['event'] == 'call.ended'), '')" "$3"
}

# ---------------------------------------------------------------- qo'ng'iroq / yozuv
linkedid_to_ext() { # ext -> eng so'nggi CDR (dstchannel = shu ext) linkedid
  wait_for_sql "select linkedid from cdr where dstchannel like 'PJSIP/t1-$1-%' order by calldate desc limit 1" 10
}
linkedid_from_ext_to_trunk() { # ext -> eng so'nggi chiquvchi (ext -> trunk) linkedid
  wait_for_sql "select linkedid from cdr where channel like 'PJSIP/t1-$1-%' and dstchannel like '%trunk%' order by calldate desc limit 1" 10
}
ended_emitted() { [[ "$(sql "select count(*) from integration_events where dedupe_key='ended:$1'")" == "1" ]]; }
rec_count() { sql "select count(*) from call_recordings where linkedid='$1' and deleted_at is null"; }
rec_first() { sql "select id||'|'||duration_s||'|'||coalesce(extension,'')||'|'||path from call_recordings where linkedid='$1' and deleted_at is null order by started_at limit 1"; }
wav_seconds() { # fayl -> davomiylik (s, float); WAV emas bo'lsa 0
  python3 -c '
import sys, wave
try:
    with wave.open(sys.argv[1]) as w:
        print(round(w.getnframes() / float(w.getframerate()), 2))
except Exception:
    print(0)' "$1"
}
http_code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
signed_link() { # rec_id exp -> API konteynerida (SECRET_KEY bilan) imzolangan havola so'rovi `?exp=&sig=`
  docker exec "$APICONT" python -c "
import sys
from app.core.config import settings
from app.services.recordings import link_signature
print(f'?exp={sys.argv[2]}&sig=' + link_signature(sys.argv[1], int(sys.argv[2]), settings.require_secret_key()))" "$1" "$2"
}
run_purge() { # API konteynerida saqlash muddati tozalovchisini BIR marta ishga tushiradi -> o'chirilganlar soni
  docker exec "$APICONT" python -c "
import asyncio
from app.db.session import SessionLocal
from app.services.recordings import purge_once
print(asyncio.run(purge_once(SessionLocal)))"
}

# ---------------------------------------------------------------- ochiq API
pub() { # kalit method path [data] -> body + "\n" + http_code
  local key="$1" method="$2" path="$3" data="${4:-}"
  local auth=()
  [[ -n "$key" ]] && auth=(-H "Authorization: Bearer $key")
  if [[ -n "$data" ]]; then
    curl -s -w '\n%{http_code}' -X "$method" "$PUBLIC_BASE$path" "${auth[@]}" -H 'Content-Type: application/json' -d "$data"
  else
    curl -s -w '\n%{http_code}' -X "$method" "$PUBLIC_BASE$path" "${auth[@]}"
  fi
}
err_is() { # javob kod error_code -> 0/1
  [[ "$(jcode "$1")" == "$2" && "$(jget "$(jbody "$1")" error code 2>/dev/null)" == "$3" ]]
}
updated_at_of() { jget "$(jbody "$(api GET "$1")")" updated_at; }   # sozlama yo'li -> updated_at
