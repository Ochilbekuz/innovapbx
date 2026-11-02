-- M5b §1 Follow Me / §2 SIP sozlamasi QR orqali (m5b-contract.md).
--
-- Follow Me holati `extensions.follow_me` jsonb'da (yagona manba). Asterisk uni
-- `asterisk_ext_state` view'idan realtime o'qiydi (reload'siz) — `*21` esa
-- `fm_enabled` ustuniga `Set(REALTIME(ext_state,...))` bilan YOZADI (trigger).

-- 1) Eski/qisman obyektlarni to'liq shaklga keltirish (0001 standarti 3 kalitli edi).
update extensions set follow_me =
  jsonb_build_object('enabled', false, 'numbers', '[]'::jsonb, 'strategy', 'ring_all',
                     'include_extension', true, 'ring_seconds', 20, 'confirm', true)
  || coalesce(follow_me, '{}'::jsonb);
update extensions set follow_me = jsonb_set(follow_me, '{enabled}', 'false')
 where jsonb_array_length(follow_me -> 'numbers') = 0 and (follow_me ->> 'enabled')::boolean;
alter table extensions alter column follow_me set default
  '{"enabled":false,"numbers":[],"strategy":"ring_all","include_extension":true,"ring_seconds":20,"confirm":true}';
alter table extensions drop constraint if exists extensions_follow_me_shape;
alter table extensions add constraint extensions_follow_me_shape check (
  jsonb_typeof(follow_me -> 'numbers') = 'array'
  and jsonb_array_length(follow_me -> 'numbers') <= 6
  and follow_me ->> 'strategy' in ('ring_all', 'sequential')
  and (follow_me ->> 'ring_seconds')::int between 5 and 120
  and (not coalesce((follow_me ->> 'enabled')::boolean, false) or jsonb_array_length(follow_me -> 'numbers') > 0));

-- 2) Realtime view: PG `create or replace view` faqat OXIRIGA ustun qo'shadi (0018 tartibi saqlanadi).
--    fm_dial  — ring_all uchun tayyor Dial qatori (Local/<raqam>@<code>-fm-leg/n&...),
--    fm_numbers — sequential uchun '&' bilan ajratilgan ro'yxat.
create or replace view asterisk_ext_state as
  select t.code || '-' || e.number as endpoint, e.dnd, e.forward_always, e.forward_busy,
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

-- Trigger: DND/yo'naltirish (0013) + Follow Me yoqish/o'chirish (*21). Ro'yxat bo'sh bo'lsa
-- CHECK yoqishni rad etadi — dialplan qayta o'qib xatoni ko'radi (`invalid`).
create or replace function asterisk_ext_state_update() returns trigger language plpgsql as $$
begin
  update extensions e set dnd = new.dnd,
         forward_always = nullif(new.forward_always, ''),
         forward_busy = nullif(new.forward_busy, ''),
         follow_me = case when new.fm_enabled is distinct from old.fm_enabled
                          then jsonb_set(e.follow_me, '{enabled}', to_jsonb(coalesce(new.fm_enabled, false)))
                          else e.follow_me end
    from tenants t
   where t.id = e.tenant_id and t.code || '-' || e.number = old.endpoint;
  return new;
end $$;

-- 3) Xususiyat kodi *21 — Follow Me almashtirish.
alter table feature_codes drop constraint if exists feature_codes_feature_check;
alter table feature_codes add constraint feature_codes_feature_check check (feature in (
  'voicemail','voicemail_other','dnd_toggle','cf_always_on','cf_always_off','cf_busy_on','cf_busy_off',
  'pickup_group','pickup_direct','park','queue_login','queue_logout','queue_pause','call_flow_toggle',
  'echo_test','speaking_clock','record_now','followme_toggle'));

insert into feature_code_defaults (feature, code, position) values ('followme_toggle', '*21', 15)
on conflict (feature) do nothing;

-- Mavjud tenant'lar: faqat kod bo'sh va boshqa kod bilan prefiks to'qnashuvi bo'lmasa.
insert into feature_codes (tenant_id, feature, code, enabled)
  select t.id, 'followme_toggle', '*21', true from tenants t
   where not exists (select 1 from feature_codes f where f.tenant_id = t.id
                      and (f.code like '*21%' or '*21' like f.code || '%'))
on conflict do nothing;

-- 4) QR orqali sozlash tokenlari: ichki raqamga BITTA faol token (yangisi eskisini almashtiradi).
--    Bazada faqat SHA-256 xesh; token o'zi faqat yaratilgan javobda.
create table if not exists qr_provision_tokens (
  extension_id uuid primary key references extensions(id) on delete cascade,
  tenant_id uuid not null references tenants(id) on delete cascade,
  token_hash bytea not null unique,
  expires_at timestamptz not null,
  first_used_at timestamptz,
  created_by uuid references users(id) on delete set null,
  created_at timestamptz not null default now()
);
