-- M5a: FreePBX'dan ko'chirish — replica/m5a-contract.md §2.

-- 1) `backups.kind` ga `pre_import` qo'shiladi (pre_restore kabi faqat lokal).
alter table backups drop constraint if exists backups_kind_check;
alter table backups add constraint backups_kind_check
  check (kind in ('scheduled', 'manual', 'pre_restore', 'uploaded', 'pre_import'));

-- 2) `migration_jobs` — bitta FreePBX ko'chirish ishi (yuklash yoki SSH orqali).
create table if not exists migration_jobs (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  source text not null check (source in ('upload', 'ssh')),
  status text not null check (status in (
    'uploaded', 'analyzing', 'analyzed', 'applying', 'ok', 'failed')),
  step text,
  progress smallint,
  bundle_path text,
  source_meta jsonb,
  plan jsonb,
  options jsonb not null default jsonb_build_object('rotate_weak_secrets', false),
  result jsonb,
  error jsonb,
  pre_import_backup_id uuid references backups(id) on delete set null,
  created_by uuid references users(id) on delete set null,
  created_at timestamptz not null default now(),
  finished_at timestamptz
);
create index if not exists migration_jobs_tenant_created_idx
  on migration_jobs (tenant_id, created_at desc);

-- 3) `migration_items` — har import qilingan (yoki import qilinishi mo'ljallangan)
-- obyektning kelib chiqishi — idempotentlik uchun (qayta import — "already_imported").
create table if not exists migration_items (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references migration_jobs(id) on delete cascade,
  tenant_id uuid not null references tenants(id) on delete cascade,
  kind text not null,
  source_ref text not null,
  innova_kind text,
  innova_id uuid,
  created_at timestamptz not null default now(),
  unique (tenant_id, kind, source_ref)
);
create index if not exists migration_items_job_idx on migration_items (job_id);
