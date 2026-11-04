; Innova PBX — AMI. Faqat ICHKI docker tarmog'ida (hostga publish qilinmaydi).
; Parol ENV'dan (AMI_PASSWORD) — entrypoint.sh envsubst qiladi.
[general]
enabled = yes
port = 5038
bindaddr = 0.0.0.0
displayconnects = no
; `channelvars` ATAYLAB yo'q: yoqilsa Asterisk har Set() da kanal snapshot'ini e'lon qiladi va CDR dst/dcontext
; Gosub ichidagi `s` bo'lib qoladi (qora ro'yxat CDR'i). M3b hodisalari DID/navbatni AMI `VarSet` dan oladi.

[${AMI_USERNAME}]
secret = ${AMI_PASSWORD}
deny = 0.0.0.0/0.0.0.0
; M12 C L8: ILGARI butun 172.16.0.0/12 + 192.168.0.0/16 (deyarli har qanday LAN
; manzili) AMI'ga parol topishga urinishi mumkin edi. Faqat `api` chiqadigan
; haqiqiy `innova-net` subnet'i (AMI_PERMIT_CIDR, docker-compose'da L7 bilan
; pin qilingan) + lokal debug uchun loopback.
permit = 127.0.0.1/32
permit = ${AMI_PERMIT_CIDR}
; `read` — faqat API haqiqatda tinglaydigan hodisa sinflari (`call_events.py`
; AMI ulanishi `Events: call,dialplan` bilan obuna bo'ladi; amal (write)
; ulanishi `events=off`, hodisa olmaydi).
read = call,dialplan
; `write` — har bir sinf API haqiqatda chaqiradigan AMI amali uchun (jonli
; tekshirilgan, `asterisk -rx "manager show command <Action>"`):
;   command   -> Command (module/dialplan/voicemail/moh reload va h.k., `app/services/*.py`)
;   originate -> Originate (`callback_dialer.py`/`campaign_dialer.py`/`api/public.py`/`api/v1/live.py`)
;   system    -> PJSIPNotify (`devices.py`), Filter (`ami.py` login)
;   reporting -> ConfbridgeList (`conference.py`); PJSIPQualify/CoreShowChannels ham
;                `system,reporting` qabul qiladi (yuqoridagi `system` bilan allaqachon qoplangan)
;   call      -> ParkedCalls (`parking.py`)
;   user      -> VoicemailMove/VoicemailRemove (`voicemail.py`, M1c)
;   agent     -> QueuePause (`queue_agents.py`) — ILGARI YO'Q EDI (funksional kamchilik,
;                jim yutilardi: `nudge_pause_state()` barcha xatolarni bosardi; endi tuzatildi.
; `dialplan` ATAYLAB OLIB TASHLANDI: write uchun hech bir amal talab qilmaydi
; (`dialplan reload`/`show` — `Command` orqali, faqat `command` sinfi kerak).
write = command,originate,system,reporting,call,user,agent
