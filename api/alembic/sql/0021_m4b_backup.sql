-- M4b: Zaxira nusxa va tiklash — replica/m4b-contract.md §1.

-- 1) `backups` (0001'dagi minimal shakl) — `target`/`path` endi `backup_copies`ga
-- ko'chadi (bitta zaxira bir nechta nishonga nusxalanishi mumkin).
alter table backups drop constraint if exists backups_target_check;
alter table backups drop constraint if exists backups_status_check;
alter table backups drop column if exists target;
alter table backups drop column if exists path;
alter table backups add column if not exists kind text;
update backups set kind = 'manual' where kind is null;
alter table backups alter column kind set not null;
alter table backups add column if not exists components text[] not null default array[]::text[];
alter table backups add column if not exists step text;
alter table backups add column if not exists progress smallint;
alter table backups add column if not exists file_name text;
alter table backups add column if not exists sha256 text;
alter table backups add column if not exists manifest jsonb;
alter table backups add column if not exists created_by uuid references users(id) on delete set null;
alter table backups add constraint backups_kind_check
  check (kind in ('scheduled', 'manual', 'pre_restore', 'uploaded'));
alter table backups add constraint backups_status_check
  check (status in ('running', 'ok', 'partial', 'failed'));
create index if not exists backups_tenant_kind_idx on backups (tenant_id, kind, started_at desc);

-- 2) `backup_copies` — har bir nishon (local/s3/sftp) uchun bitta qator.
create table if not exists backup_copies (
  id uuid primary key default gen_random_uuid(),
  backup_id uuid not null references backups(id) on delete cascade,
  target text not null check (target in ('local', 's3', 'sftp')),
  status text not null check (status in ('pending', 'ok', 'failed', 'deleted')),
  remote_path text,
  size_bytes bigint,
  error text,
  uploaded_at timestamptz
);
create unique index if not exists backup_copies_backup_target_uniq on backup_copies (backup_id, target);

-- 3) `restore_jobs` — tiklash jarayoni (inspect o'zgarish qoldirmaydi, shu sabab jadvalga yozilmaydi).
create table if not exists restore_jobs (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  backup_id uuid references backups(id) on delete set null,
  source text not null check (source in ('local', 'upload')),
  status text not null check (status in ('running', 'ok', 'failed')),
  step text,
  progress smallint,
  error text,
  force boolean not null default false,
  pre_restore_backup_id uuid references backups(id) on delete set null,
  started_by uuid references users(id) on delete set null,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  result jsonb
);
create index if not exists restore_jobs_tenant_idx on restore_jobs (tenant_id, started_at desc);

-- 4) `system_settings.backup` — passphrase (shifrlangan), jadval, nishonlar (§1).
alter table system_settings add column if not exists backup jsonb not null default jsonb_build_object(
  'passphrase_enc', null,
  'schedule', jsonb_build_object(
    'enabled', false, 'frequency', 'daily', 'weekday', 1, 'time', '03:00',
    'components', jsonb_build_array('config', 'history', 'sounds', 'voicemail', 'certs')),
  'targets', jsonb_build_object(
    'local', jsonb_build_object('keep_last', 7),
    's3', jsonb_build_object(
      'enabled', false, 'endpoint', '', 'region', '', 'bucket', '', 'prefix', '',
      'access_key', '', 'secret_key_enc', null, 'path_style', false, 'keep_last', 14),
    'sftp', jsonb_build_object(
      'enabled', false, 'host', '', 'port', 22, 'user', '', 'password_enc', null,
      'key_enc', null, 'folder', '/backups', 'host_key_fp', null, 'keep_last', 7)
  ),
  'last_scheduled_at', null,
  'last_scheduled_ok_at', null,
  'last_stale_alert_at', null
);

-- 5) Ogohlantirish turlari: jadval ishdan chiqdi / uzoq vaqt muvaffaqiyatli bo'lmadi (§0).
alter table alert_log drop constraint if exists alert_log_kind_check;
alter table alert_log add constraint alert_log_kind_check check (kind in (
  'ip_banned', 'toll_blocked', 'concurrent_limit', 'trunk_down', 'trunk_up', 'test',
  'webhook_disabled', 'recording_error', 'prov_bruteforce', 'backup_failed', 'backup_stale'));
