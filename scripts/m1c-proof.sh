#!/usr/bin/env bash
# Innova PBX — M1c proof skripti (replica/m1c-contract.md §5):
#   1. Ovozli pochta: 202 -> 201 (qutili, ro'yxatdan o'tgan, faqat 180 —
#      javob bermaydi) -> VoiceMail(201@t1,u) -> RTP (PCMU, 20 s) bilan xabar
#      -> spool'da fayl -> API new=1 -> audio WAV yuklab olinadi -> heard -> old=1
#      -> o'chirish -> 0. Path traversal 404.
#   2. Bildirishnoma: mailpit (SMTP, faqat proof) WAV ilovali xatni oladi; soxta
#      Telegram server `sendAudio` oladi; API restartidan keyin takror yo'q.
#      `/settings/notify/test` — 200 va 502 `notify_failed`. Audit'da parol/token/PIN «***».
#   3. `*97` (o'z qutisi): xato PIN -> rad; to'g'ri PIN -> VoiceMailMain
#      (`core show channels` + CDR lastapp). `*98` (istalgan quti) ham.
#   4. TLS — (boshqa agent, joy ajratilgan).
#   5. memoryhunt — (joy ajratilgan).
#
# Foydalanish:
#   scripts/m1c-proof.sh            # joriy `innova-m0` stackka qarshi (M1c qoldiqlari bo'lsa — exit 2)
#   scripts/m1c-proof.sh --fresh    # avval `docker compose down -v` + qayta build + up -d
#
# MUHIM: bu skript faqat `innova-m0` compose loyihasiga tegadi; o'z
# konteynerlarini (m1c-proof-*) oxirida o'chiradi.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"
SIPP_DIR="$ROOT_DIR/tests/sipp"
API_BASE="${API_BASE:-http://127.0.0.1:8710/api/v1}"
PROJECT="innova-m0"
NET="${PROJECT}_innova-net"
PY_IMAGE="python:3.12-slim"
MAILPIT_IMAGE="axllent/mailpit"
PG=innova-m0-postgres-1
AST=innova-m0-asterisk-1

EXT201_IP="172.21.0.160"   # 201 — qutili ext (jiringlaydi, javob bermaydi; *97 chaqiruvchi)
EXT202_IP="172.21.0.161"   # 202 — chaqiruvchi (qutisiz; *98)
MAILPIT_IP="172.21.0.163"  # test SMTP (1025) + API (8025)
TG_IP="172.21.0.164"       # soxta Telegram Bot API (8081)

ADMIN_PASSWORD="${PROOF_ADMIN_PASSWORD:-$(grep -E '^PROOF_ADMIN_PASSWORD=' "$DEPLOY_DIR/.env" | cut -d= -f2-)}"
[[ -n "$ADMIN_PASSWORD" ]] || { echo "PROOF_ADMIN_PASSWORD deploy/.env da yo'q"; exit 2; }

PASS=0
FAIL=0
pass() { echo "PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); }
check() { # shart_natijasi(0/1) xabar [tafsilot]
  if [[ "$1" == "0" ]]; then pass "$2"; else fail "$2${3:+ -> $3}"; fi
}

sql() { docker exec "$PG" psql -U innova -d innova -tAc "$1" 2>/dev/null; }
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

CONTAINERS=(m1c-proof-ext201 m1c-proof-ext202 m1c-proof-mailpit m1c-proof-tg)
cleanup() { docker rm -f "${CONTAINERS[@]}" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

wait_api() {
  for _ in $(seq 1 60); do
    curl -sf "${API_BASE%/api/v1}/healthz" >/dev/null 2>&1 && return 0
    sleep 2
  done
  return 1
}

if [[ "${1:-}" == "--fresh" ]]; then
  echo "--- --fresh: stack qayta quriladi ---"
  (cd "$DEPLOY_DIR" && docker compose down -v) || true
  (cd "$DEPLOY_DIR" && docker compose build) || { fail "docker compose build"; exit 1; }
  (cd "$DEPLOY_DIR" && docker compose up -d) || { fail "docker compose up"; exit 1; }
  echo "Konteynerlar tayyor bo'lishini kutish..."
  wait_api
fi

echo "=== setup/login ==="
curl -s -o /dev/null -X POST "$API_BASE/setup" -H 'Content-Type: application/json' \
  -d '{"admin":{"login":"admin","password":"'"$ADMIN_PASSWORD"'","full_name":"Admin"},"language":"uz","timezone":"Asia/Tashkent"}'
LOGIN_JSON=$(curl -s -X POST "$API_BASE/auth/login" -H 'Content-Type: application/json' \
  -d '{"login":"admin","password":"'"$ADMIN_PASSWORD"'"}')
TOKEN=$(echo "$LOGIN_JSON" | python3 -c "import json,sys;print(json.load(sys.stdin).get('access',''))" 2>/dev/null)
[[ -n "$TOKEN" ]] || { fail "login -> token yo'q ($LOGIN_JSON)"; exit 1; }
AUTH=(-H "Authorization: Bearer $TOKEN")
echo "login OK"

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

LEFTOVER=$(jget "$(jbody "$(api GET /voicemail-boxes)")" items 0 mailbox 2>/dev/null)
if [[ -n "$LEFTOVER" ]]; then
  echo "Stekda oldingi M1c isbot qoldiqlari bor (quti $LEFTOVER) — 'scripts/m1c-proof.sh --fresh' bilan ishga tushiring."
  exit 2
fi

echo "=== resurslar ==="
EXT201_JSON=$(api POST /extensions '{"number":"201","name":"M1cBox201"}')
EXT201_ID=$(jget "$(jbody "$EXT201_JSON")" item id)
EXT201_SECRET=$(jget "$(jbody "$EXT201_JSON")" sip password)
EXT202_JSON=$(api POST /extensions '{"number":"202","name":"M1cCaller202"}')
EXT202_SECRET=$(jget "$(jbody "$EXT202_JSON")" sip password)
[[ -n "$EXT201_ID" && -n "$EXT202_SECRET" ]] && pass "POST /extensions -> 201, 202" || fail "extensions -> $EXT201_JSON / $EXT202_JSON"

check "$( [[ "$(sql "select coalesce(mailboxes,'') from ps_endpoints where id='t1-201'")" == "" ]]; echo $?)" \
  "qutisiz ext 201: ps_endpoints.mailboxes bo'sh"

# Bildirishnoma sozlamalari (xabar qoldirilishidan OLDIN — 2-ssenariy shu xabarni kutadi).
SMTP_PASS="M1cSmtpS3cret"; TG_TOKEN="123456:M1C-PROOF-token"; VM_PIN="4826"
NS_JSON=$(api PATCH /settings/notify "{\"smtp_host\":\"$MAILPIT_IP\",\"smtp_port\":1025,\"smtp_tls\":\"none\",\"smtp_user\":\"proof\",\"smtp_password\":\"$SMTP_PASS\",\"from_email\":\"pbx@innova.test\",\"telegram_token\":\"$TG_TOKEN\",\"telegram_api_base\":\"http://$TG_IP:8081\"}")
NS_BODY=$(jbody "$NS_JSON")
check "$( [[ "$(jcode "$NS_JSON")" == "200" && "$(jget "$NS_BODY" has_smtp_password)" == "True" && "$(jget "$NS_BODY" has_telegram_token)" == "True" ]]; echo $?)" \
  "PATCH /settings/notify -> has_smtp_password/has_telegram_token=true" "$NS_JSON"
check "$( ! grep -q -e "$SMTP_PASS" -e "$TG_TOKEN" <<<"$(api GET /settings/notify)"; echo $?)" \
  "GET /settings/notify javobida parol/token YO'Q"
check "$( [[ "$(sql "select count(*) from notify_settings where smtp_password_enc like '%$SMTP_PASS%' or telegram_token_enc like '%$TG_TOKEN%'")" == "0" ]]; echo $?)" \
  "notify_settings bazada parol/token shifrlangan"

BOX_JSON=$(api POST /voicemail-boxes "{\"extension_id\":\"$EXT201_ID\",\"pin\":\"$VM_PIN\",\"email\":\"box201@innova.test\",\"email_notify\":true,\"telegram_notify\":true,\"telegram_chat_id\":\"4242\",\"attach_audio\":true}")
BOX_BODY=$(jbody "$BOX_JSON")
BOX_ID=$(jget "$BOX_BODY" item id)
check "$( [[ "$(jcode "$BOX_JSON")" == "201" && "$(jget "$BOX_BODY" apply status)" == "applied" && "$(jget "$BOX_BODY" item has_pin)" == "True" ]]; echo $?)" \
  "POST /voicemail-boxes 201 -> 201 Created, apply=applied, has_pin" "$BOX_JSON"
check "$( [[ "$(sql "select mailboxes from ps_endpoints where id='t1-201'")" == "201@t1" && -z "$(sql "select coalesce(mailboxes,'') from ps_endpoints where id='t1-202'")" ]]; echo $?)" \
  "ps_endpoints.mailboxes: 201 -> 201@t1, 202 (qutisiz) -> bo'sh"
check "$(ast "voicemail show users for t1" | grep -q "201"; echo $?)" \
  "Asterisk: voicemail show users for t1 -> 201" "$(ast "voicemail show users for t1")"
check "$( ! docker exec "$AST" grep -rq "$VM_PIN" /srv/dialplan/voicemail_innova.conf; echo $?)" \
  "voicemail_innova.conf faylida PIN YO'Q"
check "$( [[ "$(sql "select no_answer_target_id is not null from extensions where id='$EXT201_ID'")" == "t" ]]; echo $?)" \
  "ext 201 no_answer -> voicemail maqsadi (avtomatik)"

echo "=== konteynerlar ==="
docker run -d --name m1c-proof-mailpit --network "$NET" --ip "$MAILPIT_IP" "$MAILPIT_IMAGE" \
  --smtp-auth-accept-any --smtp-auth-allow-insecure >/dev/null
for c in ext201:$EXT201_IP ext202:$EXT202_IP tg:$TG_IP; do
  docker run -d --name "m1c-proof-${c%%:*}" --network "$NET" --ip "${c#*:}" "$PY_IMAGE" sleep infinity >/dev/null
done
for c in m1c-proof-ext201 m1c-proof-ext202; do
  docker cp "$SIPP_DIR/outbound_invite.py" "$c:/tmp/outbound_invite.py"
  docker cp "$SIPP_DIR/vm_caller.py" "$c:/tmp/vm_caller.py"
done
docker cp "$SIPP_DIR/fake_telegram.py" m1c-proof-tg:/tmp/fake_telegram.py
docker exec -d m1c-proof-tg python3 /tmp/fake_telegram.py 0.0.0.0 8081 /tmp/tg.log
for c in m1c-proof-ext201 m1c-proof-ext202; do
  docker exec -i "$c" sh -c 'cat > /tmp/call.py' <<'PYEOF'
"""call.py user password local_port dialed rtp_seconds [dtmf] [dtmf_after_s]"""
import sys
sys.path.insert(0, "/tmp")
from vm_caller import VmCaller
user, pw, port, dialed, secs = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], float(sys.argv[5])
dtmf = sys.argv[6] if len(sys.argv) > 6 else ""
after = float(sys.argv[7]) if len(sys.argv) > 7 else 1.0
c = VmCaller("asterisk", 5060, port, user, pw, rtp_port=12000, final_timeout_s=40)
try:
    r = c.invite(dialed)
    final = r[-1] if r else "SIP/2.0 000 NO_RESPONSE"
    print("INVITE_FINAL:", final.splitlines()[0], flush=True)
    if final.startswith("SIP/2.0 200"):
        c.ack()
        print("RTP_SENT:", c.stream_rtp(secs, dtmf, after), flush=True)
        c.bye()
        print("BYE_SENT", flush=True)
finally:
    c.close()
PYEOF
done
docker exec -i m1c-proof-ext201 sh -c 'cat > /tmp/ring.py' <<'PYEOF'
"""ring.py user password local_port seconds — REGISTER, keyin faqat 180 (javob yo'q)."""
import sys
sys.path.insert(0, "/tmp")
from vm_caller import VmCaller
c = VmCaller("asterisk", 5060, int(sys.argv[3]), sys.argv[1], sys.argv[2], rtp_port=12002)
print("REGISTER_RESULT:", "OK" if c.register() else "FAIL", flush=True)
print("SEEN:", c.ring_without_answer(float(sys.argv[4])), flush=True)
c.close()
PYEOF
pass "proof konteynerlari (201, 202, mailpit, soxta Telegram) ishga tushdi"

# ---------------------------------------------------------------- 1
echo "--- 1. ovozli pochta: 202 -> 201 (javob yo'q) -> xabar ---"
docker exec -d m1c-proof-ext201 sh -c "python3 /tmp/ring.py t1-201 '$EXT201_SECRET' 5080 60 > /tmp/ring.log 2>&1"
wait_until 10 sh -c "docker exec m1c-proof-ext201 cat /tmp/ring.log 2>/dev/null | grep -q 'REGISTER_RESULT: OK'" \
  && pass "201 REGISTER -> 200 OK (jiringlaydi, javob bermaydi)" \
  || fail "201 REGISTER -> $(docker exec m1c-proof-ext201 cat /tmp/ring.log)"
# 20 s: ~10 s «unavailable» e'loni + vm-intro + beep, qolgani yozuv.
S1_OUT=$(docker exec m1c-proof-ext202 python3 /tmp/call.py t1-202 "$EXT202_SECRET" 5081 201 20 2>&1)
check "$(grep -q "INVITE_FINAL: SIP/2.0 200" <<<"$S1_OUT"; echo $?)" "1: 202 -> 201 -> 200 OK (VoiceMail javob berdi)" "$S1_OUT"
RTP_SENT=$(sed -n 's/^RTP_SENT: //p' <<<"$S1_OUT")
check "$( (( ${RTP_SENT:-0} >= 150 )); echo $?)" "1: RTP PCMU ${RTP_SENT:-0} paket (>= 3 s) yuborildi"
RING_LOG=$(docker exec m1c-proof-ext201 cat /tmp/ring.log 2>/dev/null)
CDR1=$(sql "select string_agg(disposition||'/'||lastapp, ', ' order by calldate) from cdr where src='202'")
check "$(grep -q "NO ANSWER/Dial, ANSWERED/VoiceMail" <<<"$CDR1"; echo $?)" "1: CDR 202: Dial NO ANSWER -> VoiceMail ANSWERED ($CDR1)"
SPOOL=/var/spool/asterisk/voicemail/t1/201/INBOX
SPOOL_LS=$(docker exec "$AST" ls -ln "$SPOOL" 2>&1)
check "$(grep -q "msg0000.wav" <<<"$SPOOL_LS" && grep -q "msg0000.txt" <<<"$SPOOL_LS"; echo $?)" \
  "1: spool'da $SPOOL/msg0000.{wav,txt}" "$SPOOL_LS"
counts() { jget "$(jbody "$(api GET "/voicemail-boxes?extension_id=$EXT201_ID")")" items 0 counts "$1"; }
check "$( [[ "$(counts new)" == "1" && "$(counts old)" == "0" ]]; echo $?)" "1: API counts new=1 old=0" "new=$(counts new) old=$(counts old)"
MSGS=$(jbody "$(api GET "/voicemail-boxes/$BOX_ID/messages")")
check "$(python3 -c "
import json,sys
m=json.load(sys.stdin)['items']
ok = len(m)==1 and m[0]['id']=='INBOX/msg0000' and m[0]['folder']=='inbox' and not m[0]['heard'] \
     and m[0]['duration_s']>=3 and '202' in m[0]['callerid']
sys.exit(0 if ok else 1)" <<<"$MSGS"; echo $?)" "1: GET messages -> INBOX/msg0000, callerid 202, duration>=3 s" "$MSGS"
AUDIO_HDR=$(curl -s -D - -o /tmp/m1c_msg.wav "$API_BASE/voicemail-boxes/$BOX_ID/messages/INBOX/msg0000/audio" "${AUTH[@]}")
AUDIO_SIZE=$(stat -c %s /tmp/m1c_msg.wav 2>/dev/null || echo 0)
check "$(grep -qi "content-type: audio/wav" <<<"$AUDIO_HDR" && [[ "$(head -c 4 /tmp/m1c_msg.wav)" == "RIFF" ]] && (( AUDIO_SIZE > 1000 )); echo $?)" \
  "1: audio yuklab olindi (audio/wav, RIFF, $AUDIO_SIZE bayt)" "$(head -1 <<<"$AUDIO_HDR")"
for bad in "..%2F..%2F..%2Fetc%2Fpasswd" "INBOX%2F..%2F..%2Fgreet" "%2Fetc%2Fpasswd"; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$API_BASE/voicemail-boxes/$BOX_ID/messages/$bad/audio" "${AUTH[@]}")
  check "$( [[ "$code" == "404" ]]; echo $?)" "1: path traversal '$bad' -> 404" "$code"
done

# ---------------------------------------------------------------- 2
echo "--- 2. bildirishnoma: mailpit + soxta Telegram, restartda takror yo'q ---"
mailpit() { docker exec m1c-proof-tg python3 -c "
import json,sys,urllib.request
print(json.dumps(json.load(urllib.request.urlopen('http://$MAILPIT_IP:8025/api/v1/'+sys.argv[1]))))" "$1"; }
mail_total() { mailpit messages | python3 -c "import json,sys;print(json.load(sys.stdin).get('total',0))"; }
tg_count() { docker exec m1c-proof-tg sh -c "grep -c '$1' /tmp/tg.log 2>/dev/null || true"; }
mail_is() { [[ "$(mail_total)" == "$1" ]]; }
tg_is() { [[ "$(tg_count "$1")" == "$2" ]]; }
wait_until 30 tg_is sendAudio 1
wait_until 15 mail_is 1
MAIL_ID=$(mailpit messages | python3 -c "import json,sys;m=json.load(sys.stdin)['messages'];print(m[0]['ID'] if m else '')")
MAIL='{}'; [[ -n "$MAIL_ID" ]] && MAIL=$(mailpit "message/$MAIL_ID")
check "$(python3 -c "
import json,sys
m=json.load(sys.stdin)
att=m.get('Attachments') or []
ok = any(a['FileName']=='201-msg0000.wav' and a['ContentType']=='audio/wav' and a['Size']>1000 for a in att) \
     and m['To'][0]['Address']=='box201@innova.test' and '201' in m['Subject']
sys.exit(0 if ok else 1)" <<<"$MAIL" 2>/dev/null; echo $?)" "2: mailpit xatni oldi (box201@innova.test, ilova 201-msg0000.wav audio/wav)" "${MAIL:0:300}"
TG_LOG=$(docker exec m1c-proof-tg cat /tmp/tg.log 2>/dev/null)
check "$(grep -q "path=/bot$TG_TOKEN/sendAudio chat_id=4242 filename=msg0000.wav riff=1" <<<"$TG_LOG"; echo $?)" \
  "2: soxta Telegram sendAudio oldi (token deshifrlangan, chat 4242, WAV)" "$TG_LOG"
check "$( [[ "$(sql "select count(*) from voicemail_notifications where box_id='$BOX_ID' and status='sent' and attempts=1")" == "2" ]]; echo $?)" \
  "2: voicemail_notifications: email+telegram sent (attempts=1)" "$(sql "select channel,status,attempts,error from voicemail_notifications")"

echo "    API restart..."
(cd "$DEPLOY_DIR" && docker compose restart api >/dev/null 2>&1)
wait_api || fail "2: API restartdan keyin healthz javob bermadi"
LOGIN_JSON=$(curl -s -X POST "$API_BASE/auth/login" -H 'Content-Type: application/json' -d '{"login":"admin","password":"'"$ADMIN_PASSWORD"'"}')
TOKEN=$(echo "$LOGIN_JSON" | python3 -c "import json,sys;print(json.load(sys.stdin).get('access',''))" 2>/dev/null)
AUTH=(-H "Authorization: Bearer $TOKEN")
sleep 12  # >= 2 skan (vm_notify_interval_s=5)
check "$( [[ "$(mail_total)" == "1" && "$(tg_count sendAudio)" == "1" ]]; echo $?)" \
  "2: API restartidan keyin takror yo'q (mail=1, sendAudio=1)" "mail=$(mail_total) tg=$(tg_count sendAudio)"

NT=$(api POST /settings/notify/test '{"channel":"email","to":"ops@innova.test"}')
check "$( [[ "$(jcode "$NT")" == "200" && "$(jget "$(jbody "$NT")" ok)" == "True" ]] && wait_until 10 mail_is 2; echo $?)" \
  "2: POST /settings/notify/test email -> 200, mailpit 2-xat" "$NT"
NT=$(api POST /settings/notify/test '{"channel":"telegram","to":"4242"}')
check "$( [[ "$(jcode "$NT")" == "200" && "$(tg_count sendMessage)" == "1" ]]; echo $?)" "2: notify/test telegram -> 200, sendMessage" "$NT"
NT=$(api POST /settings/notify/test '{"channel":"telegram","to":"0"}')
check "$( [[ "$(jcode "$NT")" == "502" && "$(jget "$(jbody "$NT")" error code)" == "notify_failed" ]] && grep -q "chat not found" <<<"$NT"; echo $?)" \
  "2: notify/test telegram xato chat -> 502 notify_failed (sabab bilan)" "$NT"

AUDIT_NS=$(jbody "$(api GET "/audit?entity=notify_settings")")
check "$(python3 -c "
import json,sys
rows=[r for r in json.load(sys.stdin).get('items',[]) if r.get('diff',{}).get('smtp_password')]
sys.exit(0 if rows and rows[0]['diff']['smtp_password']=='***' and rows[0]['diff']['telegram_token']=='***' else 1)" <<<"$AUDIT_NS"; echo $?)" \
  "2: audit notify_settings: smtp_password/telegram_token = '***'" "${AUDIT_NS:0:300}"
AUDIT_BOX=$(jbody "$(api GET "/audit?entity=voicemail_box")")
check "$(python3 -c "
import json,sys
rows=[r for r in json.load(sys.stdin).get('items',[]) if 'pin' in (r.get('diff') or {})]
sys.exit(0 if rows and all(r['diff']['pin']=='***' for r in rows) else 1)" <<<"$AUDIT_BOX"; echo $?)" \
  "2: audit voicemail_box: pin = '***'" "${AUDIT_BOX:0:300}"
check "$( [[ "$(sql "select count(*) from audit_log where diff::text like '%$SMTP_PASS%' or diff::text like '%$TG_TOKEN%' or diff::text like '%\"$VM_PIN\"%'")" == "0" ]]; echo $?)" \
  "2: audit_log bazasida ochiq parol/token/PIN YO'Q"

# 1-ssenariy davomi (bildirishnoma INBOX xabarini kutgani uchun keyin): heard -> old, o'chirish.
HEARD=$(api POST "/voicemail-boxes/$BOX_ID/messages/INBOX/msg0000/heard")
check "$( [[ "$(jcode "$HEARD")" == "204" && "$(counts new)" == "0" && "$(counts old)" == "1" ]]; echo $?)" \
  "1: heard -> 204, counts new=0 old=1" "$(jcode "$HEARD") new=$(counts new) old=$(counts old)"
OLD_ID=$(jget "$(jbody "$(api GET "/voicemail-boxes/$BOX_ID/messages")")" items 0 id)
check "$( [[ "$OLD_ID" == "Old/msg0000" ]] && docker exec "$AST" test -f /var/spool/asterisk/voicemail/t1/201/Old/msg0000.wav; echo $?)" \
  "1: xabar Old/msg0000 ga ko'chdi (spool)" "$OLD_ID"
DEL=$(api DELETE "/voicemail-boxes/$BOX_ID/messages/$OLD_ID")
check "$( [[ "$(jcode "$DEL")" == "204" && "$(counts new)" == "0" && "$(counts old)" == "0" ]] && [[ -z "$(jget "$(jbody "$(api GET "/voicemail-boxes/$BOX_ID/messages")")" items 0 id 2>/dev/null)" ]]; echo $?)" \
  "1: DELETE xabar -> 204, counts 0/0, ro'yxat bo'sh" "$DEL"
RING_LOG=$(docker exec m1c-proof-ext201 cat /tmp/ring.log 2>/dev/null)
check "$(grep -q "REQ INVITE" <<<"$RING_LOG"; echo $?)" \
  "1: 201 INVITE oldi (faqat 180, javob bermadi; MWI NOTIFY'ga bardoshli: $(grep -c 'REQ NOTIFY' <<<"$RING_LOG") NOTIFY)" "$RING_LOG"

# ---------------------------------------------------------------- 3
echo "--- 3. *97 / *98: PIN ---"
last_cdr() { sql "select lastapp from cdr where src='$1' and lastapp<>'' order by calldate desc limit 1"; }
S3_BAD=$(docker exec m1c-proof-ext201 python3 /tmp/call.py t1-201 "$EXT201_SECRET" 5082 '*97' 7 "1111#" 1.5 2>&1)
sleep 1
check "$(grep -q "INVITE_FINAL: SIP/2.0 200" <<<"$S3_BAD" && [[ "$(last_cdr 201)" != "VoiceMailMain" ]]; echo $?)" \
  "3: *97 xato PIN -> rad (VoiceMailMain'ga kirmadi, CDR lastapp=$(last_cdr 201))" "$S3_BAD"
docker exec m1c-proof-ext201 sh -c "python3 /tmp/call.py t1-201 '$EXT201_SECRET' 5083 '*97' 12 '$VM_PIN#' 1.5 > /tmp/s3ok.log 2>&1" &
S3_PID=$!
wait_until 10 sh -c "docker exec $AST asterisk -rx 'core show channels concise' | grep -q 'VoiceMailMain!201@t1,s'" \
  && pass "3: *97 to'g'ri PIN -> core show channels: VoiceMailMain(201@t1,s)" \
  || fail "3: *97 to'g'ri PIN -> VoiceMailMain kanalda ko'rinmadi ($(ast 'core show channels concise'))"
wait "$S3_PID"
sleep 1
check "$( [[ "$(last_cdr 201)" == "VoiceMailMain" ]]; echo $?)" "3: *97 CDR lastapp=VoiceMailMain" "$(last_cdr 201)"
S98=$(docker exec m1c-proof-ext202 python3 /tmp/call.py t1-202 "$EXT202_SECRET" 5084 '*98' 10 "201#$VM_PIN#" 1.0 2>&1)
sleep 1
check "$(grep -q "INVITE_FINAL: SIP/2.0 200" <<<"$S98" && [[ "$(last_cdr 202)" == "VoiceMailMain" ]]; echo $?)" \
  "3: *98 (quti 201 + PIN) -> CDR lastapp=VoiceMailMain" "$S98 / $(last_cdr 202)"
PIN_DENY=$(docker exec m1c-proof-tg python3 -c "
import urllib.request;print(urllib.request.urlopen('http://api:8000/internal/voicemail/pin-check?token=wrong&context=t1&mailbox=201&pin=$VM_PIN').read().decode())" 2>&1)
check "$( [[ "$PIN_DENY" == "0" ]]; echo $?)" "3: /internal/voicemail/pin-check noto'g'ri token -> 0" "$PIN_DENY"

# ---------------------------------------------------------------- 4
echo "--- 4. SIP TLS ---"
# shellcheck source=lib/m1c_tls_scenario.sh
source "$(dirname "$0")/lib/m1c_tls_scenario.sh"
scenario_tls "$AST" 5061

# ---------------------------------------------------------------- 5
echo "--- 5. memoryhunt: 1, 1+2, 1+2+3 ---"
MH_IDS=(); MH_SECRETS=()
for n in 211 212 213; do
  j=$(api POST /extensions "{\"number\":\"$n\",\"name\":\"M1cHunt$n\"}")
  MH_IDS+=("$(jget "$(jbody "$j")" item id)"); MH_SECRETS+=("$(jget "$(jbody "$j")" sip password)")
done
MH_RG=$(api POST /ring-groups "{\"name\":\"M1cMemoryHunt\",\"number\":\"611\",\"strategy\":\"memoryhunt\",\"ring_seconds\":5,\"members\":[{\"extension_id\":\"${MH_IDS[0]}\"},{\"extension_id\":\"${MH_IDS[1]}\"},{\"extension_id\":\"${MH_IDS[2]}\"}],\"no_answer_target_id\":\"$(curl -s "$API_BASE/targets?kind=hangup" "${AUTH[@]}" | python3 -c "import json,sys;print([i['id'] for i in json.load(sys.stdin)['items'] if i['kind']=='hangup'][0])")\"}")
check "$( [[ "$(jcode "$MH_RG")" == "201" ]]; echo $?)" "5: POST /ring-groups memoryhunt (211, 212, 213) -> 201" "$MH_RG"
docker exec -i m1c-proof-ext201 sh -c 'cat > /tmp/mh_ring.py' <<'PYEOF'
"""mh_ring.py user password local_port rtp_port seconds — REGISTER, keyin faqat 180."""
import sys
sys.path.insert(0, "/tmp")
from vm_caller import VmCaller
c = VmCaller("asterisk", 5060, int(sys.argv[3]), sys.argv[1], sys.argv[2], rtp_port=int(sys.argv[4]))
print("REGISTER_RESULT:", "OK" if c.register() else "FAIL", flush=True)
print("SEEN:", c.ring_without_answer(float(sys.argv[5])), flush=True)
c.close()
PYEOF
for i in 0 1 2; do
  n=$((211 + i))
  docker exec -d m1c-proof-ext201 sh -c "python3 /tmp/mh_ring.py t1-$n '${MH_SECRETS[$i]}' $((5090 + i)) $((12010 + i * 2)) 40 > /tmp/mh$n.log 2>&1"
done
mh_registered() { for n in 211 212 213; do docker exec m1c-proof-ext201 grep -q 'REGISTER_RESULT: OK' /tmp/mh$n.log 2>/dev/null || return 1; done; }
wait_until 15 mh_registered && pass "5: 211, 212, 213 REGISTER -> 200 OK" || fail "5: memoryhunt a'zolari ro'yxatdan o'tmadi"
MH_CALL=$(docker exec m1c-proof-ext202 python3 /tmp/call.py t1-202 "$EXT202_SECRET" 5085 611 1 2>&1)
invites_of() { docker exec m1c-proof-ext201 grep -c '^REQ INVITE' "/tmp/mh$1.log" 2>/dev/null; }
MH_COUNTS="$(invites_of 211)/$(invites_of 212)/$(invites_of 213)"
check "$( [[ "$MH_COUNTS" == "3/2/1" ]]; echo $?)" "5: INVITE soni 211/212/213 = 3/2/1 (yig'ilib boruvchi)" "$MH_COUNTS; $MH_CALL"

echo "=== NATIJA: PASS=$PASS FAIL=$FAIL ==="
[[ "$FAIL" -eq 0 ]]
