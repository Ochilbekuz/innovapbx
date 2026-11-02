-- SIP login = ichki raqamning o'zi (FreePBX'dagidek), tenant kod prefiksisiz.
--
-- Sabab: tizimda doim BITTA tenant bo'ladi (bootstrap, `auth.py`) — shu sabab
-- `t.code || '-' || e.number` prefiksi ichki raqamlar uchun hech qanday
-- nomlar to'qnashuvidan himoya qilmaydi, faqat foydalanuvchiga ortiqcha
-- qiyinchilik (telefonga "t1-103" emas, "103" yozilishi kerak). Trunk
-- endpoint'lari (`t.code || '-trunk-' || tr.id`) BUTUNLAY TEGILMAYDI — ular
-- haqiqatan ham boshqa (trunk) nomlar maydonida va ko'p trunk bo'lishi mumkin.
--
-- Har bir view/funksiyaning FAQAT eng so'nggi (joriy) ta'rifi shu yerda qayta
-- yoziladi (`create or replace` — ustunlar soni/tartibi o'zgarmagani uchun
-- PostgreSQL cheklovi (faqat oxiriga qo'shish mumkin) bu yerga taalluqli emas).

-- 1) ps_endpoints (0017's oxirgi shakli) — id/aors/auth endi `e.number`.
create or replace view ps_endpoints as
  select e.number as id, 'transport-' || case when e.webrtc then 'wss' else 'udp' end as transport,
         e.number as aors, e.number as auth,
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

-- 2) ps_auths (0009's oxirgi shakli) — id/username endi `e.number`; trunk
--    tarmog'i (realm = null::text — outbound registratsiya xatosini tuzatgan
--    0009'dagi qaror) O'ZGARMAYDI.
create or replace view ps_auths as
  select e.number as id, 'userpass' as auth_type, e.number as username,
         sip_secret(e.sip_password_enc) as password, 'asterisk' as realm
  from extensions e join tenants t on t.id = e.tenant_id
  union all
  select t.code || '-trunk-' || tr.id::text, 'userpass', tr.username, sip_secret(tr.password_enc), null::text as realm
  from trunks tr join tenants t on t.id = tr.tenant_id where tr.auth_mode = 'register';

-- 3) ps_aors (0001'dan beri o'zgarmagan, yagona ta'rif) — id endi `e.number`.
create or replace view ps_aors as
  select e.number as id, e.max_contacts, 'yes' as remove_existing, 60 as qualify_frequency,
         null::text as contact
  from extensions e join tenants t on t.id = e.tenant_id
  union all
  select t.code || '-trunk-' || tr.id::text, 1, 'no', 30, 'sip:' || tr.host || ':' || tr.port
  from trunks tr join tenants t on t.id = tr.tenant_id;

-- 4) asterisk_queue_members (0015's oxirgi shakli) — faqat `interface`/
--    `state_interface` prefiksi olib tashlanadi; `uniqueid` ichki qator kaliti
--    (SIP identity emas), navbat nomlanishi — ikkisi ham TEGILMAYDI.
create or replace view asterisk_queue_members as
  select t.code || '-q-' || q.id::text || '-' || e.number as uniqueid,
         t.code || '-q-' || q.id::text as queue_name,
         'PJSIP/' || e.number as interface, e.name as membername,
         'PJSIP/' || e.number as state_interface, qm.penalty,
         case when qm.paused or e.dnd then 1 else 0 end as paused,
         coalesce(qm.pause_reason, '')::varchar(80) as reason_paused
  from queue_members qm join queues q on q.id = qm.queue_id
  join extensions e on e.id = qm.extension_id join tenants t on t.id = q.tenant_id
  where not qm.dynamic or qm.logged_in;

-- 5) asterisk_ext_state (0024's oxirgi shakli, Follow Me bilan) + uning
--    INSTEAD OF UPDATE trigger funksiyasi — `endpoint` endi `e.number`,
--    moslash (join) ham shunga ko'ra.
create or replace view asterisk_ext_state as
  select e.number as endpoint, e.dnd, e.forward_always, e.forward_busy,
         e.recording,
         case when coalesce((s.recording ->> 'external_only')::boolean, false) then 't' else 'f' end
           as rec_external_only,
         coalesce((e.follow_me ->> 'enabled')::boolean, false) as fm_enabled,
         e.follow_me ->> 'strategy' as fm_strategy,
         (e.follow_me ->> 'ring_seconds')::int as fm_ring,
         case when coalesce((e.follow_me ->> 'confirm')::boolean, true) then 't' else 'f' end as fm_confirm,
         (select string_agg(n, '&' order by o) from jsonb_array_elements_text(e.follow_me -> 'numbers')
            with ordinality as x(n, o)) as fm_numbers,
         (select string_agg('Local/' || n || '@' || t.code || '-fm-leg/n', '&' order by o)
            from (select e.number as n, 0::bigint as o
                   where coalesce((e.follow_me ->> 'include_extension')::boolean, true)
                  union all
                  select n, o from jsonb_array_elements_text(e.follow_me -> 'numbers') with ordinality as x(n, o)) legs)
           as fm_dial
  from extensions e join tenants t on t.id = e.tenant_id
  left join system_settings s on s.tenant_id = e.tenant_id
  where t.status = 'active';

create or replace function asterisk_ext_state_update() returns trigger language plpgsql as $$
begin
  update extensions e set dnd = new.dnd,
         forward_always = nullif(new.forward_always, ''),
         forward_busy = nullif(new.forward_busy, ''),
         follow_me = case when new.fm_enabled is distinct from old.fm_enabled
                          then jsonb_set(e.follow_me, '{enabled}', to_jsonb(coalesce(new.fm_enabled, false)))
                          else e.follow_me end
    from tenants t
   where t.id = e.tenant_id and e.number = old.endpoint;
  return new;
end $$;

-- 6) asterisk_agent_state (0015's oxirgi shakli) + uning INSTEAD OF UPDATE
--    trigger funksiyasi — `endpoint` endi `e.number`.
create or replace view asterisk_agent_state as
  select e.number as endpoint,
         coalesce(bool_or(qm.logged_in) filter (where qm.dynamic), false) as logged_in,
         coalesce(bool_or(qm.paused), false) as paused
  from extensions e
  join tenants t on t.id = e.tenant_id
  left join queue_members qm on qm.extension_id = e.id
  where t.status = 'active'
  group by t.code, e.number;

create or replace function asterisk_agent_state_update() returns trigger language plpgsql as $$
declare
  v_ext_id uuid;
begin
  select e.id into v_ext_id from extensions e join tenants t on t.id = e.tenant_id
   where e.number = old.endpoint;
  if v_ext_id is null then
    return new;
  end if;
  if new.logged_in is distinct from old.logged_in then
    update queue_members set logged_in = new.logged_in
     where extension_id = v_ext_id and dynamic;
  end if;
  if new.paused is distinct from old.paused then
    update queue_members set paused = new.paused,
           pause_reason = case when new.paused then pause_reason else null end
     where extension_id = v_ext_id;
  end if;
  return new;
end $$;
