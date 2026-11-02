# Innova PBX — Asterisk qatlami.
# Baza: andrius/asterisk:22 (lokal, Asterisk 22 LTS). O'zgartirilmagan Asterisk
# kodi (GPL) — faqat konfiguratsiya va kichik entrypoint ustquruma qo'shiladi.
#
# Qaror: ODBC EMAS. Tekshirildi — obrazda res_config_pgsql.so bor va libpq.so.5
# ni to'liq topadi (`ldd` "not found" bermadi), demak ishlaydi. ODBC qatlami
# (unixODBC + psqlodbc) shart emas — bitta kam qatlam, kamroq nosozlik nuqtasi.
FROM andrius/asterisk:22

USER root

COPY etc-asterisk/modules.conf /etc/asterisk/modules.conf
COPY etc-asterisk/sorcery.conf /etc/asterisk/sorcery.conf
COPY etc-asterisk/extconfig.conf /etc/asterisk/extconfig.conf
COPY etc-asterisk/pjsip.conf /etc/asterisk/pjsip.conf
COPY etc-asterisk/rtp.conf /etc/asterisk/rtp.conf
# M3a §1 — HTTP serveri (8088, faqat ichki) WebRTC `/ws` uchun.
COPY etc-asterisk/http.conf /etc/asterisk/http.conf
COPY etc-asterisk/pjsip_transports_innova.default.conf /etc/asterisk/pjsip_transports_innova.default.conf
COPY etc-asterisk/rtp_innova.default.conf /etc/asterisk/rtp_innova.default.conf
COPY etc-asterisk/extensions.conf /etc/asterisk/extensions.conf
COPY etc-asterisk/musiconhold.conf /etc/asterisk/musiconhold.conf
# `res_musiconhold` haqiqiy xatosi (2026-10-28, m1b-proof.sh orqali topilgan):
# modul BIRINCHI marta 0 (ishlaydigan fayli bo'lgan) sinf bilan yuklansa,
# butunlay "disabled" holatiga qotib qoladi — shundan keyin oddiy `moh reload`
# (AMI'dan `apply_moh()` ishlatadigani) HECH QACHON tiklanmaydi (faqat AMI'dan
# TAQIQLANGAN to'liq module unload+load yordam beradi). Shu sabab image'da
# DOIM mavjud bo'ladigan statik `[default]` sinf uchun haqiqiy fayl generatsiya
# qilinadi (sof Python, ffmpeg shart emas) — Asterisk HECH QACHON 0 sinf bilan
# yuklanmaydi (musiconhold.conf'dagi `[default]` — pastda).
COPY make_moh_fallback.py /tmp/make_moh_fallback.py
RUN python3 /tmp/make_moh_fallback.py && rm /tmp/make_moh_fallback.py
COPY etc-asterisk/queues.conf /etc/asterisk/queues.conf
COPY etc-asterisk/voicemail.conf /etc/asterisk/voicemail.conf
COPY etc-asterisk/voicemail_innova.default.conf /etc/asterisk/voicemail_innova.default.conf
# DIQQAT (M1c'da topilgan): baza image `/etc/asterisk` va
# `/var/lib/asterisk/sounds` ni VOLUME deb e'lon qilgan — compose konteynerni
# qayta yaratganda anonim hajm ESKI tarkibni saqlaydi, image'dagi yangi/
# o'zgargan fayl u yerda KO'RINMAYDI (`--fresh`siz yangilashda Asterisk
# yangi `voicemail_innova.default.conf`ni topmay yiqilar, `manager.conf.tpl`
# eskicha qolardi). Shuning uchun BUTUN `etc-asterisk/` hajmsiz joyga ham
# qo'yiladi va entrypoint.sh har ishga tushishda `/etc/asterisk` ga o'rnatadi.
COPY etc-asterisk/ /usr/share/innova/asterisk/etc/
# Asosiy ovoz fayllari (en, wav). Baza image'da `/var/lib/asterisk/sounds`
# BO'SH edi — app_voicemail salomlashuv/`beep`/`vm-*` fayllarisiz
# `VoiceMail()` darhol FAILED qaytaradi va xabar yozilmaydi (M1c'da topilgan).
# Versiya va sha256 qotirilgan (takrorlanuvchi build).
ARG CORE_SOUNDS=asterisk-core-sounds-en-wav-1.6.1.tar.gz
ARG CORE_SOUNDS_SHA256=07ad543764567ea235d3a96dcd15ecce4521855efc295de6f5443299c331ec0b
RUN mkdir -p /usr/share/innova/asterisk/sounds-en \
 && curl -fsSL -o /tmp/core-sounds.tgz "https://downloads.asterisk.org/pub/telephony/sounds/releases/${CORE_SOUNDS}" \
 && echo "${CORE_SOUNDS_SHA256}  /tmp/core-sounds.tgz" | sha256sum -c - \
 && tar -xzf /tmp/core-sounds.tgz -C /usr/share/innova/asterisk/sounds-en \
 && rm /tmp/core-sounds.tgz \
 && echo "${CORE_SOUNDS}" > /usr/share/innova/asterisk/sounds-en/.innova-core-sounds
COPY etc-asterisk/cdr.conf /etc/asterisk/cdr.conf
COPY etc-asterisk/res_pgsql.conf.tpl /etc/asterisk/res_pgsql.conf.tpl
COPY etc-asterisk/cdr_pgsql.conf.tpl /etc/asterisk/cdr_pgsql.conf.tpl
COPY etc-asterisk/manager.conf.tpl /etc/asterisk/manager.conf.tpl
# M2c §2 (S33) — `security` logger kanali (`${SECURITY_LOG_PATH}` entrypoint'da to'ldiriladi).
COPY etc-asterisk/logger.conf.tpl /etc/asterisk/logger.conf.tpl
COPY entrypoint.sh /usr/local/bin/innova-entrypoint.sh
RUN chmod +x /usr/local/bin/innova-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/innova-entrypoint.sh"]
CMD ["/usr/sbin/asterisk", "-vvvdddf", "-T", "-U", "asterisk", "-p"]
