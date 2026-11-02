-- M3a (replica/m3a-contract.md): WebRTC softfon.
--
-- 1) `security_events.transport` — §0: WS/WSS orqali kelgan muvaffaqiyatsiz SIP autentifikatsiya
--    avto-ban uchun SANALMAYDI (Asterisk nginx IP'sini ko'radi), lekin iz qoladi:
--    `kind='ws_auth_failed'`, `transport='ws'`. Eski hodisalar uchun NULL (transportsiz).
alter table security_events add column if not exists transport text
  check (transport is null or transport in ('udp', 'tcp', 'tls', 'ws'));
alter table security_events drop constraint if exists security_events_kind_check;
alter table security_events add constraint security_events_kind_check
  check (kind in ('ip_banned', 'ip_unbanned', 'ban_expired',
                  'toll_blocked', 'toll_unblocked', 'concurrent_limit', 'ws_auth_failed'));

-- 2) ps_endpoints: 0013 bilan AYNAN bir xil, faqat `dtmf_mode` — webrtc raqamda `rfc4733`
--    (brauzer DTMF'ni RTCDTMFSender/RFC 4733 bilan yuboradi; `info` rejimida Asterisk SDP'da
--    telephone-event taklif qilmaydi va brauzer DTMF yubora olmaydi). Oddiy SIP — `info` (0004).
create or replace view ps_endpoints as
  select t.code || '-' || e.number as id, 'transport-' || case when e.webrtc then 'wss' else 'udp' end as transport,
         t.code || '-' || e.number as aors, t.code || '-' || e.number as auth,
         t.code || '-from-internal' as context, 'all' as disallow, array_to_string(e.codecs, ',') as allow,
         'no' as direct_media, 'yes' as rtp_symmetric, 'yes' as force_rport,
         'yes' as rewrite_contact,
         '"' || coalesce(e.callerid_name, e.name) || '" <' || e.number || '>' as callerid,
         t.code as accountcode,
         (select vb.mailbox || '@' || t.code from voicemail_boxes vb where vb.extension_id = e.id) as mailboxes,
         case when e.webrtc then 'yes' else 'no' end as webrtc,
         case when e.webrtc then 'rfc4733' else 'info' end as dtmf_mode,
         t.code || '-' || e.pickup_group as named_call_group,
         t.code || '-' || e.pickup_group as named_pickup_group
  from extensions e join tenants t on t.id = e.tenant_id where t.status = 'active'
  union all
  select t.code || '-trunk-' || tr.id::text, 'transport-' || tr.transport, t.code || '-trunk-' || tr.id::text,
         case when tr.auth_mode = 'register' then t.code || '-trunk-' || tr.id::text end,
         t.code || '-from-trunk', 'all', array_to_string(tr.codecs, ','), 'no', 'yes', 'yes', 'no',
         null, t.code, null, 'no', 'info', null, null
  from trunks tr join tenants t on t.id = tr.tenant_id where tr.enabled and t.status = 'active';
