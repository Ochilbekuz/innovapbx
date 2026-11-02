-- 0002 — `extensions.enabled` ustuni qo'shildi (m0-contract.md: Extension.enabled
-- maydoni kontraktda bor, lekin replica/schema.sql'ning asl jadval ta'rifida yo'q
-- edi — bu qator shu nomuvofiqlikni tuzatadi, qo'shimcha ustun, hech narsani
-- buzmaydi). PJSIP realtime `ps_endpoints` view ham yangilanadi: o'chirilgan
-- (enabled=false) ichki raqam ENDI ro'yxatdan o'ta olmaydi (realtime, reload shart
-- emas — faqat view WHERE sharti).
alter table extensions add column if not exists enabled boolean not null default true;

create or replace view ps_endpoints as
  select t.code || '-' || e.number as id, 'transport-' || case when e.webrtc then 'wss' else 'udp' end as transport,
         t.code || '-' || e.number as aors, t.code || '-' || e.number as auth,
         t.code || '-from-internal' as context, 'all' as disallow, array_to_string(e.codecs, ',') as allow,
         'no' as direct_media, 'yes' as rtp_symmetric, 'yes' as force_rport,
         'yes' as rewrite_contact,
         '"' || coalesce(e.callerid_name, e.name) || '" <' || e.number || '>' as callerid,
         t.code as accountcode, null::text as mailboxes,
         case when e.webrtc then 'yes' else 'no' end as webrtc
  from extensions e join tenants t on t.id = e.tenant_id where t.status = 'active' and e.enabled
  union all
  select t.code || '-trunk-' || tr.id::text, 'transport-' || tr.transport, t.code || '-trunk-' || tr.id::text,
         case when tr.auth_mode = 'register' then t.code || '-trunk-' || tr.id::text end,
         t.code || '-from-trunk', 'all', array_to_string(tr.codecs, ','), 'no', 'yes', 'yes', 'no',
         null, t.code, null, 'no'
  from trunks tr join tenants t on t.id = tr.tenant_id where tr.enabled and t.status = 'active';
