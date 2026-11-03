-- M10 Bo'lak B: Sifat baholash (QA), 2FA (TOTP) va tashqi WS hodisalar (events:read scope).
-- m10-onlinepbx-contract.md Bo'lak B1/B2/B3.

-- ---- B1: Sifat baholash ------------------------------------------------
create table qa_checklists (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references tenants(id) on delete cascade,
    name text not null,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (tenant_id, name)
);

create table qa_criteria (
    id uuid primary key default gen_random_uuid(),
    checklist_id uuid not null references qa_checklists(id) on delete cascade,
    label text not null,
    kind text not null check (kind in ('yesno', 'scale5')),
    weight double precision not null default 1.0 check (weight > 0),
    critical boolean not null default false,
    position integer not null default 0
);

create table qa_evaluations (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references tenants(id) on delete cascade,
    checklist_id uuid not null references qa_checklists(id) on delete restrict,
    call_id text not null,
    extension_id uuid references extensions(id) on delete set null,
    evaluator_id uuid references users(id) on delete set null,
    answers jsonb not null default '{}'::jsonb,
    comment text,
    score_pct double precision not null default 0.0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index ix_qa_evaluations_tenant_call on qa_evaluations (tenant_id, call_id);

-- ---- B2: 2FA (TOTP) -----------------------------------------------------
alter table users add column totp_enabled_at timestamptz;
alter table users add column totp_recovery_hashes text[] not null default '{}';
alter table users add column totp_last_step bigint;

alter table system_settings add column require_2fa text not null default 'off';
alter table system_settings add constraint system_settings_require_2fa_check
    check (require_2fa in ('off', 'admins', 'all'));

create table totp_challenges (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id) on delete cascade,
    token_hash text not null unique,
    attempts integer not null default 0,
    created_at timestamptz not null default now(),
    expires_at timestamptz not null
);

-- ---- B3: tashqi WebSocket hodisalar (api_keys.scopes — Python tomonida
-- `app/services/api_keys.py::SCOPES`ga "events:read" qo'shiladi; bu yerda
-- DB sxemasiga o'zgarish kerak emas, `scopes` allaqachon text[] erkin ro'yxat).
