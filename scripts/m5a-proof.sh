#!/usr/bin/env bash
# Innova PBX — M5a (FreePBX'dan ko'chirish) proof (replica/m5a-contract.md §5, bandlar 1-10;
# UI — web/scripts/m5a-real-check.mjs, bu skript JAVOBGAR EMAS):
#   1. RBAC (operator 403), yaroqsiz to'plam -> 422 bundle_invalid, export-script `bash -n` dan o'tadi.
#   2. Haqiqiy FreePBX 17 to'plami (tests/freepbx-fixture/bundle) -> analyze -> aniq sonlar; rejada sir yo'q.
#   3. apply: confirm'siz 422, parolsiz 409 passphrase_required, to'g'ri -> ok, pre_import zaxira, reviziya.
#   4. Innova bazasida mazmun (yo'naltirish/DND/CID/follow-me/TC/IVR/DID/outbound/ip trunk/RG/queue/...).
#   5. Asterisk: 101 FreePBX dagi parol bilan REGISTER 200; DID 998712345601 -> IVR javob beradi.
#   6. Idempotentlik: qayta yuklash -> hammasi skip, yangi qator 0.
#  10. DELETE /jobs/{id} -> to'plam fayli yo'q; audit yozuvlari, sirlar audit/logda yo'q.
#   9. pre_import zaxirani tiklash -> import qilingan obyektlar yo'q.
#   8. Atomarlik: INNOVA_TEST_FAIL_AT=routes -> failed, DB va audio fayllar o'zgarmagan.
#   7. To'qnashuv: qo'lda yaratilgan 101 -> conflict, replace 422, qolganlari import, 101 ga bog'lanish.
# (Tartib ataylab: 9 -> 8 -> 7 toza holatda ishlashi uchun.)
#
# Foydalanish:
#   scripts/m5a-proof.sh            # joriy `innova-m0` stack (M5a qoldiqlari bo'lsa — exit 2)
#   scripts/m5a-proof.sh --fresh    # avval `docker compose down -v` + build + up -d
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
UAC_IP="172.28.0.95"
M=/migration/freepbx
BUNDLE="$ROOT_DIR/tests/freepbx-fixture/bundle/fpbx-export-fixture.tar.gz"
BACKUP_PASSPHRASE="M5aZaxiraParoli!2026"
# Fixture'dagi SINOV sirlari (tests/freepbx-fixture/seed.sh) — rejada/auditda/logda chiqmasligi kerak
SECRET_NEEDLES=(SinovSecret SinovTrunkSecret SinovRoutePass '"1105"' '"4321"' '"4242"')

# shellcheck source=lib/m2a_common.sh
source "$LIB_DIR/m2a_common.sh"
# shellcheck source=lib/m3b_common.sh
source "$LIB_DIR/m3b_common.sh"
# shellcheck source=lib/m4b_common.sh
source "$LIB_DIR/m4b_common.sh"

ADMIN_PASSWORD="${PROOF_ADMIN_PASSWORD:-$(grep -E '^PROOF_ADMIN_PASSWORD=' "$DEPLOY_DIR/.env" | cut -d= -f2-)}"
[[ -n "$ADMIN_PASSWORD" ]] || { echo "PROOF_ADMIN_PASSWORD deploy/.env da yo'q"; exit 2; }
[[ -f "$BUNDLE" ]] || { echo "fixture to'plam yo'q: $BUNDLE"; exit 2; }

CONTAINERS=(m5a-proof-ph m5a-proof-uac)
api_env() { # [KEY=VAL] -> api konteynerini shu muhit bilan qayta yaratadi
  (cd "$DEPLOY_DIR" && env "$@" docker compose -p "$PROJECT" up -d --no-deps --force-recreate api >/dev/null 2>&1)
  wait_api
}
cleanup() {
  docker rm -f "${CONTAINERS[@]}" >/dev/null 2>&1 || true
  rm -rf /tmp/m5a-bad
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
LEFTOVER=$(jbody "$(api GET "$M/jobs")" | python3 -c "import json,sys;print(len(json.load(sys.stdin)['items']))" 2>/dev/null)
if [[ "$LEFTOVER" != "0" ]]; then
  echo "Stekda oldingi M5a isbot qoldiqlari bor (jobs=$LEFTOVER) — 'scripts/m5a-proof.sh --fresh' bilan ishga tushiring."
  exit 2
fi

# ---------------------------------------------------------------- yordamchilar
mjob() { jbody "$(api GET "$M/jobs/$1")"; }
mjob_wait() { # job_id "final1 final2" [max_s] -> stdout: oxirgi status
  local id="$1" finals=" $2 " max="${3:-240}" i=0 st=""
  while (( i < max * 2 )); do
    st=$(jget "$(mjob "$id")" item status)
    [[ -n "$st" && "$finals" == *" $st "* ]] && { echo "$st"; return 0; }
    sleep 0.5; i=$((i + 1))
  done
  echo "${st:-timeout}"
}
upload_analyze() { # fayl -> stdout: job_id (analyzed bo'lguncha kutadi; xato bo'lsa bo'sh)
  local r id st
  r=$(api_upload "$M/upload" "$1"); id=$(jget "$(jbody "$r")" item id)
  [[ -n "$id" ]] || { echo "upload: $r" >&2; return 1; }
  r=$(api POST "$M/jobs/$id/analyze" '{}')
  [[ "$(jcode "$r")" == "202" ]] || { echo "analyze: $r" >&2; return 1; }
  st=$(mjob_wait "$id" "analyzed failed" 240)
  [[ "$st" == "analyzed" ]] || { echo "analyze status=$st: $(mjob "$id")" >&2; return 1; }
  echo "$id"
}
summary_of() { # job_id kind action -> summary.by_kind[kind][action] (yo'q -> 0)
  mjob "$1" | python3 -c "
import json, sys
s = (json.load(sys.stdin)['item'].get('summary') or {}).get('by_kind', {})
print((s.get(sys.argv[1]) or {}).get(sys.argv[2], 0))" "$2" "$3"
}
plan_all() { # job_id -> barcha reja elementlari (JSON massiv, sahifalab)
  local id="$1" page=1 out="[]" chunk
  while :; do
    chunk=$(jbody "$(api GET "$M/jobs/$id/plan?page=$page&page_size=200")")
    out=$(python3 -c "
import json, sys
a = json.loads(sys.argv[1]); c = json.loads(sys.argv[2])
print(json.dumps(a + c['items']))" "$out" "$chunk") || break
    [[ $(jget "$chunk" items 0 kind) == "" ]] && break
    (( $(python3 -c "import json,sys;print(len(json.loads(sys.argv[1])))" "$out") >= $(jget "$chunk" total) )) && break
    page=$((page + 1))
  done
  echo "$out"
}
plan_item() { # plan_json kind number_yoki_name field -> qiymat
  python3 -c "
import json, sys
items = json.loads(sys.argv[1])
it = next((i for i in items if i['kind'] == sys.argv[2] and sys.argv[3] in ((i.get('number') or ''), i['name'])), None)
v = None if it is None else it.get(sys.argv[4])
print('' if v is None else (json.dumps(v) if isinstance(v, (list, dict, bool)) else v))" "$1" "$2" "$3" "$4"
}
no_secrets() { # matn -> 0 (sir topilmasa)
  local n; for n in "${SECRET_NEEDLES[@]}"; do grep -qF -- "$n" <<<"$1" && { echo "topildi: $n" >&2; return 1; }; done
  return 0
}
tgt() { sql "select target_id from $1 where $2 limit 1"; }    # jadval shart -> target_id
ext_tgt() { tgt extensions "number='$1'"; }
counts() { sql "select (select count(*) from extensions)||'/'||(select count(*) from trunks)||'/'||(select count(*) from ivrs)
  ||'/'||(select count(*) from inbound_routes)||'/'||(select count(*) from outbound_routes)||'/'||(select count(*) from queues)
  ||'/'||(select count(*) from ring_groups)||'/'||(select count(*) from audio_files)||'/'||(select count(*) from moh_classes)
  ||'/'||(select count(*) from blacklist)||'/'||(select count(*) from voicemail_boxes)||'/'||(select count(*) from conferences)"; }
TCODE=$(sql "select code from tenants limit 1")
sounds_n() { docker exec "$APICONT" sh -c "find /var/lib/innova/sounds/$TCODE /var/lib/innova/moh 2>/dev/null -type f | wc -l"; }

# ================================================================== 1
echo "=== 1. RBAC / yaroqsiz to'plam / export-script ==="
UJ=$(api POST /users '{"username":"m5a_op","full_name":"M5a Op","role":"operator","password":"M5aOpTmp!123"}')
OP_TOKEN=$(login_as m5a_op 'M5aOpTmp!123')
C1=$(jcode "$(api_as "$OP_TOKEN" GET "$M/jobs")")
C2=$(jcode "$(api_as "$OP_TOKEN" GET "$M/export-script")")
check "$( [[ "$(jcode "$UJ")" == "201" && "$C1" == "403" && "$C2" == "403" ]]; echo $?)" "1: operator -> /migration/freepbx 403" "$UJ / $C1 / $C2"

mkdir -p /tmp/m5a-bad && python3 - <<'PY'
import io, json, os, tarfile
d = "/tmp/m5a-bad"
with open(f"{d}/random.tar.gz", "wb") as f:
    f.write(os.urandom(4096))
def mk(name, members):
    with tarfile.open(f"{d}/{name}", "w:gz") as t:
        for path, data in members:
            ti = tarfile.TarInfo(path); ti.size = len(data); t.addfile(ti, io.BytesIO(data))
mk("badformat.tar.gz", [("fpbx-export-x/meta.json", json.dumps({"format": "BOSHQA/9"}).encode())])
mk("traversal.tar.gz", [("fpbx-export-x/meta.json", json.dumps({"format": "INNOVA-FPBX-EXPORT/1", "tables": []}).encode()),
                        ("fpbx-export-x/../../../tmp/m5a-pwned", b"x")])
PY
bad_rejected() { # fayl -> 0 agar upload YOKI analyze 422 bundle_invalid bersa
  local r id
  r=$(api_upload "$M/upload" "$1")
  err_is "$r" 422 bundle_invalid && return 0
  id=$(jget "$(jbody "$r")" item id); [[ -n "$id" ]] || return 1
  r=$(api POST "$M/jobs/$id/analyze" '{}')
  err_is "$r" 422 bundle_invalid && { api DELETE "$M/jobs/$id" >/dev/null; return 0; }
  [[ "$(mjob_wait "$id" "failed analyzed" 60)" == "failed" && "$(jget "$(mjob "$id")" item error code)" == "bundle_invalid" ]] \
    && { api DELETE "$M/jobs/$id" >/dev/null; return 0; }
  return 1
}
for f in random badformat traversal; do
  check "$( bad_rejected "/tmp/m5a-bad/$f.tar.gz"; echo $?)" "1: yaroqsiz to'plam ($f) -> 422 bundle_invalid"
done
check "$( docker exec "$APICONT" test ! -e /tmp/m5a-pwned; echo $?)" "1: '../' yo'l API konteynerida fayl yaratmadi"

api_download "$M/export-script" /tmp/m5a-export.sh >/dev/null
check "$( bash -n /tmp/m5a-export.sh && grep -q 'INNOVA-FPBX-EXPORT/1' /tmp/m5a-export.sh; echo $?)" "1: export-script yuklab olindi va bash -n dan o'tdi"
check "$( [[ "$(jbody "$(api GET "$M/jobs")" | python3 -c "import json,sys;print(len(json.load(sys.stdin)['items']))")" == "0" ]] \
  || [[ -n "$(jbody "$(api GET "$M/jobs")")" ]]; echo $?)" "1: jobs ro'yxati o'qiladi"

# ================================================================== 2
echo "=== 2. haqiqiy FreePBX 17 to'plami -> analyze -> aniq sonlar ==="
JOB1=$(upload_analyze "$BUNDLE")
check "$( [[ -n "$JOB1" ]]; echo $?)" "2: upload -> analyze -> analyzed" "$JOB1"
SRC_VER=$(jget "$(mjob "$JOB1")" item source_meta freepbx_version)
check "$( [[ "$SRC_VER" == 17.* ]]; echo $?)" "2: source_meta.freepbx_version = 17.x" "$SRC_VER"

EXPECT="extension:6 trunk:2 inbound_route:3 outbound_route:2 ring_group:1 queue:1 ivr:1 time_group:1 holiday:1
time_condition:1 announcement:1 audio:1 moh:1 conference:1 voicemail:1 blacklist:1 feature_code:1"
for kv in $EXPECT; do
  k=${kv%%:*}; want=${kv#*:}; got=$(summary_of "$JOB1" "$k" create)
  check "$( [[ "$got" == "$want" ]]; echo $?)" "2: reja $k create = $want" "got=$got"
done
PLAN1=$(plan_all "$JOB1")
EXT_NUMS=$(python3 -c "import json,sys;print(' '.join(sorted(i['number'] for i in json.loads(sys.argv[1]) if i['kind']=='extension')))" "$PLAN1")
check "$( [[ "$EXT_NUMS" == "101 102 103 105 106 107" ]]; echo $?)" "2: ichki raqamlar 101,102,103,105,106,107" "$EXT_NUMS"
check "$( [[ "$(plan_item "$PLAN1" moh default action)" != "create" ]]; echo $?)" "2: MOH 'default' yaratilmaydi (skip/ignored)" \
  "$(plan_item "$PLAN1" moh default action)"
IGN=$(jbody "$(api GET "$M/jobs/$JOB1/ignored")")
check "$( python3 -c "
import json, sys
it = json.loads(sys.argv[1])['items']
sys.exit(0 if any('1234' in (i.get('key') or '') and 'voicemail' in (i.get('table') or '') for i in it) else 1)" "$IGN"; echo $?)" \
  "2: namunaviy pochta qutisi 1234 -> ignored" "$(echo "$IGN" | head -c 400)"
WARN=$(jbody "$(api GET "$M/jobs/$JOB1/warnings")")
check "$( grep -q custom_dialplan_present <<<"$WARN"; echo $?)" "2: custom_dialplan_present ogohlantirishi" "$(echo "$WARN" | head -c 300)"
check "$( no_secrets "$PLAN1$IGN$WARN$(mjob "$JOB1")"; echo $?)" "2: reja/ignored/warnings/job javobida sir YO'Q"
check "$( [[ "$(plan_item "$PLAN1" extension 101 has_secret)" == "true" ]]; echo $?)" "2: ext 101 has_secret=true (qiymatsiz)"

# ================================================================== 3
echo "=== 3. apply ==="
BASE_REV=$(sql "select count(*) from config_revisions")
R=$(api POST "$M/jobs/$JOB1/apply" '{"options":{"rotate_weak_secrets":false}}')
check "$( err_is "$R" 422 confirm_required; echo $?)" "3: confirm'siz apply -> 422 confirm_required" "$R"
R=$(api POST "$M/jobs/$JOB1/apply" '{"confirm":"KOCHIRISH","options":{"rotate_weak_secrets":false}}')
check "$( err_is "$R" 409 passphrase_required; echo $?)" "3: zaxira parolisiz apply -> 409 passphrase_required" "$R"
check "$( [[ "$(jget "$(mjob "$JOB1")" item backup_ready)" == "False" ]]; echo $?)" "3: job.backup_ready=false (parol yo'q)"
PJ=$(api PUT /settings/backup/passphrase "{\"passphrase\":\"$BACKUP_PASSPHRASE\"}")
check "$( [[ "$(jcode "$PJ")" == "200" ]]; echo $?)" "3: zaxira paroli o'rnatildi" "$PJ"
R=$(api POST "$M/jobs/$JOB1/apply" '{"confirm":"KOCHIRISH","options":{"rotate_weak_secrets":false}}')
check "$( [[ "$(jcode "$R")" == "202" ]]; echo $?)" "3: apply -> 202" "$R"
ST=$(mjob_wait "$JOB1" "ok failed" 280)
check "$( [[ "$ST" == "ok" ]]; echo $?)" "3: apply ishi -> ok" "$ST / $(mjob "$JOB1" | head -c 600)"
PRE1=$(jget "$(mjob "$JOB1")" item pre_import_backup_id)
check "$( [[ -n "$PRE1" && "$(sql "select kind||':'||status from backups where id='$PRE1'")" == pre_import:ok ]]; echo $?)" \
  "3: pre_import zaxira yaratilgan (kind=pre_import, ok)" "$PRE1 / $(sql "select kind||':'||status from backups where id='$PRE1'")"
REV1=$(jget "$(mjob "$JOB1")" item result revision_id)
check "$( [[ -n "$REV1" && "$(sql "select count(*) from config_revisions")" -gt "$BASE_REV" ]]; echo $?)" \
  "3: dialplan reviziya yaratildi (result.revision_id)" "$REV1 / $(sql "select id||':'||status from config_revisions order by created_at desc limit 1")"
check "$( [[ "$(sql "select count(*) from audit_log where entity='migration' and diff::text like '%FreePBX importi%'")" -ge 1 \
  && "$(sql "select count(*) from config_revisions where id::text='$REV1' and status in ('applied','ok')")" == 1 ]]; echo $?)" \
  "3: reviziya «FreePBX importi» qo'llangan" "$(sql "select status from config_revisions where id::text='$REV1'")"

# ================================================================== 4
echo "=== 4. Innova bazasida mazmun ==="
X102=$(sql "select forward_always||'|'||forward_busy||'|'||coalesce(no_answer_target_id::text,'') from extensions where number='102'")
check "$( [[ "$X102" == "106|106|$(ext_tgt 105)" ]]; echo $?)" "4: ext 102 CF=106, CFB=106, javobsiz -> 105" "$X102"
X106=$(sql "select dnd||'|'||coalesce(outbound_callerid,'') from extensions where number='106'")
check "$( [[ "$X106" == "true|+998901110106" ]]; echo $?)" "4: ext 106 DND=true, CID=+998901110106" "$X106"
FM=$(sql "select follow_me::text from extensions where number='107'")
# Fixture: FreePBX `FOLLOWME_DISABLED` standarti -> astdb ddial=EXTENSION (o'chiq); M5b: strategiya/ichki raqam ham.
check "$( grep -q 0991234567 <<<"$FM" && grep -q '"enabled": false' <<<"$FM" && grep -q '"strategy": "sequential"' <<<"$FM" \
  && grep -q '"include_extension": true' <<<"$FM"; echo $?)" "4: ext 107 follow_me [0991234567], hunt -> sequential, ddial=EXTENSION -> o'chiq" "$FM"
check "$( [[ "$(sql "select count(*) from extensions where number in ('101','102','103','105','106','107')")" == 6 ]]; echo $?)" "4: 6 ta ichki raqam"
IVR_T=$(sql "select target_id from ivrs limit 1"); ANN_T=$(sql "select target_id from announcements limit 1")
RG_T=$(sql "select target_id from ring_groups limit 1"); Q_T=$(sql "select target_id from queues limit 1")
TC=$(sql "select open_target_id||'|'||closed_target_id from time_conditions limit 1")
check "$( [[ "$TC" == "$IVR_T|$ANN_T" ]]; echo $?)" "4: TC ochiq -> IVR, yopiq -> e'lon (TESKARI EMAS)" "$TC"
check "$( [[ "$(sql "select count(*) from time_ranges")" -ge 1 && "$(sql "select count(*) from holidays where to_char(day,'MM-DD')='01-01'")" == 1 ]]; echo $?)" \
  "4: vaqt guruhi oraliqlari + 1-yanvar bayrami" "$(sql "select weekdays||' '||start_time||'-'||end_time from time_ranges limit 1")"
OPTS=$(sql "select string_agg(digit||'='||target_id, ',' order by digit) from ivr_options")
check "$( [[ "$OPTS" == "1=$(ext_tgt 101),2=$RG_T,3=$Q_T" ]]; echo $?)" "4: IVR 1->101, 2->RG 600, 3->Q 700" "$OPTS"
check "$( [[ "$(tgt inbound_routes "did='998712345601'")" == "$IVR_T" ]]; echo $?)" "4: DID 998712345601 -> IVR"
TCOND_T=$(sql "select target_id from time_conditions limit 1")
check "$( [[ "$(tgt inbound_routes "did='998712345602'")" == "$TCOND_T" ]]; echo $?)" "4: DID 998712345602 -> vaqt sharti"
check "$( [[ "$(sql "select count(*) from inbound_routes")" == 3 && "$(tgt inbound_routes "coalesce(did,'')=''")" == "$RG_T" ]]; echo $?)" \
  "4: catch-all kiruvchi -> RG 600" "$(sql "select coalesce(did,'<null>')||'->'||target_id from inbound_routes")"
OB=$(sql "select p.strip_prefix||'|'||p.add_prefix||'|'||p.pattern from outbound_route_patterns p join outbound_routes r on r.id=p.route_id where r.name like 'Sinov-Mobil%' limit 1")
check "$( [[ "$OB" == 0\|+998\|* ]]; echo $?)" "4: outbound Mobil: strip 0, add +998" "$OB"
OBT=$(sql "select string_agg(t.auth_mode, ',' order by rt.position) from outbound_route_trunks rt join trunks t on t.id=rt.trunk_id join outbound_routes r on r.id=rt.route_id where r.name like 'Sinov-Mobil%'")
check "$( [[ "$OBT" == "register,ip" ]]; echo $?)" "4: outbound Mobil trunk tartibi [register, ip]" "$OBT"
check "$( [[ "$(sql "select count(*) from outbound_routes where pin_hash is not null and name like 'Sinov-Mobil%'")" == 1 ]]; echo $?)" "4: outbound Mobil PIN (xesh) ko'chdi"
IPT=$(sql "select array_to_string(match_ips,',') from trunks where auth_mode='ip'")
check "$( [[ "$IPT" == *203.0.113.10* ]]; echo $?)" "4: ip trunk match_ips 203.0.113.10/32" "$IPT"
RT=$(sql "select username||'|'||host||'|'||coalesce(outbound_callerid,'')||'|'||max_channels from trunks where auth_mode='register'")
check "$( [[ "$RT" == "sinovuser1|sip.sinov-provider.test|+998901112233|10" ]]; echo $?)" "4: register trunk user/host/CID/kanal" "$RT"
RGM=$(sql "select count(extension_id)||'/'||string_agg(external_number, ',') from ring_group_members")
check "$( [[ "$RGM" == "3/0991234567" ]]; echo $?)" "4: RG 600: 3 ichki + tashqi 0991234567" "$RGM"
QM=$(sql "select count(*)||'/'||count(*) filter (where dynamic) from queue_members")
check "$( [[ "$QM" == "3/1" ]]; echo $?)" "4: Q 700: 2 statik + 1 dinamik" "$QM"
for n in 600 700 8000; do
  check "$( [[ -n "$(sql "select target_id from dial_numbers where number='$n'")" ]]; echo $?)" "4: raqam $n terilishi mumkin (dial_numbers)"
done
check "$( [[ "$(sql "select string_agg(mailbox,',') from voicemail_boxes")" == "105" ]]; echo $?)" "4: ovozli pochta faqat 105 (1234 yo'q)" \
  "$(sql "select string_agg(mailbox,',') from voicemail_boxes")"
check "$( [[ "$(sql "select count(*) from blacklist where number='0998887766'")" == 1 ]]; echo $?)" "4: qora ro'yxat 0998887766"
check "$( [[ "$(sql "select code from feature_codes where feature='voicemail'")" == "*970" ]]; echo $?)" "4: feature code voicemail -> *970"
check "$( [[ "$(sql "select count(*) from moh_classes where name='sinov-moh'")" == 1 ]]; echo $?)" "4: MOH sinov-moh"
check "$( [[ "$(sql "select count(*) from conferences where pin_hash is not null and admin_pin_hash is not null")" == 1 ]]; echo $?)" "4: konferensiya 8000 PIN'lari (xesh)"
AUD=$(sql "select id from audio_files where source<>'system' order by created_at desc limit 1")
C=$(http_code "$API_BASE/audio/$AUD/stream" "${AUTH[@]}")
check "$( [[ "$C" == 200 ]]; echo $?)" "4: import qilingan yozuv eshitiladi (/audio/../stream 200)" "$C"
check "$( [[ "$(sql "select count(*) from announcements where audio_file_id='$AUD'")" == 1 ]]; echo $?)" "4: e'lon -> import qilingan yozuv"

# ================================================================== 5
echo "=== 5. Asterisk: REGISTER (FreePBX paroli) + DID -> IVR ==="
ep_101() { ast "pjsip show endpoint 101" | grep -q "Endpoint:  *101"; }  # apply'dan so'ng realtime — bir oz kutish
check "$(wait_until 10 ep_101; echo $?)" "5: pjsip endpoint 101 bor"
docker run -d --name m5a-proof-ph --network "$NET" "$PY_IMAGE" sleep infinity >/dev/null
docker cp "$SIPP_DIR/register_only.py" m5a-proof-ph:/tmp/register_only.py
REG=$(docker exec m5a-proof-ph python3 /tmp/register_only.py asterisk 5060 5090 101 'SinovSecret101!' 2>&1)
check "$( grep -q "REGISTER OK" <<<"$REG"; echo $?)" "5: 101 FreePBX dagi parol bilan REGISTER -> 200" "$REG"
REGB=$(docker exec m5a-proof-ph python3 /tmp/register_only.py asterisk 5060 5091 101 'NotoGriParol1!' 2>&1)
check "$( ! grep -q "REGISTER OK" <<<"$REGB"; echo $?)" "5: noto'g'ri parol bilan REGISTER rad etiladi" "$REGB"

docker run -d --name m5a-proof-uac --network "$NET" --ip "$UAC_IP" "$PY_IMAGE" sleep infinity >/dev/null
docker exec m5a-proof-uac bash -c "apt-get update -qq && apt-get install -y -qq sip-tester >/tmp/i.log 2>&1"
IPT_ID=$(sql "select id from trunks where auth_mode='ip'")
IPT_AT=$(jget "$(jbody "$(api GET "/trunks/$IPT_ID")")" item updated_at)
[[ -n "$IPT_AT" ]] || IPT_AT=$(jbody "$(api GET /trunks)" | python3 -c "import json,sys;print(next(t['updated_at'] for t in json.load(sys.stdin)['items'] if t['id']=='$IPT_ID'))")
R=$(api PATCH "/trunks/$IPT_ID" "{\"updated_at\":\"$IPT_AT\",\"match_ips\":[\"$UAC_IP/32\"]}")
check "$( [[ "$(jcode "$R")" == 200 ]]; echo $?)" "5: import qilingan ip trunk match_ips -> sinov UAC IP" "$R"
wait_until 30 bash -c "docker exec $AST asterisk -rx 'pjsip show identifies' | grep -q '$UAC_IP'"
sed "s/712000000/998712345601/g; s/1500/6000/" "$SIPP_DIR/uac_trunk_invite.xml" > /tmp/m5a_uac.xml
docker cp /tmp/m5a_uac.xml m5a-proof-uac:/tmp/uac.xml
UAC_OUT=$(docker exec m5a-proof-uac sipp -sf /tmp/uac.xml -i "$UAC_IP" -p 5080 asterisk:5060 -m 1 -timeout 30s 2>&1 || true)
OK_COUNT=$(echo "$UAC_OUT" | grep "Successful call" | tail -1 | grep -oE '[0-9]+' | tail -1)
check "$( [[ "${OK_COUNT:-0}" -ge 1 ]]; echo $?)" "5: DID 998712345601 ga kiruvchi qo'ng'iroq javob topdi (SIPp)" "$(echo "$UAC_OUT" | tail -5)"
did_answered_ivr() {
  curl -s "$API_BASE/calls" "${AUTH[@]}" | python3 -c "
import json, sys
it = json.load(sys.stdin).get('items', [])
sys.exit(0 if any(i.get('did') == '998712345601' and i.get('disposition') == 'answered' for i in it) else 1)"
}
wait_until 20 did_answered_ivr
check "$( did_answered_ivr; echo $?)" "5: /calls: DID 998712345601 answered (IVR)" \
  "$(sql "select dcontext||' '||lastapp||' '||disposition from cdr order by start desc limit 2" | tr '\n' ';')"

# ================================================================== 6
echo "=== 6. idempotentlik ==="
BEFORE6=$(counts)
JOB2=$(upload_analyze "$BUNDLE")
CREATES=$(mjob "$JOB2" | python3 -c "
import json, sys
s = json.load(sys.stdin)['item']['summary']['by_kind']
print(sum(v.get('create', 0) for v in s.values()))")
check "$( [[ -n "$JOB2" && "$CREATES" == 0 ]]; echo $?)" "6: qayta analyze -> create=0" "$CREATES"
PLAN2=$(plan_all "$JOB2")
NONSKIP=$(python3 -c "
import json, sys
print(sum(1 for i in json.loads(sys.argv[1]) if i['action'] == 'create' or (i['action'] == 'skip' and i.get('reason') not in ('already_imported', 'default_moh', 'builtin'))))" "$PLAN2")
check "$( [[ "$NONSKIP" == 0 ]]; echo $?)" "6: hammasi skip already_imported" "$NONSKIP"
R=$(api POST "$M/jobs/$JOB2/apply" '{"confirm":"KOCHIRISH","options":{"rotate_weak_secrets":false}}')
ST=$(mjob_wait "$JOB2" "ok failed" 280)
check "$( [[ "$ST" == ok && "$(counts)" == "$BEFORE6" ]]; echo $?)" "6: qayta apply -> ok, yangi qator 0" "$ST / $BEFORE6 -> $(counts)"

# ================================================================== 10
echo "=== 10. DELETE / audit / sirlar ==="
BP=$(sql "select bundle_path from migration_jobs where id='$JOB1'")
check "$( [[ -n "$BP" ]] && docker exec "$APICONT" test -e "$BP"; echo $?)" "10: to'plam fayli diskda bor (DELETE dan oldin)" "$BP"
MODE=$(docker exec "$APICONT" sh -c "find '$BP' -maxdepth 0 -printf '%m'" 2>/dev/null)
check "$( [[ "$MODE" == 600 || "$MODE" == 700 ]]; echo $?)" "10: to'plam fayli/papka huquqi faqat egasiga ($MODE)"
R=$(api DELETE "$M/jobs/$JOB1")
check "$( [[ "$(jcode "$R")" == 204 ]] && ! docker exec "$APICONT" test -e "$BP"; echo $?)" "10: DELETE -> 204, to'plam fayli yo'q" "$R"
check "$( [[ "$(sql "select count(*) from extensions")" -ge 6 ]]; echo $?)" "10: import natijasi qoladi"
check "$( [[ "$(sql "select count(*) from audit_log where entity='migration' and diff::text like '%analyze%'")" -ge 1 && \
  "$(sql "select count(*) from audit_log where entity='migration' and diff::text like '%apply%'")" -ge 1 ]]; echo $?)" \
  "10: audit (entity=migration): analyze + apply" "$(sql "select action||':'||left(diff::text,80) from audit_log where entity='migration'" | tr '\n' ';')"
AUD_TXT=$(sql "select string_agg(diff::text, ' ') from audit_log where created_at > now() - interval '1 hour'")
check "$( no_secrets "$AUD_TXT"; echo $?)" "10: audit_log da sir yo'q"
check "$( no_secrets "$(docker logs "$APICONT" 2>&1)"; echo $?)" "10: API logida sir yo'q"
api_download "$M/jobs/$JOB2/report" /tmp/m5a-report.csv >/dev/null
check "$( [[ $(wc -l </tmp/m5a-report.csv) -gt 5 ]] && no_secrets "$(cat /tmp/m5a-report.csv)"; echo $?)" "10: CSV hisobot bor, sirsiz"

# ================================================================== 9
echo "=== 9. pre_import zaxirani tiklash (bekor qilish) ==="
R=$(api POST "/backups/$PRE1/restore" '{"confirm":"TIKLASH"}')
RJ=$(jget "$(jbody "$R")" job id)
RST=no_job; [[ -n "$RJ" ]] && RST=$(job_wait "$RJ" 280)
check "$( [[ "$RST" == ok ]]; echo $?)" "9: pre_import tiklash -> ok" "$RST / $(echo "$R" | tr '\n' ' ')"
login "$ADMIN_PASSWORD" >/dev/null || true
AFTER9=$(counts)
check "$( [[ "$(sql "select count(*) from extensions")" == 0 && "$(sql "select count(*) from trunks")" == 0 \
  && "$(sql "select count(*) from ivrs")" == 0 ]]; echo $?)" "9: import qilingan obyektlar yo'q" "$AFTER9"

# ================================================================== 8
echo "=== 8. atomarlik (INNOVA_TEST_FAIL_AT=routes) ==="
api_env INNOVA_TEST_FAIL_AT=routes
login "$ADMIN_PASSWORD" >/dev/null || true
BEFORE8=$(counts); SN8=$(sounds_n); REV8=$(sql "select count(*) from config_revisions")
JOB3=$(upload_analyze "$BUNDLE")
R=$(api POST "$M/jobs/$JOB3/apply" '{"confirm":"KOCHIRISH","options":{"rotate_weak_secrets":false}}')
ST=$(mjob_wait "$JOB3" "ok failed" 280)
check "$( [[ "$ST" == failed ]]; echo $?)" "8: apply o'rtasida xato -> failed" "$ST / $(jget "$(mjob "$JOB3")" item error)"
check "$( [[ "$(counts)" == "$BEFORE8" ]]; echo $?)" "8: DB o'zgarmagan" "$BEFORE8 -> $(counts)"
check "$( [[ "$(sounds_n)" == "$SN8" ]]; echo $?)" "8: audio fayllar tozalangan" "$SN8 -> $(sounds_n)"
check "$( [[ "$(sql "select count(*) from config_revisions")" == "$REV8" ]]; echo $?)" "8: yangi reviziya yo'q"
api DELETE "$M/jobs/$JOB3" >/dev/null
api_env INNOVA_TEST_FAIL_AT=
login "$ADMIN_PASSWORD" >/dev/null || true

# ================================================================== 7
echo "=== 7. to'qnashuv (qo'lda yaratilgan 101) ==="
R=$(api POST /extensions '{"number":"101","name":"Qolda 101"}')
MAN101=$(jget "$(jbody "$R")" item id)
check "$( [[ -n "$MAN101" ]]; echo $?)" "7: qo'lda ext 101 yaratildi" "$R"
JOB4=$(upload_analyze "$BUNDLE")
PLAN4=$(plan_all "$JOB4")
check "$( [[ "$(plan_item "$PLAN4" extension 101 action)" == conflict && "$(plan_item "$PLAN4" extension 101 reason)" == number_taken ]]; echo $?)" \
  "7: 101 -> conflict number_taken" "$(plan_item "$PLAN4" extension 101 action) / $(plan_item "$PLAN4" extension 101 reason)"
REF101=$(plan_item "$PLAN4" extension 101 source_ref)
if [[ "$(plan_item "$PLAN4" extension 101 replaceable)" == "false" ]]; then
  R=$(api PATCH "$M/jobs/$JOB4/plan" "{\"items\":[{\"kind\":\"extension\",\"source_ref\":\"$REF101\",\"action\":\"replace\"}]}")
  check "$( err_is "$R" 422 action_not_allowed; echo $?)" "7: replace (replaceable=false) -> 422" "$R"
else
  fail "7: qo'lda yaratilgan 101 replaceable=true bo'lmasligi kerak"
fi
R=$(api POST "$M/jobs/$JOB4/apply" '{"confirm":"KOCHIRISH","options":{"rotate_weak_secrets":false}}')
ST=$(mjob_wait "$JOB4" "ok failed" 280)
check "$( [[ "$ST" == ok ]]; echo $?)" "7: apply -> ok" "$ST / $(jget "$(mjob "$JOB4")" item error)"
check "$( [[ "$(sql "select count(*) from extensions")" == 6 && "$(sql "select name from extensions where number='101'")" == "Qolda 101" ]]; echo $?)" \
  "7: 101 o'zgarmagan, qolgan 5 ichki import qilindi" "$(sql "select count(*) from extensions")"
OPT1=$(sql "select target_id from ivr_options where digit='1'")
check "$( [[ "$OPT1" == "$(ext_tgt 101)" ]]; echo $?)" "7: IVR 1 -> mavjud (qo'lda) 101 ga ulandi"
check "$( [[ "$(sql "select count(*) from ring_group_members m join extensions e on e.id=m.extension_id where e.id='$MAN101'")" == 1 ]]; echo $?)" \
  "7: RG 600 a'zosi -> mavjud 101"
api DELETE "$M/jobs/$JOB4" >/dev/null
api DELETE "$M/jobs/$JOB2" >/dev/null

echo
echo "=== NATIJA: PASS=$PASS FAIL=$FAIL ==="
[[ "$FAIL" == "0" ]]
