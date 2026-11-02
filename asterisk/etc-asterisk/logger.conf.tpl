; Innova PBX — logger.conf (baza andrius/asterisk:22 standartidan: console +
; messages.log saqlanadi). M2c §2 (SIP hujum himoyasi, S33) uchun YANGI
; `security` kanali qo'shilgan — Asterisk `res_security_log` moduli
; ChallengeResponseFailed/InvalidAccountID/InvalidPassword kabi hodisalarni
; shu faylga yozadi, `app/services/sip_guard.py` fon vazifasi tail qiladi.
; Yo'l `astlog` umumiy hajmida (Asterisk rw, API ro — `deploy/docker-compose.yml`).
; `entrypoint.sh` ishga tushishda `envsubst` bilan ${SECURITY_LOG_PATH}ni to'ldiradi.

[general]

[logfiles]
console => notice,warning,error
messages.log => notice,warning,error
${SECURITY_LOG_PATH} => security
