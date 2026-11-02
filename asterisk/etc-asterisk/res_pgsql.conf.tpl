; Innova PBX — res_config_pgsql ulanishi (PJSIP realtime: ps_endpoints, ps_auths,
; ps_aors, ps_endpoint_id_ips, ps_registrations — sorcery.conf'da bog'langan).
; entrypoint.sh buni envsubst qilib /etc/asterisk/res_pgsql.conf ga yozadi.

[general]
hostname=${POSTGRES_HOST}
port=${POSTGRES_PORT}
dbname=${POSTGRES_DB}
user=${POSTGRES_USER}
password=${POSTGRES_PASSWORD}
appname=innova-pjsip-realtime
requirements=warn
