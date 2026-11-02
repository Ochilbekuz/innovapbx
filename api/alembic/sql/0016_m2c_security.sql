-- M2c (replica/m2c-contract.md): SIP hujum himoyasi, toll-fraud, ogohlantirishlar.
--
-- `system_settings.toll_fraud`/`telegram` 0001'dan bor edi, lekin hech kim
-- ishlatmagan (eski kalitlar: max_international_per_hour, night_alert) — M2c
-- shartnomasidagi yangi shaklga o'tkaziladi. Standart va chegaralar kodda —
-- `app/services/security_config.py` (YAGONA joy); bu yerdagi standart faqat
-- yangi qatorlar uchun boshlang'ich qiymat.

alter table system_settings add column if not exists sip_guard jsonb not null
  default '{"enabled":true,"max_failures":5,"window_s":60,"ban_s":3600,"trusted_nets":[]}';
alter table system_settings alter column toll_fraud set default
  '{"enabled":true,"max_concurrent_outbound":0,"ext_max_per_hour":60,"ext_international_per_day":20}';
alter table system_settings alter column telegram set default
  '{"chat_ids":[],"dedup_s":600,"events":{"ip_banned":true,"toll_blocked":true,"concurrent_limit":true,"trunk_down":true,"trunk_up":true}}';
update system_settings set
  toll_fraud = '{"enabled":true,"max_concurrent_outbound":0,"ext_max_per_hour":60,"ext_international_per_day":20}'
  where not (toll_fraud ? 'ext_max_per_hour');
update system_settings set
  telegram = '{"chat_ids":[],"dedup_s":600,"events":{"ip_banned":true,"toll_blocked":true,"concurrent_limit":true,"trunk_down":true,"trunk_up":true}}'
  where not (telegram ? 'chat_ids');

create table if not exists ip_bans (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  ip inet not null,
  reason text not null check (reason in ('auto', 'manual')),
  failures integer not null default 0,
  note text check (note is null or char_length(note) <= 200),
  created_by uuid references users(id) on delete set null,
  created_at timestamptz not null default now(),
  expires_at timestamptz,
  lifted_at timestamptz,
  lift_reason text check (lift_reason is null or lift_reason in ('manual', 'expired'))
);
-- Bitta IP uchun bir vaqtda faqat BITTA faol ban (409 already_banned shu indeksga tayanadi).
create unique index if not exists ip_bans_active_uq on ip_bans (tenant_id, ip) where lifted_at is null;
create index if not exists ip_bans_tenant_created_idx on ip_bans (tenant_id, created_at);

create table if not exists sip_attack_stats (
  tenant_id uuid not null references tenants(id) on delete cascade,
  hour timestamptz not null,
  ip inet not null,
  failures integer not null default 0,
  blocked integer not null default 0,
  last_at timestamptz not null default now(),
  primary key (tenant_id, hour, ip)
);

create table if not exists security_events (
  id bigserial primary key,
  tenant_id uuid not null references tenants(id) on delete cascade,
  at timestamptz not null default now(),
  kind text not null check (kind in ('ip_banned', 'ip_unbanned', 'ban_expired',
                                     'toll_blocked', 'toll_unblocked', 'concurrent_limit')),
  ip inet,
  extension_id uuid references extensions(id) on delete set null,
  details jsonb not null default '{}'
);
create index if not exists security_events_tenant_at_idx on security_events (tenant_id, at);

alter table extensions add column if not exists toll_blocked_at timestamptz;
alter table extensions add column if not exists toll_block_reason text
  check (toll_block_reason is null or toll_block_reason in ('per_hour', 'international_per_day'));
alter table extensions add column if not exists toll_unblocked_at timestamptz;

create table if not exists outbound_attempts (
  id bigserial primary key,
  tenant_id uuid not null references tenants(id) on delete cascade,
  extension_id uuid not null references extensions(id) on delete cascade,
  number text not null,
  international boolean not null default false,
  allowed boolean not null,
  at timestamptz not null default now()
);
create index if not exists outbound_attempts_ext_at_idx on outbound_attempts (extension_id, at);

create table if not exists alert_log (
  id bigserial primary key,
  tenant_id uuid not null references tenants(id) on delete cascade,
  at timestamptz not null default now(),
  kind text not null check (kind in ('ip_banned', 'toll_blocked', 'concurrent_limit', 'trunk_down', 'trunk_up', 'test')),
  key text not null default '',
  text text not null,
  status text not null check (status in ('pending', 'sent', 'failed', 'suppressed', 'disabled')),
  error text,
  sent_at timestamptz
);
create index if not exists alert_log_tenant_at_idx on alert_log (tenant_id, at);
create index if not exists alert_log_dedup_idx on alert_log (tenant_id, kind, key, at);
create index if not exists alert_log_pending_idx on alert_log (id) where status = 'pending';
