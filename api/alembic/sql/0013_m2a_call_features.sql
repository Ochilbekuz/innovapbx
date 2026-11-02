-- M2a §0–§3: DND / yo'naltirish / pickup guruhi / funksiya kodlari / park.
--
-- Realtime: Asterisk DND va yo'naltirishni `asterisk_ext_state` view'idan
-- (res_config_pgsql, extconfig `ext_state`) o'qiydi va *-kodlar orqali
-- `Set(REALTIME(ext_state,...))` bilan YOZADI — view INSTEAD OF UPDATE trigger
-- bilan yangilanadigan. Yagona haqiqat manbai — `extensions` jadvali (AstDB yo'q).

alter table extensions add column if not exists pickup_group text
  check (pickup_group ~ '^[a-z0-9_-]{1,32}$');

alter table feature_codes drop constraint if exists feature_codes_feature_check;
alter table feature_codes add constraint feature_codes_feature_check check (feature in (
  'voicemail','voicemail_other','dnd_toggle','cf_always_on','cf_always_off','cf_busy_on','cf_busy_off',
  'pickup_group','pickup_direct','park','queue_login','queue_logout','queue_pause','call_flow_toggle',
  'echo_test','speaking_clock','record_now'));

-- Standart kodlar — yagona manba (seed, reset va `default_code` shu yerdan).
create table if not exists feature_code_defaults (
  feature text primary key,
  code text not null unique check (code ~ '^\*[0-9*#]{1,6}$'),
  position integer not null unique
);
insert into feature_code_defaults (feature, code, position) values
  ('voicemail', '*97', 1), ('voicemail_other', '*98', 2), ('dnd_toggle', '*76', 3),
  ('cf_always_on', '*72', 4), ('cf_always_off', '*73', 5), ('cf_busy_on', '*90', 6),
  ('cf_busy_off', '*91', 7), ('pickup_group', '*8', 8), ('pickup_direct', '**', 9),
  ('park', '*70', 10), ('echo_test', '*43', 11), ('speaking_clock', '*60', 12)
on conflict (feature) do nothing;

insert into feature_codes (tenant_id, feature, code, enabled)
  select t.id, d.feature, d.code, true from tenants t cross join feature_code_defaults d
on conflict do nothing;

create or replace function seed_tenant_feature_codes() returns trigger language plpgsql as $$
begin
  insert into feature_codes (tenant_id, feature, code, enabled)
    select new.id, d.feature, d.code, true from feature_code_defaults d
  on conflict do nothing;
  return new;
end $$;
drop trigger if exists tenants_seed_feature_codes on tenants;
create trigger tenants_seed_feature_codes after insert on tenants
  for each row execute function seed_tenant_feature_codes();

-- Realtime holat view'i: endpoint = '<tenant>-<raqam>'. Bo'sh satr = NULL (tozalash).
create or replace view asterisk_ext_state as
  select t.code || '-' || e.number as endpoint, e.dnd, e.forward_always, e.forward_busy
  from extensions e join tenants t on t.id = e.tenant_id where t.status = 'active';

create or replace function asterisk_ext_state_update() returns trigger language plpgsql as $$
begin
  update extensions e set dnd = new.dnd,
         forward_always = nullif(new.forward_always, ''),
         forward_busy = nullif(new.forward_busy, '')
    from tenants t
   where t.id = e.tenant_id and t.code || '-' || e.number = old.endpoint;
  return new;
end $$;
drop trigger if exists asterisk_ext_state_update on asterisk_ext_state;
create trigger asterisk_ext_state_update instead of update on asterisk_ext_state
  for each row execute function asterisk_ext_state_update();

-- ps_endpoints: 0010 dagi ko'rinish + pickup guruhi (named_call/pickup_group).
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
         'info' as dtmf_mode,
         t.code || '-' || e.pickup_group as named_call_group,
         t.code || '-' || e.pickup_group as named_pickup_group
  from extensions e join tenants t on t.id = e.tenant_id where t.status = 'active'
  union all
  select t.code || '-trunk-' || tr.id::text, 'transport-' || tr.transport, t.code || '-trunk-' || tr.id::text,
         case when tr.auth_mode = 'register' then t.code || '-trunk-' || tr.id::text end,
         t.code || '-from-trunk', 'all', array_to_string(tr.codecs, ','), 'no', 'yes', 'yes', 'no',
         null, t.code, null, 'no', 'info', null, null
  from trunks tr join tenants t on t.id = tr.tenant_id where tr.enabled and t.status = 'active';
