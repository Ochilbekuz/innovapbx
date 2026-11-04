-- M12 A1/A2 (asterisk-engineer) — Kun/Tun rejimi (`day_night`) + DISA (`disa`).
-- m12-contract.md bo'lim A1/A2.

-- `call_targets.kind`ga ikki yangi tur qo'shiladi — boshqa marshrut/IVR/vaqt
-- sharti day_night/disa'ni manzil sifatida ko'rsata oladi (satellit qolipi,
-- `compiler.py::_SATELLITE_BUILDERS`).
alter table call_targets drop constraint if exists call_targets_kind_check;
alter table call_targets add constraint call_targets_kind_check check (kind in (
  'extension','ring_group','queue','ivr','time_condition','announcement','voicemail',
  'conference','external','hangup','busy','feature','misc','day_night','disa'));

-- ───────────────────────── A1: Kun/Tun rejimi ─────────────────────────
create table if not exists day_night (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  target_id uuid not null unique references call_targets(id) on delete cascade,
  name text not null,
  -- bir xonali kod (`*28<code>` funksiya kodi, tenant ichida unikal).
  code text not null check (code ~ '^[0-9]$'),
  mode text not null default 'day' check (mode in ('day', 'night')),
  day_target_id uuid not null references call_targets(id) on delete restrict,
  night_target_id uuid not null references call_targets(id) on delete restrict,
  -- PIN — mavjud HMAC-SHA256 usuli (`pin_hmac.py`, `pin_set_pins.pin_hmac` BILAN
  -- BIR XIL qolip), ochiq matn saqlanmaydi. NULL = PIN so'ralmaydi.
  pin_hmac text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, code),
  unique (tenant_id, name)
);
create index if not exists ix_day_night_tenant on day_night (tenant_id);

-- ───────────────────────── A2: DISA ─────────────────────────
create table if not exists disa (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  target_id uuid not null unique references call_targets(id) on delete cascade,
  name text not null,
  pin_hmac text,
  -- Xavfsizlik (m12-contract.md A2): PIN bo'sh DISA FAQAT `allow_no_pin=true`
  -- bilan API orqali yaratilishi mumkin — DB darajasida CHECK bilan mustahkamlanadi.
  allow_no_pin boolean not null default false,
  check (pin_hmac is not null or allow_no_pin),
  cid_override text,
  digit_timeout int not null default 5 check (digit_timeout between 1 and 60),
  response_timeout int not null default 10 check (response_timeout between 1 and 60),
  max_attempts int not null default 3 check (max_attempts between 1 and 10),
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists ix_disa_tenant on disa (tenant_id);

-- `internal_day_night.py`/`internal_disa.py` xato PIN bo'yicha `security_events`ga
-- `day_night_pin_fail`/`disa_pin_fail` yozadi (`internal_pinset.py::_deny_with_event`
-- BILAN BIR XIL qolip) — mavjud CHECK ro'yxatiga qo'shiladi.
alter table security_events drop constraint if exists security_events_kind_check;
alter table security_events add constraint security_events_kind_check check (kind in (
  'ip_banned','ip_unbanned','ban_expired','toll_blocked','toll_unblocked','concurrent_limit',
  'ws_auth_failed','pinset_fail','pinset_rate_limited','day_night_pin_fail','disa_pin_fail'));
