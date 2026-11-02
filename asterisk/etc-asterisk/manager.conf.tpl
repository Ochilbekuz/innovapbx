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
permit = 172.16.0.0/12
permit = 192.168.0.0/16
; write `user` — M1c: VoicemailMove/VoicemailRemove (xabar «eshitildi»/o'chirish).
read = system,call,dialplan,command,reporting
write = system,call,dialplan,command,reporting,originate,user
