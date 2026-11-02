-- Innova PBX — M1a: `ps_endpoints`ga `dtmf_mode = 'info'` ustuni qo'shiladi.
--
-- Sabab (build-log.md'da batafsil): m1a-proof.sh SIPp bilan IVR menyusida
-- raqam bosishni (DTMF) tasdiqlashi kerak (ssenariy 1: «1» bosib navbatga
-- o'tish). RFC2833 (RTP in-band) DTMF uchun SIPp'da haqiqiy RTP/pcap oqimi
-- kerak bo'ladi — informatsion test uchun ortiqcha murakkab. SIP INFO
-- (RFC 2976, `application/dtmf-relay`) signalizatsiya darajasida, RTP/audio
-- shart emas — SIPp skriptida bitta qo'shimcha so'rov. Shu sabab barcha
-- PJSIP endpoint'lar (ichki raqam+trunk) uchun `dtmf_mode='info'`
-- standart qilib belgilandi (M1a qarori — ichki raqamlar ham shu usulda
-- DTMF yuboradi, odatiy IP-telefonlar buni qo'llab-quvvatlaydi).
create or replace view ps_endpoints as
  select t.code || '-' || e.number as id, 'transport-' || case when e.webrtc then 'wss' else 'udp' end as transport,
         t.code || '-' || e.number as aors, t.code || '-' || e.number as auth,
         t.code || '-from-internal' as context, 'all' as disallow, array_to_string(e.codecs, ',') as allow,
         'no' as direct_media, 'yes' as rtp_symmetric, 'yes' as force_rport,
         'yes' as rewrite_contact,
         '"' || coalesce(e.callerid_name, e.name) || '" <' || e.number || '>' as callerid,
         t.code as accountcode, null::text as mailboxes,
         case when e.webrtc then 'yes' else 'no' end as webrtc,
         'info' as dtmf_mode
  from extensions e join tenants t on t.id = e.tenant_id where t.status = 'active'
  union all
  select t.code || '-trunk-' || tr.id::text, 'transport-' || tr.transport, t.code || '-trunk-' || tr.id::text,
         case when tr.auth_mode = 'register' then t.code || '-trunk-' || tr.id::text end,
         t.code || '-from-trunk', 'all', array_to_string(tr.codecs, ','), 'no', 'yes', 'yes', 'no',
         null, t.code, null, 'no', 'info'
  from trunks tr join tenants t on t.id = tr.tenant_id where tr.enabled and t.status = 'active';
