# shellcheck shell=bash
# M2c §2 (S33) — ssenariy 2 (SIP brute-force -> avtomatik ban), 3 (ishonchli
# tarmoq -> hech qachon bloklanmaydi/sanalmaydi), 4 (qo'lda ban/blokdan
# chiqarish, 409'lar, muddat tugashi). `scripts/m2c-proof.sh` DAVOM ETTIRADI —
# umumiy o'zgaruvchi/funksiyalar (shu fayl ULARGA tayanadi, qayta e'lon
# QILMAYDI): API_BASE, NET, SIPP_IMAGE, SIPP_DIR, TG_CONT/TG_LOG, CONTAINERS
# massivi, api/jget/jbody/jcode/check/pass/fail/wait_until (m2a_common.sh),
# tg_is_decoded/tg_count_decoded (m2c_common.sh).
#
# IKKI YANGI maxsus konteyner/IP — ATAYLAB `EXT_IP`/`TRUNK_IP`/`TG_IP`dan
# ALOHIDA (5/6-ssenariy toll-fraud SIP trafigiga ta'sir qilmasligi uchun):
SG_ATTACK_IP="172.21.0.203"   # 2: brute-force -> avtoban; 4: qo'lda ban/unban/409/muddat
SG_TRUST_IP="172.21.0.204"    # 3: ishonchli tarmoq istisnosi; 4: 409 trusted_ip

CONTAINERS+=(m2c-proof-sgattack m2c-proof-sgtrust)
docker run -d --name m2c-proof-sgattack --network "$NET" --ip "$SG_ATTACK_IP" "$SIPP_IMAGE" sleep infinity >/dev/null
docker run -d --name m2c-proof-sgtrust  --network "$NET" --ip "$SG_TRUST_IP"  "$SIPP_IMAGE" sleep infinity >/dev/null
docker cp "$SIPP_DIR/register_only.py" m2c-proof-sgattack:/tmp/register_only.py
docker cp "$SIPP_DIR/register_only.py" m2c-proof-sgtrust:/tmp/register_only.py

SG_LPORT=5500
bad_register() { # container username -> stdout (register_only.py chiqishi, parol ATAYLAB noto'g'ri)
  SG_LPORT=$((SG_LPORT + 1))
  docker exec "$1" python3 /tmp/register_only.py asterisk 5060 "$SG_LPORT" "$2" "wrong-$2-pass" 3600 2>&1
}
sg_bans_json() { jbody "$(api GET /security/bans)"; }
sg_is_banned() { # ip -> 0 (faol ban bor) / 1 (yo'q)
  sg_bans_json | python3 -c "
import json,sys
d=json.load(sys.stdin)
sys.exit(0 if any(i['ip']=='$1' for i in d['items']) else 1)"
}
sg_not_banned() { ! sg_is_banned "$1"; }
sg_ban_id_for() { # ip -> stdout: faol ban id (yoki bo'sh)
  sg_bans_json | python3 -c "
import json,sys
d=json.load(sys.stdin)
m=[i['id'] for i in d['items'] if i['ip']=='$1']
print(m[0] if m else '')"
}

echo "--- ssenariy 2: SIP brute-force -> avtomatik ban (<=15s), 403, Telegram, stats ---"
for i in 1 2 3 4 5; do
  R=$(bad_register m2c-proof-sgattack "t1-sgatk-$i")
  echo "$R" | grep -q "401" || echo "2: kutilmagan REGISTER javobi (urinish $i): $R"
done

wait_until 15 sg_is_banned "$SG_ATTACK_IP"
check "$(sg_is_banned "$SG_ATTACK_IP"; echo $?)" \
  "2: 5 ta noto'g'ri parolli REGISTER -> $SG_ATTACK_IP <=15s ichida avtomatik bloklandi" "$(sg_bans_json)"
SG_BAN_ID=$(sg_ban_id_for "$SG_ATTACK_IP")
check "$( [[ -n "$SG_BAN_ID" ]]; echo $?)" "2: faol ban yozuvi ID olindi" "$SG_BAN_ID"

R_AFTER_BAN=$(bad_register m2c-proof-sgattack "t1-sgatk-afterban")
check "$(echo "$R_AFTER_BAN" | grep -q "403"; echo $?)" \
  "2: bloklangandan keyin REGISTER -> 403 Forbidden (PJSIP ACL darhol)" "$R_AFTER_BAN"

wait_until 10 tg_is_decoded "$SG_ATTACK_IP bloklandi" 1
check "$(tg_is_decoded "$SG_ATTACK_IP bloklandi" 1; echo $?)" \
  "2: Telegram'ga ip_banned ogohlantirishi keldi ($SG_ATTACK_IP)" "$(tg_count_decoded "$SG_ATTACK_IP bloklandi")"

SG_STATS_J=$(api "GET" "/security/stats?hours=1")
check "$(echo "$(jbody "$SG_STATS_J")" | python3 -c "
import json,sys
d=json.load(sys.stdin)
ip=[t for t in d['top_ips'] if t['ip']=='$SG_ATTACK_IP']
sys.exit(0 if ip and ip[0]['failures']>=5 and ip[0]['banned'] else 1)"; echo $?)" \
  "2: GET /security/stats -> $SG_ATTACK_IP failures>=5, banned=true" "$(jbody "$SG_STATS_J")"

echo "--- ssenariy 3: ishonchli tarmoq -> hech qachon avtomatik bloklanmaydi ---"
SG_U=$(jget "$(jbody "$(api GET /security/settings)")" updated_at)
SG_TRUST_PATCH_J=$(api PATCH /security/settings "{\"sip_guard\":{\"trusted_nets\":[\"$SG_TRUST_IP/32\"]},\"updated_at\":\"$SG_U\"}")
check "$( [[ "$(jget "$(jbody "$SG_TRUST_PATCH_J")" item sip_guard trusted_nets 0)" == "$SG_TRUST_IP/32" ]]; echo $?)" \
  "3: PATCH sip_guard.trusted_nets=[$SG_TRUST_IP/32]" "$SG_TRUST_PATCH_J"

for i in 1 2 3 4 5 6; do
  R=$(bad_register m2c-proof-sgtrust "t1-sgtrust-$i")
  echo "$R" | grep -q "401" || echo "3: kutilmagan REGISTER javobi (urinish $i): $R"
done
sleep 3  # fon vazifaning kamida bir aylanishi o'tishi uchun (sig_guard interval qisqa)
check "$(sg_not_banned "$SG_TRUST_IP"; echo $?)" \
  "3: ishonchli $SG_TRUST_IP 6 ta noto'g'ri urinishdan keyin HAM bloklanmadi" "$(sg_bans_json)"
R_TRUST_STILL=$(bad_register m2c-proof-sgtrust "t1-sgtrust-still")
check "$(echo "$R_TRUST_STILL" | grep -q "401"; echo $?)" \
  "3: ishonchli $SG_TRUST_IP hali ham 401 oladi (403 EMAS)" "$R_TRUST_STILL"

echo "--- ssenariy 4: qo'lda ban/blokdan chiqarish, 409'lar, muddat tugashi ---"
SG_DEL_J=$(api DELETE "/security/bans/$SG_BAN_ID")
check "$( [[ "$(jcode "$SG_DEL_J")" == "200" ]]; echo $?)" "4: DELETE /security/bans/$SG_BAN_ID -> 200" "$SG_DEL_J"
R_AFTER_UNBAN=$(bad_register m2c-proof-sgattack "t1-sgatk-unban")
check "$(echo "$R_AFTER_UNBAN" | grep -q "401"; echo $?)" \
  "4: blokdan chiqarilgandan keyin REGISTER -> 401 (403 EMAS)" "$R_AFTER_UNBAN"
EV_UNBAN_J=$(api "GET" "/security/events?kind=ip_unbanned&limit=20")
check "$(echo "$(jbody "$EV_UNBAN_J")" | python3 -c "
import json,sys
d=json.load(sys.stdin)
sys.exit(0 if any(i['ip']=='$SG_ATTACK_IP' for i in d['items']) else 1)"; echo $?)" \
  "4: GET /security/events kind=ip_unbanned -> $SG_ATTACK_IP bor" "$(jbody "$EV_UNBAN_J")"

SG_TRUST_BAN_J=$(api POST /security/bans "{\"ip\":\"$SG_TRUST_IP\"}")
check "$( [[ "$(jcode "$SG_TRUST_BAN_J")" == "409" && "$(jget "$(jbody "$SG_TRUST_BAN_J")" error code)" == "trusted_ip" ]]; echo $?)" \
  "4: POST /security/bans ip=$SG_TRUST_IP (ishonchli) -> 409 trusted_ip" "$SG_TRUST_BAN_J"

SG_MANUAL_J=$(api POST /security/bans "{\"ip\":\"$SG_ATTACK_IP\",\"ban_s\":10,\"note\":\"m2c-proof manual\"}")
check "$( [[ "$(jcode "$SG_MANUAL_J")" == "201" && "$(jget "$(jbody "$SG_MANUAL_J")" apply status)" == "applied" ]]; echo $?)" \
  "4: POST /security/bans ip=$SG_ATTACK_IP ban_s=10 -> 201 apply.status=applied" "$SG_MANUAL_J"

R_AFTER_MANUAL=$(bad_register m2c-proof-sgattack "t1-sgatk-manual")
check "$(echo "$R_AFTER_MANUAL" | grep -q "403"; echo $?)" \
  "4: qo'lda bloklangandan keyin REGISTER -> 403" "$R_AFTER_MANUAL"

SG_DUP_J=$(api POST /security/bans "{\"ip\":\"$SG_ATTACK_IP\"}")
check "$( [[ "$(jcode "$SG_DUP_J")" == "409" && "$(jget "$(jbody "$SG_DUP_J")" error code)" == "already_banned" ]]; echo $?)" \
  "4: takror POST /security/bans ip=$SG_ATTACK_IP (faol) -> 409 already_banned" "$SG_DUP_J"

wait_until 25 sg_not_banned "$SG_ATTACK_IP"
check "$(sg_not_banned "$SG_ATTACK_IP"; echo $?)" \
  "4: qo'lda ban (ban_s=10) <=25s ichida muddati tugadi" "$(sg_bans_json)"
R_AFTER_EXPIRY=$(bad_register m2c-proof-sgattack "t1-sgatk-expired")
check "$(echo "$R_AFTER_EXPIRY" | grep -q "401"; echo $?)" \
  "4: muddati tugagandan keyin REGISTER -> 401 (403 EMAS)" "$R_AFTER_EXPIRY"
EV_EXPIRED_J=$(api "GET" "/security/events?kind=ban_expired&limit=20")
check "$(echo "$(jbody "$EV_EXPIRED_J")" | python3 -c "
import json,sys
d=json.load(sys.stdin)
sys.exit(0 if any(i['ip']=='$SG_ATTACK_IP' for i in d['items']) else 1)"; echo $?)" \
  "4: GET /security/events kind=ban_expired -> $SG_ATTACK_IP bor" "$(jbody "$EV_EXPIRED_J")"
