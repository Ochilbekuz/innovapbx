# shellcheck shell=bash
# M2c proof umumiy yordamchilari — ikki mustaqil blok:
#   1) SIP UAS (trunk peer) infratuzilmasi — `m1b-proof.sh`dagi bilan AYNAN BIR
#      XIL qolip (jonli isbotda topilgan race-condition tuzatishlari bilan),
#      shu sabab bu yerga ko'chirilib, qayta ishlatiladi (dryer). Kerak:
#      `qualify_trunk`/`wait_for_aor_avail` doim `innova-m0-asterisk-1`ga tegadi
#      (loyihada yagona Asterisk konteyner — boshqa stack bilan ishlatilmaydi).
#   2) Soxta Telegram (`tests/sipp/fake_telegram.py`) log faylini o'qish —
#      `$TG_CONT`/`$TG_LOG` global o'zgaruvchilarga tayanadi (chaqiruvchi
#      skript ularni `source`dan OLDIN belgilashi SHART). M2c §4 (ogohlantirish)
#      SIP hujum (§2) va trunk monitor (§7) ssenariylarida HAM kerak bo'ladi —
#      shu sabab umumiy fayl, faqat m2c-proof.shga XOS emas.

# ------------------------------------------------------------- SIP UAS (trunk)
# `start_uas` tinglovchini (masalan `uas_log_and_answer.py`) orqa fonda qayta
# ishga tushiradi — avval ESKI jarayon HAQIQATAN chiqib ketganini kutadi
# (qattiq `sleep`ga ishonmaydi, m1b-proof.sh'da topilgan race).
start_uas() { # container script ip max_seconds
  docker exec "$1" pkill -x python3 >/dev/null 2>&1 || true
  local waited=0
  while docker exec "$1" pgrep -x python3 >/dev/null 2>&1; do
    sleep 0.1
    waited=$((waited + 1))
    (( waited > 20 )) && break  # ~2s dan keyin voz kechib davom etamiz
  done
  docker exec -d "$1" sh -c "python3 -u /tmp/$2 $3 5060 $4 > /tmp/out.log 2>&1"
}
uas_log() { docker exec "$1" cat /tmp/out.log 2>/dev/null; }
qualify_trunk() { docker exec innova-m0-asterisk-1 asterisk -rx "pjsip qualify t1-trunk-$1" >/dev/null 2>&1; }
# PASSIV kutish — status "Avail" bo'lguncha, qayta `qualify_trunk` CHAQIRMAYDI
# (bir nechta overlapping probe "NonQual"da mangu osilib qolish xatosiga olib
# kelgani m1b-proof.sh'da jonli tasdiqlangan).
wait_for_aor_avail() { # trunk_id max_seconds
  local tries=$(( ${2:-3} * 10 )) i=0
  while (( i < tries )); do
    docker exec innova-m0-asterisk-1 asterisk -rx "pjsip show aor t1-trunk-$1" 2>/dev/null | grep -q "Avail" && return 0
    sleep 0.1
    i=$((i + 1))
  done
  return 1
}
wait_for_uas_log() { # container pattern max_seconds
  local out="" i=0 tries=$(( ${3:-3} * 10 ))
  while (( i < tries )); do
    out=$(uas_log "$1")
    echo "$out" | grep -q "$2" && { echo "$out"; return 0; }
    sleep 0.1
    i=$((i + 1))
  done
  echo "$out"
}
# Qisqa yordamchi: tinglovchini qayta ishga tushirish + qualify + Avail
# kutish — uchtasi deyarli har doim BIRGA kerak bo'ladi (m2c-proof.sh har bir
# "trunkka yetishi kerak" chaqiruvdan OLDIN, chunki `uas_log_and_answer.py`
# BITTA INVITE'dan keyin o'zi chiqadi).
uas_ready() { # container script ip trunk_id max_seconds
  start_uas "$1" "$2" "$3" 20
  sleep 0.3
  qualify_trunk "$4"
  wait_for_aor_avail "$4" "${5:-3}"
}

# --------------------------------------------------------- soxta Telegram log
# `fake_telegram.py` qatori: `REQ path=... chat_id=... filename=... riff=...
# bytes=... text_b64=<base64(text)>` (M2c §4 — oxirgi maydon, m1c grep'larini
# buzmaydi). `$TG_CONT`/`$TG_LOG` chaqiruvchi tomonidan belgilanadi.
tg_count() { docker exec "$TG_CONT" sh -c "grep -c '$1' '$TG_LOG' 2>/dev/null || true"; }
tg_is() { [[ "$(tg_count "$1")" == "$2" ]]; }
# Berilgan grep naqshiga mos OXIRGI qatorning matnini (text_b64 dekodlangan)
# qaytaradi — ogohlantirish matni ICHIDA kutilgan so'z/raqam borligini
# tekshirish uchun (masalan: `tg_text_of toll_blocked`).
tg_text_of() {
  docker exec "$TG_CONT" sh -c "grep '$1' '$TG_LOG' 2>/dev/null | tail -1" \
    | grep -oE 'text_b64=[^ ]+' | cut -d= -f2 | base64 -d 2>/dev/null
}
# DIQQAT: `fake_telegram.py` qatorida ogohlantirish TURI (`kind`) YOZILMAYDI
# (Telegram'ning o'ziga ham yuborilmaydi — faqat `chat_id`+`text`). Shu sabab
# "toll_blocked"/"concurrent_limit" kabi `kind` so'zlari bilan RAW qatorni
# grep qilib bo'lmaydi — faqat DEKODLANGAN matn (`alerts.py` `_TEXTS`) orqali
# ajratish mumkin (masalan "bloklandi"/raqam). Quyidagi ikkisi shu uchun.
tg_count_decoded() { # naqsh -> DEKODLANGAN matnlar orasida necha marta ko'rinadi
  docker exec "$TG_CONT" sh -c "cat '$TG_LOG' 2>/dev/null" \
    | grep -oE 'text_b64=[^ ]+' | cut -d= -f2 \
    | while IFS= read -r b64; do [[ "$b64" != "-" ]] && base64 -d <<<"$b64" 2>/dev/null; echo; done \
    | grep -c "$1" 2>/dev/null || true
}
tg_is_decoded() { [[ "$(tg_count_decoded "$1")" == "$2" ]]; }
tg_text_of_decoded() { # naqsh -> mos keluvchi OXIRGI DEKODLANGAN matn
  docker exec "$TG_CONT" sh -c "cat '$TG_LOG' 2>/dev/null" \
    | grep -oE 'text_b64=[^ ]+' | cut -d= -f2 \
    | while IFS= read -r b64; do [[ "$b64" != "-" ]] && base64 -d <<<"$b64" 2>/dev/null; echo; done \
    | grep "$1" | tail -1
}
