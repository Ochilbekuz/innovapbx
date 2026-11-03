-- M9 Bo'lak A — m9-freepbx-gaps-contract.md A1-A5:
-- A1 E'lonlar (allow_skip/repeat_key/answer), A2 Boshqa manzillar/ilovalar,
-- A3 Parking sozlamalari, A4 Paging/Intercom guruhlari, A5 Call Waiting.

-- ───────────────────────── A1: announcements ─────────────────────────
alter table announcements add column if not exists allow_skip boolean not null default false;
alter table announcements add column if not exists repeat_key text;
alter table announcements add column if not exists answer boolean not null default true;
alter table announcements drop constraint if exists announcements_repeat_key_check;
alter table announcements add constraint announcements_repeat_key_check
  check (repeat_key is null or repeat_key ~ '^[0-9*#]$');

-- ───────────────────────── A2: Boshqa manzillar + ilovalar ─────────────────────────
-- `call_targets.kind` CHECK'ga FAQAT 'misc' qo'shiladi — 'announcement'/'feature'
-- 0001'da ALLAQACHON bor edi (tasdiqlangan: sed -n '85,95p' 0001_schema.sql).
alter table call_targets drop constraint if exists call_targets_kind_check;
alter table call_targets add constraint call_targets_kind_check check (kind in (
  'extension','ring_group','queue','ivr','time_condition','announcement','voicemail',
  'conference','external','hangup','busy','feature','misc'));

create table if not exists misc_destinations (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  target_id uuid not null unique references call_targets(id) on delete cascade,
  name text not null,
  -- Oddiy ichki terish kabi — toll-fraud/PIN qoidalari BYPASS qilinmaydi
  -- (dialplan `{code}-outbound`ga Goto qiladi, m9-freepbx-gaps-contract.md A2).
  dial text not null check (dial ~ '^[0-9*#+]{1,32}$'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists misc_applications (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null,
  -- Funksiya kodi uslubida (`*`+belgilar) YOKI oddiy raqam.
  code text not null check (code ~ '^(\*[0-9*#]{1,6}|[0-9]{1,10})$'),
  target_id uuid not null references call_targets(id) on delete restrict,
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, code)
);
create index if not exists ix_misc_applications_target on misc_applications (target_id);

-- ───────────────────────── A3: Parking sozlamalari ─────────────────────────
-- `system_settings` namunasi bo'yicha — tenant bo'yicha YAGONA qator.
create table if not exists parking_settings (
  tenant_id uuid primary key references tenants(id) on delete cascade,
  lot_number text not null default '700' check (lot_number ~ '^[0-9]{1,6}$'),
  first_slot int not null default 701 check (first_slot > 0),
  slot_count int not null default 20 check (slot_count between 1 and 100),
  timeout_s int not null default 60 check (timeout_s between 10 and 3600),
  on_timeout text not null default 'origin' check (on_timeout in ('origin', 'target')),
  timeout_target_id uuid references call_targets(id) on delete set null,
  moh_class_id uuid references moh_classes(id) on delete set null,
  updated_at timestamptz not null default now()
);

insert into parking_settings (tenant_id)
select t.id from tenants t
where not exists (select 1 from parking_settings p where p.tenant_id = t.id);

-- ───────────────────────── A4: Paging/Intercom ─────────────────────────
create table if not exists page_groups (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null,
  number text not null check (number ~ '^[0-9*#]{2,10}$'),
  duplex boolean not null default false,
  skip_busy boolean not null default true,
  beep boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, number)
);

create table if not exists page_group_members (
  page_group_id uuid not null references page_groups(id) on delete cascade,
  extension_id uuid not null references extensions(id) on delete cascade,
  primary key (page_group_id, extension_id)
);

-- ───────────────────────── A5: Call Waiting ─────────────────────────
alter table extensions add column if not exists call_waiting boolean not null default true;

-- `asterisk_ext_state`: PostgreSQL faqat view OXIRIGA ustun qo'shishga ruxsat
-- beradi — 0028'ning oxirgi ta'rifi (13 ustun) + `call_waiting` (14-ustun).
-- `dnd` namunasi bo'yicha TO'G'RIDAN-TO'G'RI boolean o'tkaziladi (text castsiz).
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
           as fm_dial,
         e.recording_out,
         e.call_waiting
  from extensions e join tenants t on t.id = e.tenant_id
  left join system_settings s on s.tenant_id = e.tenant_id
  where t.status = 'active';

-- Trigger funksiyasi: `fm_enabled` namunasi bo'yicha `call_waiting` yozish qo'llab-quvvatlanadi.
create or replace function asterisk_ext_state_update() returns trigger language plpgsql as $$
begin
  update extensions e set dnd = new.dnd,
         forward_always = nullif(new.forward_always, ''),
         forward_busy = nullif(new.forward_busy, ''),
         follow_me = case when new.fm_enabled is distinct from old.fm_enabled
                          then jsonb_set(e.follow_me, '{enabled}', to_jsonb(coalesce(new.fm_enabled, false)))
                          else e.follow_me end,
         call_waiting = case when new.call_waiting is distinct from old.call_waiting
                          then coalesce(new.call_waiting, true)
                          else e.call_waiting end
    from tenants t
   where t.id = e.tenant_id and e.number = old.endpoint;
  return new;
end $$;

-- Xususiyat kodlari: *80 (intercom), *56 (cw_on), *57 (cw_off).
alter table feature_codes drop constraint if exists feature_codes_feature_check;
alter table feature_codes add constraint feature_codes_feature_check check (feature in (
  'voicemail','voicemail_other','dnd_toggle','cf_always_on','cf_always_off','cf_busy_on','cf_busy_off',
  'pickup_group','pickup_direct','park','echo_test','speaking_clock','queue_login','queue_pause',
  'followme_toggle','intercom','cw_on','cw_off'));

insert into feature_code_defaults (feature, code, position) values
  ('intercom', '*80', 16), ('cw_on', '*56', 17), ('cw_off', '*57', 18)
on conflict (feature) do nothing;

insert into feature_codes (tenant_id, feature, code, enabled)
  select t.id, d.feature, d.code, true from tenants t
  cross join feature_code_defaults d where d.feature in ('intercom', 'cw_on', 'cw_off')
on conflict do nothing;
