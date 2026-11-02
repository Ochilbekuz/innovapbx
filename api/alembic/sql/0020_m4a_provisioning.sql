-- M4a — replica/m4a-contract.md §1: telefon apparatlarini avtoprovizioning.
--
-- `devices` (0001 dan) kengaytiriladi; tugmalar (`device_keys`), topilgan (ro'yxatda yo'q MAC) apparatlar
-- (`discovered_devices`), provizioning so'rovlari jurnali (`provision_requests`, 30 kun) va
-- `system_settings.provisioning` (token, tarmoqlar, til/vaqt/NTP, transport, server hosti, vendor extra).
-- Sir (SIP paroli, apparat admin paroli) bu jadvallarning HECH BIRIDA ochiq ko'rinishda yo'q.

-- 1) Apparat ustunlari.
alter table devices add column if not exists label text;
alter table devices add column if not exists last_seen_at timestamptz;
alter table devices add column if not exists last_ip inet;
alter table devices add column if not exists user_agent text;
alter table devices add column if not exists firmware text;
alter table devices add column if not exists config_hash text;
alter table devices add column if not exists enabled boolean not null default true;
alter table devices add column if not exists notes text;
create index if not exists devices_tenant_idx on devices (tenant_id);

-- `updated_at` (409 `stale`) faqat ADMIN maydoni o'zgarganda yangilanadi — apparat so'rovi (last_seen_at, last_ip,
-- config_hash, provisioned_at, ...) admin formasini eskirtirmasin (0019 dagi naqsh).
drop trigger if exists devices_touch on devices;
create trigger devices_touch before update on devices
  for each row when ((old.extension_id, old.kind, old.vendor, old.model, old.mac, old.label, old.enabled, old.notes)
                     is distinct from
                     (new.extension_id, new.kind, new.vendor, new.model, new.mac, new.label, new.enabled, new.notes))
  execute function touch_updated_at();

-- 2) Dastur tugmalari (BLF, tez terish, ...). Tugmalar o'zgarishi apparat `updated_at` ini API orqali yangilaydi.
create table if not exists device_keys (
  device_id uuid not null references devices(id) on delete cascade,
  idx int not null check (idx between 1 and 60),
  type text not null check (type in ('blf', 'speed_dial', 'line', 'park', 'dnd', 'none')),
  value text not null default '',
  label text not null default '',
  primary key (device_id, idx)
);

-- 3) Topilgan apparatlar: to'g'ri token + ro'yxatda yo'q MAC so'rovi. Biriktirilganda o'chiriladi.
create table if not exists discovered_devices (
  tenant_id uuid not null references tenants(id) on delete cascade,
  mac macaddr not null,
  vendor text check (vendor in ('yealink', 'grandstream', 'fanvil')),
  model text,
  ip inet,
  user_agent text,
  firmware text,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  requests int not null default 1,
  primary key (tenant_id, mac)
);

-- 4) So'rovlar jurnali. `tenant_id` NULL — token hech bir tenant'ga mos kelmadi (`bad_token`) yoki IP bloklangan.
--    `path` da token MASKALANGAN (`/prov/***/<fayl>`).
create table if not exists provision_requests (
  id bigint generated always as identity primary key,
  tenant_id uuid references tenants(id) on delete cascade,
  at timestamptz not null default now(),
  ip inet,
  mac macaddr,
  vendor text,
  path text not null,
  status_code int not null,
  reason text not null check (reason in
    ('ok', 'unknown_mac', 'bad_token', 'network_denied', 'rate_limited', 'legacy_binary', 'not_found')),
  user_agent text
);
create index if not exists provision_requests_tenant_at_idx on provision_requests (tenant_id, at desc);
create index if not exists provision_requests_at_idx on provision_requests (at);

-- 5) Sozlamalar. Har tenant'ga darhol tasodifiy token (yangi qatorlar ham — ustun sukuti).
alter table system_settings add column if not exists provisioning jsonb not null
  default jsonb_build_object('prov_token', encode(gen_random_bytes(16), 'hex'));
update system_settings set provisioning = provisioning
  || jsonb_build_object('prov_token', encode(gen_random_bytes(16), 'hex'))
  where coalesce(provisioning ->> 'prov_token', '') = '';
create unique index if not exists system_settings_prov_token_uniq on system_settings ((provisioning ->> 'prov_token'));

-- 6) Alert turi: provizioning bruteforce (§0 4-qatlam).
alter table alert_log drop constraint if exists alert_log_kind_check;
alter table alert_log add constraint alert_log_kind_check check (kind in (
  'ip_banned', 'toll_blocked', 'concurrent_limit', 'trunk_down', 'trunk_up', 'test',
  'webhook_disabled', 'recording_error', 'prov_bruteforce'));
