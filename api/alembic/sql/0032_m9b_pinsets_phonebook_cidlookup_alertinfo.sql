-- M9 Bo'lak B: PIN to'plamlari (B1), Telefon kitobi + CID Lookup manbalari (B2),
-- kiruvchi marshrutda Alert-Info (B3 — ustun shu yerda qo'shiladi, dialplan
-- tomoni A agent ishi). B4 (ichki raqamlar CSV) — yangi ustun/jadval kerak emas.

-- ───────────────────────── B1: PIN to'plamlari ─────────────────────────
create table pin_sets (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null,
  record_in_cdr boolean not null default true,
  updated_at timestamptz not null default now(),
  unique (tenant_id, name)
);

create table pin_set_pins (
  id uuid primary key default gen_random_uuid(),
  pin_set_id uuid not null references pin_sets(id) on delete cascade,
  pin_hmac text not null,
  label text not null
);
create index on pin_set_pins (pin_set_id);

alter table outbound_routes
  add column pin_set_id uuid references pin_sets(id) on delete restrict;

-- ─────────────── B2: Telefon kitobi + CID Lookup manbalari ───────────────
create table phonebook_contacts (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null,
  company text,
  note text,
  updated_at timestamptz not null default now()
);

create table phonebook_numbers (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  contact_id uuid not null references phonebook_contacts(id) on delete cascade,
  number_norm text not null,
  label text
);
create index on phonebook_numbers (tenant_id, number_norm);

create table cid_lookup_sources (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null,
  kind text not null check (kind in ('phonebook', 'http', 'crm')),
  http_url text,
  http_json_path text,
  timeout_ms int not null default 1500,
  cache_ttl_s int not null default 3600,
  enabled boolean not null default true,
  updated_at timestamptz not null default now(),
  unique (tenant_id, name)
);

alter table inbound_routes
  add column cid_lookup_source_id uuid references cid_lookup_sources(id) on delete set null;

-- ───────────── B3: kiruvchi marshrutda SIP Alert-Info ─────────────
alter table inbound_routes
  add column alert_info text
  check (alert_info ~ '^[A-Za-z0-9=<>:;/._@-]{1,128}$');

-- ───────────── B1 tuzatish: PIN yorlig'i accountcode'ni band qilmaydi ─────────────
-- `accountcode` tenant kodi uchun band (/calls, dashboard, hisobotlar shu bo'yicha
-- filtrlaydi) — PIN to'plami yorlig'i alohida ustunda (`cdr_pgsql` ustun nomi
-- bo'yicha custom CDR o'zgaruvchidan to'ldiradi, modul qayta yuklanganda ko'radi).
alter table cdr add column pin_label text;

-- ───────────── B1 tuzatish: `security_events.kind` ro'yxatiga PIN to'plami
-- hodisalari yetishmayapti (`internal_pinset.py` noto'g'ri PIN/tezlik
-- chegarasida yozadi) — jonli isbotda `CheckViolationError` bilan topildi.
alter table security_events drop constraint if exists security_events_kind_check;
alter table security_events add constraint security_events_kind_check
  check (kind in ('ip_banned', 'ip_unbanned', 'ban_expired',
                  'toll_blocked', 'toll_unblocked', 'concurrent_limit', 'ws_auth_failed',
                  'pinset_fail', 'pinset_rate_limited'));
