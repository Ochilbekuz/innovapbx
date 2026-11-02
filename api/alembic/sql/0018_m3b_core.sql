-- M3b (core) — replica/m3b-contract.md §0–§4: qo'ng'iroq yozuvlari, hodisalar outbox'i,
-- webhook/CRM obunalari, yetkazishlar, REST API kalitlari, API originate so'rovlari.

-- 1) Sozlamalar (§1, §2): yozuv siyosati va integratsiya parametrlari — JSONB bo'limlar
--    (`toll_fraud`/`telegram`/`sip_guard` qolipi). `recording_retention_days` 0001 dan bor.
alter table system_settings add column if not exists recording jsonb not null
  default '{"external_only": false, "format": "wav"}'::jsonb;
alter table system_settings add column if not exists integrations jsonb not null
  default '{"public_base_url": "", "recording_link_ttl_s": 604800}'::jsonb;

-- 2) Asterisk realtime (`ext_state`) — yozuv siyosatini dialplan `innova-rec` shu yerdan
--    o'qiydi. PG `create or replace view` faqat OXIRIGA ustun qo'shishga ruxsat beradi.
create or replace view asterisk_ext_state as
  select t.code || '-' || e.number as endpoint, e.dnd, e.forward_always, e.forward_busy,
         e.recording,
         case when coalesce((s.recording ->> 'external_only')::boolean, false) then 't' else 'f' end
           as rec_external_only
  from extensions e join tenants t on t.id = e.tenant_id
  left join system_settings s on s.tenant_id = e.tenant_id
  where t.status = 'active';

-- 3) Yozuvlar (§1) — fayl yopilgach API to'ldiradi (yo'l `monitor` katalogiga nisbiy).
create table if not exists call_recordings (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  linkedid text not null,
  uniqueid text not null,
  path text not null unique,
  extension text,
  started_at timestamptz not null,
  duration_s integer not null default 0,
  size_bytes bigint not null default 0,
  deleted_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists call_recordings_linkedid_idx on call_recordings (tenant_id, linkedid);
create index if not exists call_recordings_started_idx on call_recordings (tenant_id, started_at)
  where deleted_at is null;

-- 4) Hodisa holati (§0): kech kelgan AMI hodisasi tugagan qo'ng'iroqni qayta tiriltirmasin
--    (tugagan holat 10 daqiqa TTL), osilib qolgan qo'ng'iroq majburan yopilsin.
create table if not exists call_event_state (
  linkedid text primary key,
  tenant_id uuid not null references tenants(id) on delete cascade,
  info jsonb not null default '{}'::jsonb,
  ringing_sent boolean not null default false,
  answered_sent boolean not null default false,
  ended_sent boolean not null default false,
  last_hangup_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists call_event_state_open_idx on call_event_state (created_at) where not ended_sent;

-- 5) Outbox (§0): yagona hodisa manbai. `dedupe_key` — ringing:<linkedid>:<ext>,
--    answered:<linkedid>, ended:<linkedid>, test:<uuid>.
create table if not exists integration_events (
  id uuid primary key default gen_random_uuid(),
  seq bigserial not null,
  tenant_id uuid not null references tenants(id) on delete cascade,
  type text not null check (type in ('call.ringing', 'call.answered', 'call.ended', 'test.ping')),
  dedupe_key text not null,
  call_id text,
  internal boolean not null default false,
  payload jsonb not null,
  occurred_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  unique (tenant_id, dedupe_key)
);
create index if not exists integration_events_created_idx on integration_events (created_at);

create table if not exists integration_subscriptions (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  kind text not null check (kind in ('webhook', 'bitrix24', 'amocrm')),
  name text not null check (length(name) between 1 and 100),
  config jsonb not null default '{}'::jsonb,
  secret_enc text,                         -- crypto.encrypt_secret (pgcrypto, base64)
  events text[] not null default '{call.ringing,call.answered,call.ended}',
  include_internal boolean not null default false,
  enabled boolean not null default true,
  disabled_reason text,
  failing_since timestamptz,
  last_success_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists integration_subscriptions_tenant_idx on integration_subscriptions (tenant_id, kind);

create table if not exists integration_deliveries (
  id uuid primary key default gen_random_uuid(),
  seq bigserial not null,
  tenant_id uuid not null references tenants(id) on delete cascade,
  subscription_id uuid not null references integration_subscriptions(id) on delete cascade,
  event_id uuid not null references integration_events(id) on delete cascade,
  call_id text,
  status text not null default 'pending' check (status in ('pending', 'delivered', 'dead')),
  attempts integer not null default 0,
  next_attempt_at timestamptz not null default now(),
  last_attempt_at timestamptz,
  last_status_code integer,
  last_error text,
  response_body text,
  delivered_at timestamptz,
  created_at timestamptz not null default now(),
  unique (subscription_id, event_id)
);
create index if not exists integration_deliveries_pending_idx on integration_deliveries (next_attempt_at, seq)
  where status = 'pending';
create index if not exists integration_deliveries_order_idx on integration_deliveries (subscription_id, call_id, seq)
  where status = 'pending';
create index if not exists integration_deliveries_sub_idx on integration_deliveries (subscription_id, created_at);

-- 6) REST API kalitlari (§4): faqat sha256 + prefix saqlanadi.
create table if not exists api_keys (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null check (length(name) between 1 and 100),
  prefix text not null unique check (prefix ~ '^[a-z0-9]{8}$'),
  key_hash text not null,
  scopes text[] not null default '{}',
  expires_at timestamptz,
  revoked_at timestamptz,
  last_used_at timestamptz,
  created_by uuid references users(id) on delete set null,
  created_at timestamptz not null default now()
);

create table if not exists api_originate_requests (
  id uuid primary key,
  tenant_id uuid not null references tenants(id) on delete cascade,
  api_key_id uuid references api_keys(id) on delete set null,
  extension text not null,
  to_number text not null,
  external_id text,
  created_at timestamptz not null default now()
);

-- 7) Ogohlantirish turlari (§3 webhook avto-o'chirish, §1 yozuv diski xatosi).
alter table alert_log drop constraint if exists alert_log_kind_check;
alter table alert_log add constraint alert_log_kind_check check (kind in (
  'ip_banned', 'toll_blocked', 'concurrent_limit', 'trunk_down', 'trunk_up', 'test',
  'webhook_disabled', 'recording_error'));

-- 9) updated_at triggerlari (0001 dagi sikl faqat o'sha paytdagi jadvallarni qamragan).
drop trigger if exists call_event_state_touch on call_event_state;
create trigger call_event_state_touch before update on call_event_state
  for each row execute function touch_updated_at();
drop trigger if exists integration_subscriptions_touch on integration_subscriptions;
create trigger integration_subscriptions_touch before update on integration_subscriptions
  for each row execute function touch_updated_at();
