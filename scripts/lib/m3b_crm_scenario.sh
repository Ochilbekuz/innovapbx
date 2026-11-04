# shellcheck shell=bash
# M3b §7.5–7.6 — CRM isboti (Bitrix24 + amoCRM + 1C). `scripts/m3b-proof.sh` oxirida `source` qilinadi.
# Talab: m3b-proof.sh muhiti (api, sql, check, trunk_call, call_bg, mode, invites, EXT_ID, IP, NET, PY_IMAGE, SIPP_DIR,
# DID_*, OUT_NUM, HANGUP_T, PUBLIC_BASE, target_of, CONTAINERS). Soxta CRM: `tests/sipp/fake_crm.py` (bitta konteyner,
# Bitrix `/rest/...` va amoCRM `/api/v4/...`), har so'rovni yozadi va N marta 503/429 qaytara oladi.

CRM_IP="172.28.0.227"; CRM_PORT=9001
CRM_BASE="http://$CRM_IP:$CRM_PORT"
BX_HOOK_URL="$CRM_BASE/rest/1/abc123/"
BX_APP_TOKEN="apptok-M3b"; AMO_TOKEN="amotok-M3b"
DID_CQ="713000105"
CONTAINERS+=(m3b-proof-crm)

crm() { curl -s -m 5 "$CRM_BASE/$1" "${@:2}"; }
crm_cfg() { crm _config -X POST -H 'Content-Type: application/json' -d "$1" >/dev/null; }
crm_q() { # python_ifoda [arg...] -> soxta CRM yozuvlari bo'yicha natija
  # Ifodada: rs — hammasi; a — argumentlar; meth(r) — Bitrix metodi (qisqa); form(r);
  # bx(L[, cid]) — shu qo'ng'iroq Bitrix so'rovlari; seq(L[, cid]) — "metod:USER_ID:status ..."; amo(path, L).
  crm _requests | python3 -c '
import json, sys
rs, a = json.load(sys.stdin), sys.argv[2:]
def form(r): return r.get("form") or {}
def meth(r): return r["path"].rsplit("/", 1)[-1].removesuffix(".json").replace("telephony.externalcall.", "")
def bx(L, cid=None):
    ids = {L, "ext." + L} | ({cid} if cid else set())
    return [r for r in rs if r["path"].startswith("/rest/") and
            (form(r).get("EXTERNAL_CALL_ID") in ids or form(r).get("CALL_ID") in ids)]
def seq(L, cid=None): return " ".join("%s:%s:%s" % (meth(r), form(r).get("USER_ID", ""), r["status"]) for r in bx(L, cid))
def amo(path, L): return [r for r in rs if r["path"] == path and L in json.dumps(r.get("json"))]
print(eval(sys.argv[1]))' "$@"
}
bx_done() { [[ "$(crm_q 'any(meth(r) == "finish" and r["status"] == 200 for r in bx(a[0], *a[1:]))' "$@")" == "True" ]]; }
amo_done() { [[ "$(crm_q 'any(r["status"] == 200 for r in amo(a[0], a[1]))' "$1" "$2")" == "True" ]]; }
jpy() { python3 -c 'import json, sys; d = json.load(sys.stdin); print(eval(sys.argv[1]))' "$1" <<<"$2"; }
next_lid() { # sql eski_linkedid -> yangi linkedid (CDR kechikib yozilsa ham eskisini qaytarmaydi)
  local out=""
  for _ in $(seq 1 30); do
    out=$(sql "$1"); [[ -n "$out" && "$out" != "$2" ]] && break; sleep 0.5
  done
  echo "$out"
}
lid_to() { echo "select linkedid from cdr where dstchannel ~ '^PJSIP/($1)-' order by calldate desc limit 1"; }
crm_dlv() { # provayder linkedid -> "holatlar|max(attempts)|soni"
  sql "select coalesce(string_agg(distinct d.status, ','), '')||'|'||coalesce(max(d.attempts), 0)||'|'||count(*)
         from integration_deliveries d join integration_subscriptions s on s.id = d.subscription_id
        where s.kind = '$1' and d.call_id = '$2'"
}
crm_put() { # provayder json_qolgan_qism -> PUT javobi (updated_at joriy)
  api PUT "/integrations/crm/$1" "{$2,\"updated_at\":\"$(updated_at_of "/integrations/crm/$1")\"}"
}
ext_updated_at() {
  jbody "$(api GET "/extensions?q=$1")" | python3 -c "
import json,sys
print(next((i['updated_at'] for i in json.load(sys.stdin)['items'] if i['number']==sys.argv[1]), ''))" "$1"
}

# ---------------------------------------------------------------- soxta CRM
docker run -d --name m3b-proof-crm --network "$NET" --ip "$CRM_IP" "$PY_IMAGE" sleep infinity >/dev/null
docker cp "$SIPP_DIR/fake_crm.py" m3b-proof-crm:/tmp/fake_crm.py
docker exec -d m3b-proof-crm python3 /tmp/fake_crm.py 0.0.0.0 "$CRM_PORT"
wait_until 10 curl -sf -o /dev/null "$CRM_BASE/_requests" && pass "soxta Bitrix24/amoCRM ($CRM_IP:$CRM_PORT) ishlayapti" \
  || fail "soxta CRM ishga tushmadi"
for n in 101 102 103 104; do mode "$n" answer; done; mode trunk answer

# ---------------------------------------------------------------- 5. Bitrix24 sozlamalari
echo "=== 5. Bitrix24 ==="
G0=$(api GET /integrations/crm/bitrix24)
HOOK=$(jget "$(jbody "$G0")" config hook_token)
check "$( [[ "$(jcode "$G0")" == "200" && "$(jget "$(jbody "$G0")" enabled)" == "False" && ${#HOOK} -ge 16 \
  && "$(jget "$(jbody "$G0")" status state)" == "disabled" ]]; echo $?)" "5: GET crm/bitrix24 -> o'chiq, hook_token bor" "$G0"
C_NC=$(api POST /integrations/crm/bitrix24/test)
check "$(err_is "$C_NC" 422 not_configured; echo $?)" "5: sozlanmagan /test -> 422 not_configured" "$C_NC"
P_SSRF=$(crm_put bitrix24 '"enabled":true,"webhook_url":"http://127.0.0.1:9001/rest/1/abc123/"')
P_SHAPE=$(crm_put bitrix24 "\"enabled\":true,\"webhook_url\":\"$CRM_BASE/boshqa\"")
check "$(err_is "$P_SSRF" 422 url_forbidden && err_is "$P_SHAPE" 422 bad_webhook_url; echo $?)" \
  "5: webhook_url 127.0.0.1 -> 422 url_forbidden, noto'g'ri shakl -> 422 bad_webhook_url" "$P_SSRF / $P_SHAPE"
P1=$(crm_put bitrix24 "\"enabled\":true,\"webhook_url\":\"$BX_HOOK_URL\",\"application_token\":\"$BX_APP_TOKEN\",\"popup_max_delay_s\":30")
UA1=$(jget "$(jbody "$P1")" updated_at)
check "$( [[ "$(jcode "$P1")" == "200" && "$(jget "$(jbody "$P1")" config has_webhook_url)" == "True" \
  && "$(jget "$(jbody "$P1")" config application_token_set)" == "True" ]] && ! grep -Eq "abc123|$BX_APP_TOKEN" <<<"$P1"; echo $?)" \
  "5: PUT crm/bitrix24 (LAN, yoqildi) -> 200, sirlar javobda yo'q" "$P1"
sleep 1.1  # optimistik qulf soniya aniqligida (app/core/optimistic.py) — P1 va P2 turli soniyada bo'lsin
P2=$(crm_put bitrix24 '"enabled":true,"popup_max_delay_s":60')
G1=$(jbody "$(api GET /integrations/crm/bitrix24)")
check "$( [[ "$(jcode "$P2")" == "200" && "$(jget "$G1" config has_webhook_url)" == "True" && "$(jget "$G1" config popup_max_delay_s)" == "60" ]] \
  && ! grep -Eq "abc123|$BX_APP_TOKEN" <<<"$G1"; echo $?)" "5: sirsiz PUT -> eski sirlar saqlanadi, GET'da ko'rinmaydi" "$P2 / $G1"
P_STALE=$(api PUT /integrations/crm/bitrix24 "{\"enabled\":true,\"popup_max_delay_s\":45,\"updated_at\":\"$UA1\"}")
check "$(err_is "$P_STALE" 409 stale; echo $?)" "5: eskirgan updated_at -> 409 stale" "$P_STALE"
AUD_BX=$(sql "select string_agg(diff::text, ' ') from audit_log where entity='crm' and entity_id='bitrix24' and action='update'")
check "$( [[ "$AUD_BX" == *'***'* && "$AUD_BX" != *abc123* && "$AUD_BX" != *"$BX_APP_TOKEN"* ]]; echo $?)" \
  "5: audit crm.update -> sirlar '***'" "$AUD_BX"
T_BX=$(api POST /integrations/crm/bitrix24/test)
MAP_BX=$(jbody "$(api GET /integrations/crm/bitrix24)")
AUTO=$(jpy '" ".join(sorted("%s:%s:%s" % (e["extension"], e["crm_user_id"], e["source"]) for e in d["user_map"] if e["crm_user_id"]))' "$MAP_BX")
check "$( [[ "$(jget "$(jbody "$T_BX")" ok)" == "True" && "$(jget "$(jbody "$T_BX")" users_loaded)" == "3" \
  && "$AUTO" == "101:7:auto 103:9:auto 104:11:auto" ]]; echo $?)" \
  "5: /test -> ok, 3 foydalanuvchi; UF_PHONE_INNER bo'yicha avto-xarita 101->7, 103->9, 104->11" "$T_BX / $AUTO"
check "$( [[ "$(jpy '",".join(d["status"]["unmapped_extensions"])' "$MAP_BX")" == "102" ]]; echo $?)" \
  "5: status.unmapped_extensions = [102]" "$(jget "$MAP_BX" status)"
UM1=$(api PUT /integrations/crm/bitrix24/user-map '{"entries":[{"extension":"102","crm_user_id":"11"}]}')
UM1_S=$(jpy 'next((e["crm_user_id"] + ":" + e["source"] for e in d["items"] if e["extension"] == "102"), "")' "$(jbody "$UM1")")
UM2=$(api PUT /integrations/crm/bitrix24/user-map '{"entries":[{"extension":"102","crm_user_id":null}]}')
UM2_S=$(jpy 'next((str(e["crm_user_id"]) for e in d["items"] if e["extension"] == "102"), "")' "$(jbody "$UM2")")
UM3=$(api PUT /integrations/crm/bitrix24/user-map '{"entries":[{"extension":"999","crm_user_id":"7"}]}')
check "$( [[ "$UM1_S" == "11:manual" && "$UM2_S" == "None" ]] && err_is "$UM3" 422 unknown_extension; echo $?)" \
  "5: user-map: 102->11 manual, null -> o'chdi, 999 -> 422 unknown_extension" "$UM1_S / $UM2_S / $UM3"

O_LIST=$(api GET /integrations/1c/samples)
O_NAME=$(jget "$(jbody "$O_LIST")" items 0 name)
O_DL=$(http_code "${AUTH[@]}" "$API_BASE/integrations/1c/samples/$O_NAME")
O_TR1=$(http_code "${AUTH[@]}" "$API_BASE/integrations/1c/samples/..%2F..%2Fmain.py")
O_TR2=$(http_code "${AUTH[@]}" "$API_BASE/integrations/1c/samples/manifest.json")
check "$( [[ "$(jcode "$O_LIST")" == "200" && -n "$O_NAME" && "$O_DL" == "200" && "$O_TR1" == "404" && "$O_TR2" == "404" ]]; echo $?)" \
  "5: 1C namunalar: ro'yxat, yuklab olish 200, yo'l aylanib o'tish/manifest -> 404" "$O_NAME dl=$O_DL tr=$O_TR1 mf=$O_TR2"

# ---------------------------------------------------------------- 5. navbat (101, 103) -> register/show/hide/finish
UA103=$(ext_updated_at 103)
R103=$(api PATCH "/extensions/${EXT_ID[103]}" "{\"recording\":\"always\",\"updated_at\":\"$UA103\"}")
CQ_J=$(api POST /queues "{\"name\":\"M3bCrmQ\",\"strategy\":\"linear\",\"agent_ring_seconds\":5,\"retry_seconds\":1,\"max_wait_seconds\":14,\"members\":[{\"extension_id\":\"${EXT_ID[101]}\"},{\"extension_id\":\"${EXT_ID[103]}\"}],\"timeout_target_id\":\"$HANGUP_T\"}")
CQ_R=$(api POST /inbound-routes "{\"name\":\"M3bDidCrm\",\"did\":\"$DID_CQ\",\"target_id\":\"$(target_of queue M3bCrmQ)\",\"enabled\":true}")
check "$( [[ "$(jcode "$R103")" == "200" && "$(jcode "$CQ_J")" == "201" && "$(jcode "$CQ_R")" == "201" ]]; echo $?)" \
  "5: 103 recording=always, navbat M3bCrmQ (linear: 101, 103) + DID $DID_CQ" "$(jcode "$R103") $CQ_J / $CQ_R"
crm _reset -X POST >/dev/null
PREV=$(sql "$(lid_to 103)")
mode 101 ring; mode 103 answer
trunk_call "$DID_CQ" 14 crmq  # navbat darhol Answer() qiladi: 101 (5 s) + retry + 103 javob + suhbat
mode 101 answer
LQ2=$(next_lid "$(lid_to 103)" "$PREV")
wait_until 40 bx_done "$LQ2"
SEQ_Q=$(crm_q 'seq(a[0])' "$LQ2")
check "$( [[ "$SEQ_Q" == "register:7:200 show:9:200 hide:7:200 finish:9:200" ]]; echo $?)" \
  "5: navbat: register(USER 7, 101) -> show(9, 103) -> hide(7) -> finish(USER 9)" "L=$LQ2 $SEQ_Q"
FIN_Q=$(crm_q 'next((form(r)["STATUS_CODE"] + "|" + form(r)["DURATION"] + "|" + form(r).get("RECORD_URL", "") for r in bx(a[0]) if meth(r) == "finish"), "")' "$LQ2")
REG_Q=$(crm_q 'next((form(r)["TYPE"] + "|" + form(r).get("LINE_NUMBER", "") + "|" + form(r)["SHOW"] for r in bx(a[0]) if meth(r) == "register"), "")' "$LQ2")
wait_until 15 wh_has /a "$LQ2" call.ended
WH_Q=$(wh_ended_field /a "$LQ2" "str(c['billsec']) + '|' + ((c['recordings'] or [{}])[0].get('url') or '')")
CDR_BS=$(sql "select max(billsec) from cdr where linkedid='$LQ2' and disposition='ANSWERED' and dstchannel like 'PJSIP/103-%'")
DUR_Q=$(cut -d'|' -f2 <<<"$FIN_Q")
check "$( [[ "$(cut -d'|' -f1 <<<"$FIN_Q")" == "200" && "$DUR_Q" == "${WH_Q%%|*}" && $(( DUR_Q - CDR_BS )) -le 1 \
  && $(( CDR_BS - DUR_Q )) -le 1 && "$(cut -d'|' -f3- <<<"$FIN_Q")" == "${WH_Q#*|}" && "${WH_Q#*|}" == http* ]]; echo $?)" \
  "5: finish: STATUS_CODE 200, DURATION = billsec (CDR $CDR_BS), RECORD_URL = ended yozuv havolasi" "fin=$FIN_Q wh=$WH_Q"
check "$( [[ "$REG_Q" == "2|$DID_CQ|1" ]]; echo $?)" "5: register: TYPE 2 (kiruvchi), LINE_NUMBER = DID, SHOW 1" "$REG_Q"

PREV=$(sql "$(lid_to 101\|103)")
mode 101 ring; mode 103 ring
trunk_call "$DID_CQ" 25 crmq_miss
mode 101 answer; mode 103 answer
LM=$(next_lid "$(lid_to 101\|103)" "$PREV")
wait_until 40 bx_done "$LM"
FIN_M=$(crm_q 'next((form(r)["STATUS_CODE"] + "|" + form(r)["DURATION"] for r in bx(a[0]) if meth(r) == "finish"), "")' "$LM")
check "$( [[ "$FIN_M" == "304|0" ]]; echo $?)" "5: javobsiz navbat qo'ng'irog'i -> finish STATUS_CODE 304" "L=$LM fin=$FIN_M $(crm_q 'seq(a[0])' "$LM")"

# ---------------------------------------------------------------- 5. ONEXTERNALCALLSTART (click-to-call)
I101=$(invites 101); ITR=$(invites trunk)
HOOK_URL="$PUBLIC_BASE/crm/bitrix24/$HOOK/call"
hook_post() { # token -> body + "\n" + http_code
  curl -s -w '\n%{http_code}' -X POST "$HOOK_URL" --data-urlencode event=ONEXTERNALCALLSTART \
    --data-urlencode 'data[USER_ID]=7' --data-urlencode "data[PHONE_NUMBER]=$OUT_NUM" \
    --data-urlencode 'data[CALL_ID]=externalCall.click1' --data-urlencode "auth[application_token]=$1"
}
H_BAD=$(hook_post wrong-token)
H_404=$(http_code -X POST "$PUBLIC_BASE/crm/bitrix24/notatoken/call" -d "event=ONEXTERNALCALLSTART&auth[application_token]=$BX_APP_TOKEN")
check "$(err_is "$H_BAD" 403 forbidden && [[ "$H_404" == "404" && "$(invites 101)" == "$I101" ]]; echo $?)" \
  "5: ONEXTERNALCALLSTART noto'g'ri token -> 403, noma'lum hook -> 404 (qo'ng'iroq yo'q)" "$H_BAD / $H_404"
H_OK=$(hook_post "$BX_APP_TOKEN")
HREQ=$(jget "$(jbody "$H_OK")" request_id)
wait_until 15 invites_gt 101 "$I101" && wait_until 15 invites_gt trunk "$ITR"
check "$( [[ "$(jcode "$H_OK")" == "202" && -n "$HREQ" ]] && invites_gt 101 "$I101" \
  && [[ "$(plog trunk | grep '^INVITE ' | tail -1)" == *"ruri=sip:$OUT_NUM@"* ]]; echo $?)" \
  "5: ONEXTERNALCALLSTART (to'g'ri token) -> 202, 101 (USER 7) jiringladi, so'ng trunk $OUT_NUM" "$H_OK"
sleep 2; ast "channel request hangup all" >/dev/null; wait_until 10 no_calls
wait_until 40 bx_done "$HREQ" externalCall.click1
SEQ_H=$(crm_q 'seq(a[0], a[1])' "$HREQ" externalCall.click1)
LINK_H=$(sql "select origin||'|'||external_call_id from crm_call_links where provider='bitrix24' and linkedid='$HREQ'")
check "$( [[ "$SEQ_H" != *register* && "$SEQ_H" == *"finish:7:200"* && "$LINK_H" == "crm|externalCall.click1" ]]; echo $?)" \
  "5: click-to-call: ikkinchi register YO'Q, finish CALL_ID = Bitrix CALL_ID" "$SEQ_H / link=$LINK_H"

# ---------------------------------------------------------------- 6. amoCRM sozlamalari
echo "=== 6. amoCRM ==="
A_NC=$(api POST /integrations/crm/amocrm/test)
A_SSRF=$(crm_put amocrm '"enabled":true,"base_url":"http://169.254.169.254","token":"x"')
check "$(err_is "$A_NC" 422 not_configured && err_is "$A_SSRF" 422 url_forbidden; echo $?)" \
  "6: amoCRM: sozlanmagan /test -> 422, base_url 169.254.169.254 -> 422 url_forbidden" "$A_NC / $A_SSRF"
A_PUT=$(crm_put amocrm "\"enabled\":true,\"base_url\":\"$CRM_BASE\",\"token\":\"$AMO_TOKEN\",\"unsorted_for_unknown\":true")
A_T=$(api POST /integrations/crm/amocrm/test)
A_UM=$(api PUT /integrations/crm/amocrm/user-map '{"entries":[{"extension":"101","crm_user_id":"55"}]}')
A_MAP=$(jpy 'next((e["crm_user_id"] + ":" + e["source"] + ":" + str(e["crm_user_name"]) for e in d["items"] if e["extension"] == "101"), "")' "$(jbody "$A_UM")")
check "$( [[ "$(jcode "$A_PUT")" == "200" && "$(jget "$(jbody "$A_PUT")" config token_set)" == "True" \
  && "$(jget "$(jbody "$A_T")" ok)" == "True" && "$(jget "$(jbody "$A_T")" users_loaded)" == "2" \
  && "$A_MAP" == "55:manual:Amo 101" ]] && ! grep -q "$AMO_TOKEN" <<<"$A_PUT"; echo $?)" \
  "6: PUT crm/amocrm -> 200 (token yo'q), /test ok 2 foydalanuvchi, xarita 101->55" "$A_PUT / $A_T / $A_MAP"

# ---------------------------------------------------------------- chiquvchi: Bitrix TYPE 1 + amoCRM ma'lum kontakt
crm_cfg "{\"known\":[\"$OUT_NUM\"]}"
PREV=$(sql "select linkedid from cdr where channel like 'PJSIP/101-%' and dstchannel like '%trunk%' order by calldate desc limit 1")
call_bg 101 "101" "${SECRET[101]}" "$OUT_NUM" 4 crmo
wait_until 25 call_done 101 crmo; wait_until 10 no_calls
LO2=$(next_lid "select linkedid from cdr where channel like 'PJSIP/101-%' and dstchannel like '%trunk%' order by calldate desc limit 1" "$PREV")
wait_until 40 bx_done "$LO2"
REG_O=$(crm_q 'next((form(r)["TYPE"] + "|" + form(r)["PHONE_NUMBER"] + "|" + form(r)["USER_ID"] for r in bx(a[0]) if meth(r) == "register"), "")' "$LO2")
check "$( [[ "$REG_O" == "1|$OUT_NUM|7" ]]; echo $?)" "5: chiquvchi 101 -> trunk: register TYPE 1, PHONE_NUMBER, USER 7" \
  "L=$LO2 $REG_O / $(crm_q 'seq(a[0])' "$LO2")"
wait_until 40 amo_done /api/v4/calls "$LO2"
wait_until 15 wh_has /a "$LO2" call.ended
WH_O=$(wh_ended_field /a "$LO2" "str(c['billsec']) + '|' + ((c['recordings'] or [{}])[0].get('url') or '')")
AMO_O=$(crm_q '"|".join(str(c.get(k)) for c in [amo("/api/v4/calls", a[0])[-1]["json"][0]] for k in ("uniq", "direction", "phone", "call_status", "duration", "responsible_user_id", "source", "link"))' "$LO2")
check "$( [[ "$AMO_O" == "$LO2|outbound|$OUT_NUM|4|${WH_O%%|*}|55|Innova PBX|${WH_O#*|}" && "${WH_O#*|}" == http* \
  && "$(crm_q 'len(amo("/api/v4/leads/unsorted/sip", a[0]))' "$LO2")" == "0" ]]; echo $?)" \
  "6: ma'lum kontakt -> /api/v4/calls: uniq, outbound, phone, call_status 4, duration=billsec, responsible 55, link" \
  "$AMO_O / wh=$WH_O"
AUTH_O=$(crm_q 'amo("/api/v4/calls", a[0])[-1]["auth"]' "$LO2")
check "$( [[ "$AUTH_O" == "Bearer $AMO_TOKEN" ]]; echo $?)" "6: amoCRM so'rovi Authorization: Bearer <token>" "$AUTH_O"

# ---------------------------------------------------------------- ichki qo'ng'iroq -> CRM'ga 0 so'rov
PREV=$(sql "$(lid_to 101)")
N0=$(crm_q 'len(rs)')
call_bg 104 "104" "${SECRET[104]}" 101 3 crmi
wait_until 20 call_done 104 crmi; wait_until 10 no_calls
LI2=$(next_lid "$(lid_to 101)" "$PREV")
wait_until 20 ended_emitted "$LI2"; sleep 4
check "$( [[ -n "$LI2" && "$LI2" != "$PREV" && "$(crm_q 'sum(a[0] in json.dumps(r) for r in rs)' "$LI2")" == "0" \
  && "$(crm_dlv bitrix24 "$LI2")" == "|0|0" && "$(crm_dlv amocrm "$LI2")" == "|0|0" ]]; echo $?)" \
  "5/6: ichki 104 -> 101 -> Bitrix va amoCRM'ga 0 so'rov, CRM yetkazmasi yo'q" \
  "L=$LI2 bx=$(crm_dlv bitrix24 "$LI2") amo=$(crm_dlv amocrm "$LI2") all=$N0->$(crm_q 'len(rs)')"

# ---------------------------------------------------------------- Bitrix 503 + amoCRM 429 + noma'lum kontakt
crm_cfg '{"known":[],"fail":[{"prefix":"/rest/1/abc123/telephony.externalcall.register","status":503,"n":1},{"prefix":"/api/v4/calls","status":429,"n":1,"retry_after":2}]}'
PREV=$(sql "$(lid_to 101)")
trunk_call "$DID_101" 4 crmf
LF=$(next_lid "$(lid_to 101)" "$PREV")
wait_until 60 bx_done "$LF"
SEQ_F=$(crm_q 'seq(a[0])' "$LF")
DLV_F=$(crm_dlv bitrix24 "$LF")
check "$( [[ "$SEQ_F" == "register:7:503 register:7:200 "* && "$SEQ_F" == *" finish:7:200" \
  && "$(grep -o 'register:7:200' <<<"$SEQ_F" | wc -l)" == "1" && "$DLV_F" == delivered\|* && "$(cut -d'|' -f2 <<<"$DLV_F")" -ge 2 ]]; echo $?)" \
  "5: soxta Bitrix 1 marta 503 -> qayta urinish (attempts >= 2), tartib register -> finish saqlandi" "L=$LF $SEQ_F / $DLV_F"
wait_until 40 amo_done /api/v4/leads/unsorted/sip "$LF"
AMO_F=$(crm_q '",".join(str(r["status"]) for r in amo("/api/v4/calls", a[0])) + "|" + str(next((r["json"][0]["source_uid"] for r in amo("/api/v4/leads/unsorted/sip", a[0]) if r["status"] == 200), ""))' "$LF")
AT_F=$(crm_q 'max([r["t"] for r in amo("/api/v4/calls", a[0])] or [0]) - min([r["t"] for r in amo("/api/v4/calls", a[0])] or [0]) >= 1.5' "$LF")
check "$( [[ "$AMO_F" == "429,200|$LF" && "$AT_F" == "True" ]]; echo $?)" \
  "6: amoCRM 429 (Retry-After 2) -> kechiktirib qayta urinish; noma'lum kontakt -> unsorted/sip (source_uid = linkedid)" \
  "L=$LF $AMO_F delay_ok=$AT_F dlv=$(crm_dlv amocrm "$LF")"

S_BX=$(jbody "$(api GET /integrations/crm/bitrix24)"); S_AMO=$(jbody "$(api GET /integrations/crm/amocrm)")
check "$( [[ "$(jget "$S_BX" status state)" == "ok" && -n "$(jget "$S_BX" status last_ok_at)" \
  && "$(jget "$S_AMO" status state)" == "ok" && -n "$(jget "$S_AMO" status last_ok_at)" ]]; echo $?)" \
  "5/6: status.state = ok, last_ok_at bor (qayta urinishdan so'ng xato tozalandi)" "$(jget "$S_BX" status) / $(jget "$S_AMO" status)"
