-- M3b (CRM) — replica/m3b-contract.md §5: Bitrix24 / amoCRM yetkazuvchilari.
--
-- Sozlamalar saqlanadigan joy: `integration_subscriptions` qatori (kind bitrix24|amocrm, tenant'da BITTADAN).
-- Ochiq sozlamalar — `config` (create_lead, popup_max_delay_s, default_user_id, hook_token / base_url,
-- unsorted_for_unknown), sirlar (Bitrix webhook URL + application_token, amo token) — FAQAT `secret_enc`
-- (pgcrypto, JSON). Shu qator outbox obunasi ham: yoqilgan CRM uchun `integration_deliveries` yaratiladi.

-- 1) Holat (§5 `status.last_error`) — yetkazuvchi/test xatosi (sirlar `***`).
alter table integration_subscriptions add column if not exists last_error text;

create unique index if not exists integration_subscriptions_crm_uniq
  on integration_subscriptions (tenant_id, kind) where kind in ('bitrix24', 'amocrm');
create unique index if not exists integration_subscriptions_hook_token_uniq
  on integration_subscriptions ((config ->> 'hook_token')) where kind = 'bitrix24';

-- 2) `updated_at` (409 `stale`) faqat SOZLAMA o'zgarganda yangilanadi — yetkazish natijasi
--    (`last_success_at`, `failing_since`, `last_error`) admin formasini eskirtirmasin.
drop trigger if exists integration_subscriptions_touch on integration_subscriptions;
create trigger integration_subscriptions_touch before update on integration_subscriptions
  for each row when ((old.name, old.config, old.secret_enc, old.events, old.include_internal, old.enabled)
                     is distinct from
                     (new.name, new.config, new.secret_enc, new.events, new.include_internal, new.enabled))
  execute function touch_updated_at();

-- 3) CRM foydalanuvchilari keshi (`POST /test` yuklaydi) — xarita jadvalida ism ko'rsatish uchun.
create table if not exists crm_users (
  tenant_id uuid not null references tenants(id) on delete cascade,
  provider text not null check (provider in ('bitrix24', 'amocrm')),
  crm_user_id text not null,
  name text not null default '',
  inner_phone text,
  loaded_at timestamptz not null default now(),
  primary key (tenant_id, provider, crm_user_id)
);

-- 4) Ichki raqam → CRM foydalanuvchisi. `auto` — Bitrix UF_PHONE_INNER, `manual` — admin (ustun).
create table if not exists crm_user_map (
  tenant_id uuid not null references tenants(id) on delete cascade,
  provider text not null check (provider in ('bitrix24', 'amocrm')),
  extension text not null,
  crm_user_id text not null check (crm_user_id ~ '^[0-9]{1,20}$'),
  source text not null check (source in ('auto', 'manual')),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, provider, extension)
);

-- 5) Qo'ng'iroq ↔ CRM kartasi (Bitrix `CALL_ID`). `origin='crm'` — click-to-call (register QAYTA yuborilmaydi).
create table if not exists crm_call_links (
  tenant_id uuid not null references tenants(id) on delete cascade,
  provider text not null check (provider in ('bitrix24', 'amocrm')),
  linkedid text not null,
  external_call_id text not null,
  origin text not null default 'pbx' check (origin in ('pbx', 'crm')),
  user_id text,
  shown_users text[] not null default '{}',
  created_at timestamptz not null default now(),
  primary key (tenant_id, provider, linkedid)
);
create index if not exists crm_call_links_created_idx on crm_call_links (created_at);
