#!/usr/bin/env bash
# Innova PBX — M4b (zaxira nusxa va tiklash) proof (replica/m4b-contract.md §4, bandlar 1-7;
# 8-band UI, bu skript JAVOBGAR EMAS):
#   1. Parolsiz zaxira -> 409 passphrase_required; parol o'rnatildi; to'liq zaxira (recordings bilan)
#      -> ok, lokal fayl bor, faylda ochiq matn YO'Q, inspect -> sha256 ok, sirlar javob/audit/logda yo'q.
#   2. Buzilgan .ibk (1 bayt, kesilgan) -> backup_corrupt x2; noto'g'ri parol -> bad_passphrase.
#   3. S3+SFTP: test/trust/noto'g'ri sir/ishonchsiz host->partial/retention keep_last=2/begona fayl
#      tegilmaydi/SFTP o'chirilgan->partial+alert/host kaliti almashsa->host_key_mismatch.
#   4. Shu serverga tiklash: o'zgarishlar -> restore -> holat zaxiradagiga TENG, REGISTER/qo'ng'iroq/MOH/
#      yozuv/CDR ishlaydi, pre_restore -> bekor qilish; faol qo'ng'iroqda active_calls, parallel job_running,
#      tiklash paytida maintenance.
#   5. Disaster recovery: boshqa INNOVA_DB_KEY bilan fresh stack -> upload -> inspect -> restore ->
#      trunk siri to'g'ri (re-key), REGISTER 200, zaxiradagi admin login.
#   6. Jadval: 1 daqiqadan keyingi vaqt -> <=120 s ichida scheduled zaxira.
#   7. Operator -> /backups 403 (backup_newer/retention chegaralari — pytest, bu yerda EMAS).
# minio/minio Docker Hub'dan olib tashlangan (quay.io/minio/minio 401) — S3 isboti uchun
# `zenko/cloudserver` ishlatiladi (scripts/lib/m4b_common.sh izohida qayd etilgan).
#
# Foydalanish:
#   scripts/m4b-proof.sh            # joriy `innova-m0` stack (M4b qoldiqlari bo'lsa — exit 2)
#   scripts/m4b-proof.sh --fresh    # avval `docker compose down -v` + build + up -d
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"
SIPP_DIR="$ROOT_DIR/tests/sipp"
LIB_DIR="$ROOT_DIR/scripts/lib"
API_BASE="${API_BASE:-http://127.0.0.1:8710/api/v1}"
PROJECT="innova-m0"
NET="${PROJECT}_innova-net"
PY_IMAGE="python:3.12-slim"
PG=innova-m0-postgres-1
AST=innova-m0-asterisk-1
APICONT=innova-m0-api-1

BACKUP_PASSPHRASE="M4bZaxiraParoli!2026"
WRONG_PASSPHRASE="NotoGriParolQiymat1"
TEMP_DR_PASSWORD="M4bDrBootTmp!77xy"
ALL_COMPONENTS='["config","history","sounds","voicemail","recordings","certs"]'
TRUNK_USER="m4breguser"
TRUNK_PASS="M4bTrunkSecret!09"

# shellcheck source=lib/m2a_common.sh
source "$LIB_DIR/m2a_common.sh"
# shellcheck source=lib/m3b_common.sh
source "$LIB_DIR/m3b_common.sh"
# shellcheck source=lib/m4b_common.sh
source "$LIB_DIR/m4b_common.sh"

ADMIN_PASSWORD="${PROOF_ADMIN_PASSWORD:-$(grep -E '^PROOF_ADMIN_PASSWORD=' "$DEPLOY_DIR/.env" | cut -d= -f2-)}"
[[ -n "$ADMIN_PASSWORD" ]] || { echo "PROOF_ADMIN_PASSWORD deploy/.env da yo'q"; exit 2; }

# ------------------------------------------------------------------ .env EHTIYOTKORLIK (5-band)
# .env QIYMATLARI hech qachon chiqarilmaydi/logga yozilmaydi — faqat `cp -a`/`sed` bilan ishlanadi.
cp -a "$DEPLOY_DIR/.env" "/root/innova-env-asl.bak-$(date +%s)"
ENV_BAK=$(mktemp /tmp/m4b-env-bak.XXXXXX)
cp -a "$DEPLOY_DIR/.env" "$ENV_BAK"

CONTAINERS=(m4b-proof-101 m4b-proof-ph m4b-proof-dr)
cleanup() {
  docker rm -f "${CONTAINERS[@]}" "$S3_HOST" "$SFTP_HOST" >/dev/null 2>&1 || true
  cp -a "$ENV_BAK" "$DEPLOY_DIR/.env" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
cleanup

if [[ "${1:-}" == "--fresh" ]]; then
  echo "--- --fresh: stack qayta quriladi ---"
  (cd "$DEPLOY_DIR" && docker compose down -v) || true
  (cd "$DEPLOY_DIR" && docker compose build) || { fail "docker compose build"; exit 1; }
  (cd "$DEPLOY_DIR" && docker compose up -d) || { fail "docker compose up"; exit 1; }
  echo "Konteynerlar tayyor bo'lishini kutish..."
  wait_api
fi

echo "=== setup/login ==="
login "$ADMIN_PASSWORD" || { fail "login"; exit 1; }
LEFTOVER=$(python3 -c "import json,sys;print(len(json.load(sys.stdin)['items']))" <<<"$(jbody "$(api GET /backups)")" 2>/dev/null)
if [[ "$LEFTOVER" != "0" ]]; then
  echo "Stekda oldingi M4b isbot qoldiqlari bor (backups=$LEFTOVER) — 'scripts/m4b-proof.sh --fresh' bilan ishga tushiring."
  exit 2
fi

# ---------------------------------------------------------------- yordamchilar
canon() { jbody "$(api GET "$1")" | python3 -c "import json,sys;print(json.dumps(json.load(sys.stdin),sort_keys=True))"; }
pre_restore_of() { # restore_job_id -> shu ishning pre_restore_backup_id
  jbody "$(api GET /backups/restores)" | python3 -c "
import json, sys
items = json.load(sys.stdin)['items']
j = next((r for r in items if r['id'] == sys.argv[1]), None)
print((j or {}).get('pre_restore_backup_id') or '')" "$1"
}
has_number() { # path number -> topilsa 0
  jbody "$(api GET "$1")" | python3 -c "
import json, sys
sys.exit(0 if any(i.get('number') == sys.argv[1] for i in json.load(sys.stdin)['items']) else 1)" "$2"
}

# ---------------------------------------------------------------- resurslar
echo "=== resurslar ==="
declare -A EXT_ID SECRET
# 102 ATAYLAB "never" EMAS — `recording_policy.decide()`/`dialplan_recording.py`
# qoidasi "biri 'always' va HECH BIRI 'never' emas -> yoziladi" (never ustun):
# ikkala ichki tomon bo'lganda 102="never" bo'lsa 101="always" bo'lsa ham YOZILMAYDI
# (bu BACKEND xatosi EMAS, qoida ATAYLAB shunday). Shu sabab 102="on_demand" —
# 101ning "always"i 102 tomonidan bostirilmaydi, lekin ikkisi teng emasligini sinaydi.
for spec in 101:always 102:on_demand; do
  n=${spec%%:*}
  j=$(jbody "$(api POST /extensions "{\"number\":\"$n\",\"name\":\"M4b$n\",\"recording\":\"${spec#*:}\"}")")
  EXT_ID[$n]=$(jget "$j" item id); SECRET[$n]=$(jget "$j" sip password)
  check "$( [[ -n "${EXT_ID[$n]}" ]]; echo $?)" "POST /extensions $n (recording=${spec#*:})" "$j"
done

TJ=$(jbody "$(api POST /trunks "{\"name\":\"M4bTrunk\",\"host\":\"sip.m4b-proof.test\",\"port\":5060,
  \"auth_mode\":\"register\",\"username\":\"$TRUNK_USER\",\"password\":\"$TRUNK_PASS\",
  \"codecs\":[\"ulaw\"],\"max_channels\":5,\"enabled\":true}")")
TRUNK_ID=$(jget "$TJ" item id)
check "$( [[ -n "$TRUNK_ID" ]]; echo $?)" "POST /trunks (register mode)" "$TJ"

python3 - <<'PY'
import struct, wave
for name in ("/tmp/m4b-greet.wav", "/tmp/m4b-moh.wav"):
    with wave.open(name, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
        w.writeframes(struct.pack("<8000h", *([0] * 8000)))
PY
AJ=$(jbody "$(upload_audio_file M4bGreet /tmp/m4b-greet.wav)")
AUDIO_GREET_ID=$(jget "$AJ" item id)
MJ=$(jbody "$(upload_audio_file M4bMoh /tmp/m4b-moh.wav)")
AUDIO_MOH_ID=$(jget "$MJ" item id)
check "$( [[ -n "$AUDIO_GREET_ID" && -n "$AUDIO_MOH_ID" ]]; echo $?)" "POST /audio (greeting + MOH)" "$AJ / $MJ"

HANGUP_T=$(jget "$(jbody "$(api GET "/targets?kind=hangup")")" items 0 id)
IJ=$(api POST /ivrs "{\"name\":\"M4bIvr\",\"greeting_audio_id\":\"$AUDIO_GREET_ID\",
  \"timeout_target_id\":\"$HANGUP_T\",\"invalid_target_id\":\"$HANGUP_T\"}")
IVR_ID=$(jget "$(jbody "$IJ")" item id)
check "$( [[ "$(jcode "$IJ")" == "201" ]]; echo $?)" "POST /ivrs" "$IJ"

MOHJ=$(api POST /moh-classes "{\"name\":\"m4bmoh\",\"file_ids\":[\"$AUDIO_MOH_ID\"]}")
MOH_ID=$(jget "$(jbody "$MOHJ")" item id)
check "$( [[ "$(jcode "$MOHJ")" == "201" ]]; echo $?)" "POST /moh-classes" "$MOHJ"

docker run -d --name m4b-proof-101 --network "$NET" "$PY_IMAGE" sleep infinity >/dev/null
docker run -d --name m4b-proof-ph --network "$NET" "$PY_IMAGE" sleep infinity >/dev/null
for c in m4b-proof-101 m4b-proof-ph; do
  for f in outbound_invite.py vm_caller.py m2a_phone.py register_only.py; do docker cp "$SIPP_DIR/$f" "$c:/tmp/$f"; done
done

# ================================================================== 1
echo "=== 1. parol / to'liq zaxira / sirlar sizmasligi ==="
R=$(api POST /backups '{"components":["config"]}')
check "$( err_is "$R" 409 passphrase_required; echo $?)" "1: parolsiz zaxira -> 409 passphrase_required" "$R"

PJ=$(api PUT /settings/backup/passphrase "{\"passphrase\":\"$BACKUP_PASSPHRASE\"}")
check "$( [[ "$(jcode "$PJ")" == "200" ]]; echo $?)" "1: zaxira parolini o'rnatish" "$PJ"

BJ=$(api POST /backups "{\"components\":$ALL_COMPONENTS}")
BK1=$(jget "$(jbody "$BJ")" job id)
ST1=$(backup_final_status "$BK1" 180)
FNAME1=$(backup_file_name "$BK1")
check "$( [[ "$(jcode "$BJ")" == "202" && "$ST1" == "ok" && -n "$FNAME1" ]]; echo $?)" \
  "1: to'liq zaxira (recordings bilan) -> ok, file_name bor" "$BJ / $ST1 / $FNAME1"
check "$(docker exec "$APICONT" test -f "/var/lib/innova/backups/$FNAME1"; echo $?)" \
  "1: zaxira fayli api konteynerida bor ($FNAME1)"

LEAK=0
# Yalang'och "101" (3 bayt) shifrlangan MB'lik faylda tasodifan uchrab turadi (~1/16M har pozitsiyada) — flaky.
for needle in "M4b101" "$TRUNK_USER" "PGDMP"; do
  docker exec "$APICONT" grep -qaF "$needle" "/var/lib/innova/backups/$FNAME1" && LEAK=1
done
check "$( [[ "$LEAK" == "0" ]]; echo $?)" "1: faylda ochiq matn yo'q (raqam/trunk nomi/PGDMP grep 0)"

INS=$(api POST "/backups/$BK1/inspect" '{}')
check "$( [[ "$(jcode "$INS")" == "200" && "$(jget "$(jbody "$INS")" checks sha256)" == "ok" ]]; echo $?)" \
  "1: inspect -> checks.sha256 ok" "$INS"

LOG_LEAK=$(docker logs "$APICONT" 2>&1 | grep -c -F "$BACKUP_PASSPHRASE" || true)
AUDIT_LEAK=$(sql "select count(*) from audit_log where diff::text like '%$BACKUP_PASSPHRASE%'
  or diff::text like '%$TRUNK_PASS%'")
check "$( [[ "$LOG_LEAK" == "0" && "$AUDIT_LEAK" == "0" ]]; echo $?)" \
  "1: parol/sirlar docker logs va audit_log da yo'q" "$LOG_LEAK / $AUDIT_LEAK"

# ================================================================== 2
echo "=== 2. buzilish / noto'g'ri parol ==="
api_download "/backups/$BK1/download" /tmp/m4b-good.ibk >/dev/null
corrupt_flip_byte /tmp/m4b-good.ibk /tmp/m4b-flip.ibk
corrupt_truncate /tmp/m4b-good.ibk /tmp/m4b-trunc.ibk

BK_FLIP=$(jget "$(jbody "$(api_upload /backups/upload /tmp/m4b-flip.ibk)")" item id)
R=$(api POST "/backups/$BK_FLIP/inspect" '{}')
check "$( err_is "$R" 422 backup_corrupt; echo $?)" "2: 1 bayt o'zgartirilgan .ibk -> inspect 422 backup_corrupt" "$R"

BK_TRUNC=$(jget "$(jbody "$(api_upload /backups/upload /tmp/m4b-trunc.ibk)")" item id)
R=$(api POST "/backups/$BK_TRUNC/inspect" '{}')
check "$( err_is "$R" 422 backup_corrupt; echo $?)" "2: oxiri kesilgan .ibk -> inspect 422 backup_corrupt" "$R"

BK_GOODCOPY=$(jget "$(jbody "$(api_upload /backups/upload /tmp/m4b-good.ibk)")" item id)
R=$(api POST "/backups/$BK_GOODCOPY/inspect" "{\"passphrase\":\"$WRONG_PASSPHRASE\"}")
check "$( err_is "$R" 422 bad_passphrase; echo $?)" "2: noto'g'ri parol bilan inspect -> 422 bad_passphrase" "$R"

# ================================================================== 3
echo "=== 3. S3 + SFTP: test/trust/retention/outage ==="
s3_up || { fail "3: S3 (zenko/cloudserver) ko'tarilmadi"; exit 1; }
sftp_up || { fail "3: SFTP (atmoz/sftp) ko'tarilmadi"; exit 1; }

UA=$(updated_at_of /settings/backup)
R=$(api PUT /settings/backup "{\"updated_at\":\"$UA\",\"targets\":{
  \"s3\":{\"enabled\":true,\"endpoint\":\"http://$S3_HOST:8000\",\"region\":\"us-east-1\",
    \"bucket\":\"$S3_BUCKET\",\"prefix\":\"\",\"access_key\":\"$S3_ACCESS\",\"secret_key\":\"$S3_SECRET\",
    \"path_style\":true,\"keep_last\":2},
  \"sftp\":{\"enabled\":true,\"host\":\"$SFTP_HOST\",\"port\":22,\"user\":\"$SFTP_USER\",
    \"password\":\"$SFTP_PASS\",\"folder\":\"/$SFTP_DIR\",\"keep_last\":2}}}")
check "$( [[ "$(jcode "$R")" == "200" ]]; echo $?)" "3: PUT /settings/backup (S3+SFTP, trust yo'q)" "$R"

T=$(api POST /settings/backup/targets/s3/test)
check "$( [[ "$(jget "$(jbody "$T")" ok)" == "True" ]]; echo $?)" "3: S3 test (to'g'ri sirlar) -> ok" "$T"

UA=$(updated_at_of /settings/backup)
api PUT /settings/backup "{\"updated_at\":\"$UA\",\"targets\":{\"s3\":{\"enabled\":true,
  \"endpoint\":\"http://$S3_HOST:8000\",\"region\":\"us-east-1\",\"bucket\":\"$S3_BUCKET\",\"prefix\":\"\",
  \"access_key\":\"$S3_ACCESS\",\"secret_key\":\"$S3_WRONG_SECRET\",\"path_style\":true,\"keep_last\":2}}}" >/dev/null
T=$(api POST /settings/backup/targets/s3/test)
check "$( [[ "$(jget "$(jbody "$T")" ok)" == "False" && -n "$(jget "$(jbody "$T")" error)" ]]; echo $?)" \
  "3: S3 test (noto'g'ri secret_key) -> ok:false, aniq xato" "$T"
UA=$(updated_at_of /settings/backup)
api PUT /settings/backup "{\"updated_at\":\"$UA\",\"targets\":{\"s3\":{\"enabled\":true,
  \"endpoint\":\"http://$S3_HOST:8000\",\"region\":\"us-east-1\",\"bucket\":\"$S3_BUCKET\",\"prefix\":\"\",
  \"access_key\":\"$S3_ACCESS\",\"secret_key\":\"$S3_SECRET\",\"path_style\":true,\"keep_last\":2}}}" >/dev/null

BJ=$(api POST /backups '{"components":["config"]}')
BK3A=$(jget "$(jbody "$BJ")" job id)
ST=$(backup_final_status "$BK3A" 60)
check "$( [[ "$ST" == "partial" && "$(copy_error "$BK3A" sftp)" == "host_key_not_trusted" ]]; echo $?)" \
  "3: SFTP ishonilmagan (host_key_fp yo'q) -> zaxira partial, copy xatosi host_key_not_trusted" "$ST / $(copy_error "$BK3A" sftp)"

T=$(api POST /settings/backup/targets/sftp/test)
FP=$(jget "$(jbody "$T")" host_key_fp)
check "$( [[ -n "$FP" ]]; echo $?)" "3: SFTP test (hali ishonilmagan) -> barmoq izini qaytaradi" "$T"
TR=$(api POST /settings/backup/targets/sftp/trust "{\"host_key_fp\":\"$FP\"}")
check "$( [[ "$(jcode "$TR")" == "200" ]]; echo $?)" "3: POST /settings/backup/targets/sftp/trust" "$TR"

UA=$(updated_at_of /settings/backup)
api PUT /settings/backup "{\"updated_at\":\"$UA\",\"targets\":{\"sftp\":{\"enabled\":true,\"host\":\"$SFTP_HOST\",
  \"port\":22,\"user\":\"$SFTP_USER\",\"password\":\"WrongSftpPass999\",\"folder\":\"/$SFTP_DIR\",\"keep_last\":2}}}" >/dev/null
T=$(api POST /settings/backup/targets/sftp/test)
check "$( [[ "$(jget "$(jbody "$T")" ok)" == "False" ]]; echo $?)" "3: SFTP test (noto'g'ri parol) -> ok:false" "$T"
UA=$(updated_at_of /settings/backup)
api PUT /settings/backup "{\"updated_at\":\"$UA\",\"targets\":{\"sftp\":{\"enabled\":true,\"host\":\"$SFTP_HOST\",
  \"port\":22,\"user\":\"$SFTP_USER\",\"password\":\"$SFTP_PASS\",\"folder\":\"/$SFTP_DIR\",\"keep_last\":2}}}" >/dev/null

s3_put_foreign begona-s3.txt
sftp_put_foreign begona-sftp.txt
for i in 1 2 3; do
  BJ=$(api POST /backups '{"components":["config"]}')
  BID=$(jget "$(jbody "$BJ")" job id)
  ST=$(backup_final_status "$BID" 60)
  [[ "$i" == "3" ]] && LAST_OK_ST="$ST"
done
check "$( [[ "$LAST_OK_ST" == "ok" ]]; echo $?)" "3: trust'dan keyin S3+SFTP ikkalasi ham ok (3 marta)" "$LAST_OK_ST"
check "$( [[ "$(s3_count)" == "2" && "$(sftp_count)" == "2" ]]; echo $?)" \
  "3: keep_last=2 -> S3 va SFTP da aniq 2 ta o'zimizning fayl" "S3=$(s3_count) SFTP=$(sftp_count)"
check "$( s3_has begona-s3.txt && sftp_has begona-sftp.txt; echo $?)" "3: begona fayllar tegilmagan (retention faqat innova-*.ibk)"

ALERT_BEFORE=$(sql "select count(*) from alert_log where kind='backup_failed' and key='backup'")
sftp_stop
BJ=$(api POST /backups '{"components":["config"]}')
BK3O=$(jget "$(jbody "$BJ")" job id)
ST=$(backup_final_status "$BK3O" 60)
ALERT_AFTER=$(wait_for_sql "select count(*) from alert_log where kind='backup_failed' and key='backup'" 10)
check "$( [[ "$ST" == "partial" && "$ALERT_AFTER" -gt "$ALERT_BEFORE" ]]; echo $?)" \
  "3: SFTP o'chirilgan -> zaxira partial + alert_log backup_failed" "$ST / $ALERT_BEFORE -> $ALERT_AFTER"

sftp_up    # YANGI host kaliti (konteyner qayta yaratiladi) — eski host_key_fp hali ishonilgan
T=$(api POST /settings/backup/targets/sftp/test)
check "$( [[ "$(jget "$(jbody "$T")" ok)" == "False" && "$(jget "$(jbody "$T")" error)" == "host_key_mismatch" ]]; echo $?)" \
  "3: SFTP host kaliti almashdi -> test ok:false, error host_key_mismatch" "$T"

UA=$(updated_at_of /settings/backup)
api PUT /settings/backup "{\"updated_at\":\"$UA\",\"targets\":{
  \"s3\":{\"enabled\":false,\"endpoint\":\"http://$S3_HOST:8000\",\"region\":\"us-east-1\",\"bucket\":\"$S3_BUCKET\",
    \"prefix\":\"\",\"access_key\":\"$S3_ACCESS\",\"secret_key\":\"$S3_SECRET\",\"path_style\":true,\"keep_last\":2},
  \"sftp\":{\"enabled\":false,\"host\":\"$SFTP_HOST\",\"port\":22,\"user\":\"$SFTP_USER\",
    \"password\":\"$SFTP_PASS\",\"folder\":\"/$SFTP_DIR\",\"keep_last\":2}}}" >/dev/null
s3_down; sftp_down

# ================================================================== 4
echo "=== 4. shu serverga tiklash ==="
docker exec -d m4b-proof-101 sh -c "cd /tmp && python3 m2a_phone.py serve 101 '${SECRET[101]}' 5070 12000 /tmp/mode 1800 > /tmp/phone.log 2>&1"
docker exec m4b-proof-101 sh -c "echo answer > /tmp/mode"
wait_until 15 docker exec m4b-proof-101 grep -q 'REGISTER_RESULT: OK' /tmp/phone.log

docker exec m4b-proof-ph sh -c "cd /tmp && python3 m2a_phone.py call 102 '${SECRET[102]}' 5071 13000 101 4 >/tmp/call1.log 2>&1"
LID=$(linkedid_to_ext 101)
# yozuv fayli BYE'dan keyin asinxron yoziladi (MixMonitor + hup-event qayta ishlash) -- darhol
# tekshirish g'oyib yozuvga olib keladi, shu sabab bir necha soniya kutamiz (m3b-proof.sh'dagi
# `wait_until ... ended_emitted` bilan bir xil sabab, bu yerda to'g'ridan-to'g'ri yozuv borligini kutamiz).
_rec_ready() { [[ -n "$(rec_first "$1")" ]]; }
wait_until 10 _rec_ready "$LID"
REC=$(rec_first "$LID")
check "$( [[ -n "$LID" && -n "$REC" ]]; echo $?)" "4: 102->101 qo'ng'iroq -> CDR va yozuv bor (ext101 recording=always)" "$LID / $REC"
REC_ID=$(cut -d'|' -f1 <<<"$REC")

BJ=$(api POST /backups "{\"components\":$ALL_COMPONENTS}")
BK4=$(jget "$(jbody "$BJ")" job id)
ST=$(backup_final_status "$BK4" 180)
check "$( [[ "$ST" == "ok" ]]; echo $?)" "4: tiklash uchun to'liq zaxira -> ok" "$ST"

BASE_EXT=$(canon /extensions); BASE_IVR=$(canon /ivrs); BASE_TRUNK=$(canon /trunks); BASE_PROV=$(canon /settings/provisioning)

# MUHIM: faol qo'ng'iroqni 102 HALI O'CHIRILMAGANDA sinaymiz -- aks holda (destructive
# o'zgarishlardan KEYIN, 102 bazadan o'chirilgach) undan qo'ng'iroq boshlab bo'lmaydi
# (401/404 SIP javobi, Asterisk kanal OCHMAYDI) -- demak hech qachon "faol" deb
# ro'yxatga olinmaydi, 409 tekshiruvi soxta FAIL beradi VA bu o'zining qabul qilingan
# (409 kutilgan joyda 202 qaytgan) so'rovi orqali KUTILMAGAN ikkinchi tiklash ishini
# ishga tushirib yuboradi (haqiqiy tiklashdan OLDIN) -- shu soxta qo'shimcha ish
# keyingi "102->101 javob topadi" tekshiruvida ham tasodifiy nosozlikka olib keladi.
docker exec -d m4b-proof-ph sh -c "cd /tmp && python3 m2a_phone.py call 102 '${SECRET[102]}' 5072 13002 101 15 >/tmp/call2.log 2>&1"
sleep 2
R=$(api POST "/backups/$BK4/restore" '{"confirm":"TIKLASH"}')
check "$( err_is "$R" 409 active_calls; echo $?)" "4: faol qo'ng'iroq bo'lsa (force yo'q) -> 409 active_calls" "$R"
sleep 14

api POST /extensions '{"number":"150","name":"M4bExtra"}' >/dev/null
api DELETE "/extensions/${EXT_ID[102]}" >/dev/null
IJ_AT=$(jbody "$(api GET /ivrs)" | python3 -c "import sys,json; print(next(i['updated_at'] for i in json.load(sys.stdin)['items'] if i['id']=='$IVR_ID'))")
IVR_PATCH_CODE=$(jcode "$(api PATCH "/ivrs/$IVR_ID" "{\"updated_at\":\"$IJ_AT\",\"timeout_seconds\":9}")")
TCODE=$(sql "select code from tenants limit 1")
docker exec "$APICONT" rm -f "/var/lib/innova/sounds/$TCODE/$AUDIO_MOH_ID.wav"
check "$( has_number /extensions 150 && [[ "$IVR_PATCH_CODE" == 200 ]]; echo $?)" "4: buzg'unchi o'zgarishlar kiritildi (150 qo'shildi, 102 o'chirildi, IVR/MOH buzildi)" "ivr_patch=$IVR_PATCH_CODE"

R=$(api POST "/backups/$BK4/restore" '{"confirm":"TIKLASH"}')
RESTORE_JOB_ID=$(jget "$(jbody "$R")" job id)
check "$( [[ "$(jcode "$R")" == "202" && -n "$RESTORE_JOB_ID" ]]; echo $?)" "4: tiklash so'rovi -> 202" "$R"

R2=$(api POST /backups '{"components":["config"]}')
check "$( err_is "$R2" 409 job_running; echo $?)" "4: tiklash ketayotganda parallel ish -> 409 job_running" "$R2"

SEEN_MAINT=0
for _ in $(seq 1 120); do
  M=$(api GET /extensions)
  if err_is "$M" 503 maintenance; then SEEN_MAINT=1; break; fi
  JOB_ST=$(jget "$(jbody "$(api GET "/backups/jobs/$RESTORE_JOB_ID")")" status)
  [[ "$JOB_ST" != "running" ]] && break
  sleep 0.25
done
check "$( [[ "$SEEN_MAINT" == "1" ]]; echo $?)" "4: tiklash paytida boshqa so'rov -> 503 maintenance (kamida bir marta kuzatildi)"

RST=$(job_wait "$RESTORE_JOB_ID" 300)
check "$( [[ "$RST" == "ok" ]]; echo $?)" "4: tiklash ishi -> ok" "$RST"

NEW_EXT=$(canon /extensions); NEW_IVR=$(canon /ivrs); NEW_TRUNK=$(canon /trunks); NEW_PROV=$(canon /settings/provisioning)
check "$( [[ "$NEW_EXT" == "$BASE_EXT" && "$NEW_IVR" == "$BASE_IVR" && "$NEW_TRUNK" == "$BASE_TRUNK" && "$NEW_PROV" == "$BASE_PROV" ]]; echo $?)" \
  "4: tiklashdan keyin holat zaxiradagiga TENG (/extensions,/ivrs,/trunks,/settings/provisioning)"

docker rm -f m4b-proof-101 >/dev/null 2>&1 || true
docker run -d --name m4b-proof-101 --network "$NET" "$PY_IMAGE" sleep infinity >/dev/null
docker cp "$SIPP_DIR/register_only.py" m4b-proof-101:/tmp/register_only.py
# Telefon (m2a_phone) bilan BIR XIL port: contact URI bir xil bo'ladi va almashtiriladi. Boshqa port
# 2-contact qoldirardi — `Dial(PJSIP/101)` faqat BIRINCHI contact'ga INVITE yuboradi (o'lik 5090 tanlansa FAIL).
REG=$(docker exec m4b-proof-101 python3 /tmp/register_only.py asterisk 5060 5070 "101" "${SECRET[101]}")
check "$( [[ "$REG" == REGISTER\ OK:* ]]; echo $?)" "4: 101 eski (zaxiradagi) parol bilan REGISTER -> 200" "$REG"

for f in m2a_phone.py vm_caller.py outbound_invite.py; do docker cp "$SIPP_DIR/$f" "m4b-proof-101:/tmp/$f"; done
docker exec -d m4b-proof-101 sh -c "cd /tmp && python3 m2a_phone.py serve 101 '${SECRET[101]}' 5070 12000 /tmp/mode 300 > /tmp/phone.log 2>&1"
docker exec m4b-proof-101 sh -c "echo answer > /tmp/mode"
wait_until 15 docker exec m4b-proof-101 grep -q 'REGISTER_RESULT: OK' /tmp/phone.log
check "$( docker exec m4b-proof-101 grep -q 'REGISTER_RESULT: OK' /tmp/phone.log; echo $?)" \
  "4: tiklashdan keyin 101 telefon qayta ro'yxatdan o'tdi" "$(docker exec m4b-proof-101 tail -3 /tmp/phone.log)"
ast "pjsip set logger on" >/dev/null 2>&1
docker exec m4b-proof-ph sh -c "cd /tmp && python3 m2a_phone.py call 102 '${SECRET[102]}' 5073 13004 101 3 >/tmp/call3.log 2>&1"
ast "pjsip set logger off" >/dev/null 2>&1
check "$( grep -Eq 'BYE_SENT|REMOTE_BYE|INVITE_FINAL: SIP/2.0 2' <(docker exec m4b-proof-ph cat /tmp/call3.log); echo $?)" \
  "4: tiklashdan keyin 102->101 qo'ng'iroq javob topadi" "$(docker exec m4b-proof-ph cat /tmp/call3.log | tail -3)"
if ! grep -Eq 'BYE_SENT|REMOTE_BYE|INVITE_FINAL: SIP/2.0 2' <(docker exec m4b-proof-ph cat /tmp/call3.log); then
  echo "--- DIAG call3 ---"
  docker exec m4b-proof-ph cat /tmp/call3.log | head -20
  ast "pjsip show endpoint 102" | grep -E "Endpoint:|context|identify" | head -5
  ast "dialplan show t1-from-internal" | head -4
  sql "select id,status,dialplan_sha256,left(coalesce(error,''),160) from config_revisions order by id desc limit 4"
  docker logs --since 3m "$AST" 2>&1 | grep -E "102|404|No matching|Failed to authenticate|anonymous" | tail -15
  ast "pjsip show aor 101" | grep -E "contact|max_contacts|remove_existing" | head -6
  docker exec m4b-proof-101 sh -c "tail -8 /tmp/phone.log; cat /tmp/mode" 2>&1
  docker logs --since 2m "$AST" 2>&1 | grep -aE "^(INVITE|SIP/2.0) |Transmitting|Received SIP|Called|Unreachable" | tail -20
  echo "--- /DIAG ---"
fi

C=$(http_code "$API_BASE/audio/$AUDIO_MOH_ID/stream" "${AUTH[@]}")
check "$( [[ "$C" == "200" ]]; echo $?)" "4: MOH audio fayli (o'chirilgan edi) tiklangan -> /audio/.../stream 200" "$C"
C=$(http_code "$API_BASE/recordings/$REC_ID/audio" "${AUTH[@]}")
check "$( [[ "$C" == "200" ]]; echo $?)" "4: qo'ng'iroq yozuvi tiklangan -> /recordings/.../audio 200" "$C"
CDR_N=$(sql "select count(*) from cdr")
check "$( [[ "$CDR_N" -gt "0" ]]; echo $?)" "4: CDR tarixi bor (${CDR_N} yozuv)"

job_diag() { # job_id -> job tanasi + API xato logi (faqat FAIL bo'lganda)
  echo "DIAG job: $(jbody "$(api GET "/backups/jobs/$1")")"
  docker logs --since 15m "$APICONT" 2>&1 | grep -iE "error|exception|traceback|restore|zaxira" -A2 | grep -v "GET /api" | tail -40
}
PRE_ID=$(pre_restore_of "$RESTORE_JOB_ID")
check "$( [[ -n "$PRE_ID" ]]; echo $?)" "4: restore_jobs.pre_restore_backup_id mavjud" "$PRE_ID"
R=$(api POST "/backups/$PRE_ID/restore" '{"confirm":"TIKLASH"}')
PRE_JOB_ID=$(jget "$(jbody "$R")" job id)
PST=no_job; [[ -n "$PRE_JOB_ID" ]] && PST=$(job_wait "$PRE_JOB_ID" 300)
[[ "$PST" == "ok" ]] || job_diag "$PRE_JOB_ID"
check "$( [[ "$PST" == "ok" ]]; echo $?)" "4: pre_restore zaxirani tiklash (bekor qilish) -> ok" "$PST / $(echo "$R" | tr '\n' ' ')"
check "$( has_number /extensions 150; echo $?)" "4: bekor qilingach ext 150 qaytdi"

# ================================================================== 5
echo "=== 5. disaster recovery (boshqa INNOVA_DB_KEY) ==="
BJ=$(api POST /backups "{\"components\":$ALL_COMPONENTS}")
BK5=$(jget "$(jbody "$BJ")" job id)
ST=$(backup_final_status "$BK5" 180)
check "$( [[ "$ST" == "ok" ]]; echo $?)" "5: DR uchun to'liq zaxira -> ok" "$ST"
C=$(api_download "/backups/$BK5/download" /tmp/m4b-dr.ibk)
check "$( [[ "$C" == "200" ]]; echo $?)" "5: zaxira faylini yuklab olish -> 200" "$C"

(cd "$DEPLOY_DIR" && docker compose down -v) || true
NEW_KEY=$(openssl rand -hex 32)
sed -i "s/^INNOVA_DB_KEY=.*/INNOVA_DB_KEY=$NEW_KEY/" "$DEPLOY_DIR/.env"
unset NEW_KEY
(cd "$DEPLOY_DIR" && docker compose up -d) || { fail "5: boshqa INNOVA_DB_KEY bilan up"; exit 1; }
wait_api

login "$TEMP_DR_PASSWORD" || { fail "5: fresh stack bootstrap login"; exit 1; }
OLD_LOGIN_FAILS=$(login_as admin "$ADMIN_PASSWORD")
check "$( [[ -z "$OLD_LOGIN_FAILS" ]]; echo $?)" "5: fresh stackda ASL parol ishlamaydi (bo'sh DB isboti)" "$OLD_LOGIN_FAILS"

DRU=$(jbody "$(api_upload /backups/upload /tmp/m4b-dr.ibk)")
DR_BK_ID=$(jget "$DRU" item id)
check "$( [[ -n "$DR_BK_ID" ]]; echo $?)" "5: POST /backups/upload -> item" "$DRU"
INS=$(api POST "/backups/$DR_BK_ID/inspect" "{\"passphrase\":\"$BACKUP_PASSPHRASE\"}")
check "$( [[ "$(jcode "$INS")" == "200" && "$(jget "$(jbody "$INS")" checks sha256)" == "ok" ]]; echo $?)" \
  "5: inspect (boshqa server kaliti) -> sha256 ok" "$INS"

R=$(api POST "/backups/$DR_BK_ID/restore" "{\"confirm\":\"TIKLASH\",\"passphrase\":\"$BACKUP_PASSPHRASE\"}")
DR_JOB_ID=$(jget "$(jbody "$R")" job id)
DRST=$(job_wait "$DR_JOB_ID" 360)
[[ "$DRST" == "ok" ]] || job_diag "$DR_JOB_ID"
check "$( [[ "$DRST" == "ok" ]]; echo $?)" "5: DR tiklash -> ok" "$DRST"

TRUNK_SECRET_OBSERVED=$(trunk_secret_via_ps_auths "$TRUNK_ID")
check "$( [[ "$TRUNK_SECRET_OBSERVED" == "$TRUNK_PASS" ]]; echo $?)" \
  "5: trunk siri qayta kalitlashdan keyin to'g'ri (re-key, realtime view)" "$TRUNK_SECRET_OBSERVED"

docker run -d --name m4b-proof-dr --network "$NET" "$PY_IMAGE" sleep infinity >/dev/null
docker cp "$SIPP_DIR/register_only.py" m4b-proof-dr:/tmp/register_only.py
REG=$(docker exec m4b-proof-dr python3 /tmp/register_only.py asterisk 5060 5090 "101" "${SECRET[101]}")
check "$( [[ "$REG" == REGISTER\ OK:* ]]; echo $?)" "5: DR'dan keyin 101 eski parol bilan REGISTER -> 200" "$REG"

check "$( [[ -z "$(login_as admin "$TEMP_DR_PASSWORD")" ]]; echo $?)" "5: vaqtinchalik DR admin endi ishlamaydi"
login "$ADMIN_PASSWORD" || { fail "5: zaxiradagi admin bilan login"; exit 1; }
pass "5: zaxiradagi (asl) admin login -> ishlaydi"

(cd "$DEPLOY_DIR" && docker compose down -v) || true
cp -a "$ENV_BAK" "$DEPLOY_DIR/.env"
(cd "$DEPLOY_DIR" && docker compose up -d) || { fail "5: asl .env bilan qayta ko'tarish"; exit 1; }
wait_api
login "$ADMIN_PASSWORD" || { fail "5: asl .env'dan keyin bootstrap login"; exit 1; }

# ================================================================== 6
echo "=== 6. jadval ==="
api PUT /settings/backup/passphrase "{\"passphrase\":\"$BACKUP_PASSPHRASE\"}" >/dev/null
read -r SCHED_WD SCHED_TIME <<<"$(python3 -c "
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
t = datetime.now(ZoneInfo('Asia/Tashkent')) + timedelta(minutes=1)
print(t.weekday(), t.strftime('%H:%M'))")"
UA=$(updated_at_of /settings/backup)
R=$(api PUT /settings/backup "{\"updated_at\":\"$UA\",\"schedule\":{\"enabled\":true,\"frequency\":\"daily\",
  \"weekday\":$SCHED_WD,\"time\":\"$SCHED_TIME\",\"components\":[\"config\"]}}")
check "$( [[ "$(jcode "$R")" == "200" ]]; echo $?)" "6: jadval -> $SCHED_TIME (1 daqiqadan keyin)" "$R"
BEFORE=$(sql "select count(*) from backups where kind='scheduled'")
SCHED_OK=1
scheduled_appeared() { [[ "$(sql "select count(*) from backups where kind='scheduled'")" -gt "$BEFORE" ]]; }
wait_until 120 scheduled_appeared && SCHED_OK=0
check "$SCHED_OK" "6: <=120 s ichida 1 ta scheduled zaxira paydo bo'ldi"

# ================================================================== 7
echo "=== 7. operator ==="
UJ=$(api POST /users '{"username":"m4b_op","full_name":"M4b Op","role":"operator","password":"M4bOpTmp!123"}')
OP_TOKEN=$(login_as m4b_op 'M4bOpTmp!123')
C=$(jcode "$(api_as "$OP_TOKEN" GET /backups)")
check "$( [[ "$(jcode "$UJ")" == "201" && "$C" == "403" ]]; echo $?)" "7: operator -> /backups 403" "$UJ / $C"

echo
echo "=== NATIJA: $PASS PASS / $FAIL FAIL ==="
[[ "$FAIL" == "0" ]]
