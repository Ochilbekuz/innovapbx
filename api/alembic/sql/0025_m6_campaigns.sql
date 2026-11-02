-- M6 kampaniyalar: avtoinformator / avtoterish (m6-contract.md §1).
-- Dialer (app/services/campaign_dialer.py) kontaktlarni `FOR UPDATE SKIP LOCKED` bilan oladi,
-- natijani dialplan hangup handler `/internal/campaigns/result` orqali yozadi.

create table campaigns (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null check (char_length(name) between 1 and 80),
  mode text not null check (mode in ('message', 'connect')),
  status text not null default 'draft'
    check (status in ('draft', 'running', 'paused', 'completed', 'stopped')),
  audio_id uuid references audio_files(id) on delete restrict,
  target_number text check (target_number ~ '^[0-9]{2,15}$'),
  dtmf_connect boolean not null default false,
  dtmf_optout boolean not null default false,
  callerid text check (callerid ~ '^[0-9]{3,15}$'),
  max_concurrent int not null default 2 check (max_concurrent between 1 and 30),
  max_attempts int not null default 3 check (max_attempts between 1 and 5),
  retry_delay_s int not null default 600 check (retry_delay_s between 60 and 86400),
  ring_seconds int not null default 25 check (ring_seconds between 10 and 30),
  window_start time not null default '09:00',
  window_end time not null default '20:00',
  days int[] not null default '{1,2,3,4,5,6}'
    check (cardinality(days) between 1 and 7 and days <@ '{1,2,3,4,5,6,7}'::int[]),
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (window_start <> window_end),
  check (mode <> 'message' or audio_id is not null),
  check (mode <> 'connect' or target_number is not null),
  check (mode = 'message' or not (dtmf_connect or dtmf_optout)),
  check (not dtmf_connect or target_number is not null)
);
create unique index ix_campaigns_tenant_name on campaigns (tenant_id, name);
create index ix_campaigns_running on campaigns (status) where status = 'running';
create trigger campaigns_touch before update on campaigns for each row execute function touch_updated_at();

create table campaign_contacts (
  id bigserial primary key,
  campaign_id uuid not null references campaigns(id) on delete cascade,
  number text not null check (number ~ '^[0-9]{3,15}$'),
  name text check (char_length(name) <= 80),
  status text not null default 'pending'
    check (status in ('pending', 'dialing', 'retry', 'done', 'failed', 'skipped')),
  result text,
  attempts int not null default 0,
  next_attempt_at timestamptz,
  last_attempt_at timestamptz,
  billsec int,
  key text check (key ~ '^[0-9*#]$'),
  created_at timestamptz not null default now()
);
create unique index ix_campaign_contacts_number on campaign_contacts (campaign_id, number);
create index ix_campaign_contacts_queue on campaign_contacts (campaign_id, status, next_attempt_at, id)
  where status in ('pending', 'retry');

create table campaign_attempts (
  id bigserial primary key,
  campaign_id uuid not null references campaigns(id) on delete cascade,
  contact_id bigint not null references campaign_contacts(id) on delete cascade,
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  dial_status text,
  billsec int,
  key text
);
create index ix_campaign_attempts_open on campaign_attempts (campaign_id) where ended_at is null;
create index ix_campaign_attempts_contact on campaign_attempts (contact_id);

create table campaign_optouts (
  tenant_id uuid not null references tenants(id) on delete cascade,
  number text not null,
  campaign_id uuid references campaigns(id) on delete set null,
  created_at timestamptz not null default now(),
  primary key (tenant_id, number)
);
