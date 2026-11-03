-- M10 Bo'lak A: qayta chaqirish vidjeti, o'tkazib yuborilgan qo'ng'iroq
-- bildirishnomasi, Yandex SpeechKit TTS sozlamalari.

-- -------------------------------------------------------------- A1: qayta chaqirish vidjeti (S17)
create table callback_widgets (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references tenants(id) on delete cascade,
    name text not null,
    public_key text not null unique,
    target_id uuid not null references call_targets(id) on delete restrict,
    allowed_origins text[] not null default '{}',
    time_group_id uuid references time_groups(id) on delete set null,
    offhours_mode text not null default 'schedule' check (offhours_mode in ('reject', 'schedule')),
    max_attempts int not null default 2 check (max_attempts between 1 and 5),
    retry_interval_s int not null default 120 check (retry_interval_s between 60 and 1800),
    callerid_prefix text,
    allow_international boolean not null default false,
    appearance jsonb not null default '{}'::jsonb,
    enabled boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table callback_requests (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references tenants(id) on delete cascade,
    widget_id uuid not null references callback_widgets(id) on delete cascade,
    phone text not null,
    name text,
    page_url text,
    ip inet,
    status text not null default 'pending'
        check (status in ('pending', 'dialing', 'connected', 'failed', 'rejected', 'cancelled')),
    attempts int not null default 0,
    next_attempt_at timestamptz,
    linkedid text,
    last_error text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index on callback_requests (tenant_id, created_at desc);
create index on callback_requests (status, next_attempt_at);

-- -------------------------------------------------------------- A2: o'tkazib yuborilgan qo'ng'iroq
create table missed_call_rules (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references tenants(id) on delete cascade,
    name text not null,
    scope_kind text not null check (scope_kind in ('any', 'did', 'queue', 'ring_group', 'extension')),
    scope_value text,
    telegram_chat_ids text[] not null default '{}',
    emails text[] not null default '{}',
    include_internal boolean not null default false,
    enabled boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table missed_call_notices (
    id bigserial primary key,
    tenant_id uuid not null references tenants(id) on delete cascade,
    rule_id uuid not null references missed_call_rules(id) on delete cascade,
    call_id text not null,
    status text not null check (status in ('sent', 'failed')),
    attempts int not null default 0,
    last_error text,
    created_at timestamptz not null default now(),
    sent_at timestamptz,
    unique (rule_id, call_id)
);

create table missed_notify_cursor (
    tenant_id uuid primary key references tenants(id) on delete cascade,
    last_seq bigint not null default 0
);

-- -------------------------------------------------------------- A3: Yandex SpeechKit TTS
create table tts_settings (
    tenant_id uuid primary key references tenants(id) on delete cascade,
    provider text not null default 'none' check (provider in ('none', 'yandex')),
    api_key_enc text,
    folder_id text,
    voices jsonb not null default '{"uz": "nigora", "ru": "alena", "en": "john"}'::jsonb,
    updated_at timestamptz not null default now()
);
