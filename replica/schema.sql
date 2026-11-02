-- Innova PBX — 0001 boshlang'ich sxema (PostgreSQL 16)
-- Manba: replica/recon.md (ma'lumotlar modeli), replica/architecture.md (qarorlar).
-- Qoidalar: hamma vaqt timestamptz (UTC); har bir egalik qilinadigan qatorda tenant_id;
-- FK'larning on delete qoidasi ATAYLAB tanlangan; holatlar — CHECK; ruxsat — API ma'lumot qatlamida
-- (har so'rovda tenant_id filtri; RLS emas, chunki Asterisk realtime ham shu bazani o'qiydi).

create extension if not exists pgcrypto;
create extension if not exists citext;

create or replace function touch_updated_at() returns trigger language plpgsql as $$
begin new.updated_at := now(); return new; end $$;

-- ───────────────────────── Ijarachi, adminlar, audit ─────────────────────────
create table tenants (
  id uuid primary key default gen_random_uuid(),
  code text not null unique check (code ~ '^[a-z][a-z0-9]{1,15}$'),   -- Asterisk context prefiksi
  name text not null,
  timezone text not null default 'Asia/Tashkent',
  language text not null default 'uz' check (language in ('uz','ru','en')),
  status text not null default 'active' check (status in ('active','suspended')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table roles (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null,
  permissions text[] not null default '{}',
  is_system boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, name)
);

create table users (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  username citext not null,
  full_name text not null,
  email citext,
  password_hash text not null,
  totp_secret_enc text,                       -- shifrlangan (core/crypto)
  role_id uuid not null references roles(id) on delete restrict,
  extension_id uuid,                          -- operator portali uchun (FK pastda)
  is_active boolean not null default true,
  must_change_password boolean not null default true,
  failed_logins int not null default 0,
  locked_until timestamptz,
  last_login_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, username)
);
create index on users (role_id);

create table refresh_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  token_hash text not null unique,
  expires_at timestamptz not null,
  revoked_at timestamptz,
  created_at timestamptz not null default now()
);
create index on refresh_tokens (user_id);

create table audit_log (
  id bigint generated always as identity primary key,
  tenant_id uuid not null references tenants(id) on delete cascade,
  user_id uuid references users(id) on delete set null,
  action text not null,                       -- 'extension.update' ...
  entity text not null,
  entity_id uuid,
  diff jsonb not null default '{}',           -- parollar hech qachon yozilmaydi
  ip inet,
  created_at timestamptz not null default now()
);
create index on audit_log (tenant_id, created_at desc);
create index on audit_log (entity, entity_id);

-- ───────────────────────── Manzillar grafigi ─────────────────────────
-- Har bir «qo'ng'iroq borishi mumkin bo'lgan» obyekt — call_targets'da bitta qator.
-- Obyekt jadvali target_id orqali bog'lanadi (on delete cascade), «manzil» ustunlari esa
-- call_targets(id) ga ON DELETE RESTRICT: ishlatilayotgan obyektni o'chirib bo'lmaydi →
-- singan manzil (FreePBX'ning mashhur muammosi) baza darajasida imkonsiz.
create table call_targets (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  kind text not null check (kind in ('extension','ring_group','queue','ivr','time_condition',
        'announcement','voicemail','conference','external','hangup','busy','feature')),
  label text not null,                        -- UI va xato xabarlari uchun («IVR: Asosiy menyu»)
  created_at timestamptz not null default now(),
  unique (id, tenant_id)
);
create index on call_targets (tenant_id, kind);

-- Terish raqamlari bitta nom maydonida: ichki raqam 101 va navbat 101 bir vaqtda bo'lolmaydi.
create table dial_numbers (
  tenant_id uuid not null references tenants(id) on delete cascade,
  number text not null check (number ~ '^[0-9*#]{2,10}$'),
  target_id uuid not null references call_targets(id) on delete cascade,
  primary key (tenant_id, number)
);
create index on dial_numbers (target_id);

-- ───────────────────────── Audio ─────────────────────────
create table audio_files (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null,
  language text not null default 'uz' check (language in ('uz','ru','en')),
  source text not null check (source in ('upload','browser','tts','system')),
  tts_text text,
  storage_path text not null,                 -- sounds/<tenant>/<id> (kengaytmasiz — Asterisk formati)
  duration_ms int not null check (duration_ms > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, name)
);

create table moh_classes (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null check (name ~ '^[a-z0-9_-]{1,32}$'),
  shuffle boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, name)
);

create table moh_class_files (
  moh_class_id uuid not null references moh_classes(id) on delete cascade,
  audio_file_id uuid not null references audio_files(id) on delete restrict,
  position int not null,
  primary key (moh_class_id, audio_file_id)
);
create index on moh_class_files (audio_file_id);

-- ───────────────────────── Ichki raqamlar va qurilmalar ─────────────────────────
create table extensions (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  target_id uuid not null unique references call_targets(id) on delete cascade,
  number text not null,
  name text not null,
  email citext,
  callerid_name text,
  outbound_callerid text,                     -- tashqi CallerID (trunk ruxsat bersa)
  sip_password_enc text not null,             -- shifrlangan; realtime view'da ochiladi (pastda izoh)
  max_contacts int not null default 3 check (max_contacts between 1 and 10),
  codecs text[] not null default '{ulaw,alaw,g722,opus}',
  webrtc boolean not null default false,
  recording text not null default 'always' check (recording in ('always','never','on_demand')),
  ring_seconds int not null default 25 check (ring_seconds between 5 and 120),
  dnd boolean not null default false,
  forward_always text check (forward_always ~ '^\+?[0-9]{2,15}$'),
  forward_busy text check (forward_busy ~ '^\+?[0-9]{2,15}$'),
  -- javob bo'lmasa: ovozli pochta / Follow Me / boshqa manzil
  no_answer_target_id uuid references call_targets(id) on delete restrict,
  follow_me jsonb not null default '{"enabled":false,"numbers":[],"ring_seconds":20}',
  outbound_allowed boolean not null default true,
  department text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, number)
);
create index on extensions (no_answer_target_id);
alter table users add constraint users_extension_fk
  foreign key (extension_id) references extensions(id) on delete set null;
create index on users (extension_id);

create table voicemail_boxes (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  target_id uuid not null unique references call_targets(id) on delete cascade,
  extension_id uuid unique references extensions(id) on delete cascade,  -- null = umumiy quti
  mailbox text not null,
  pin_hash text not null,
  email_notify boolean not null default true,
  telegram_notify boolean not null default false,
  attach_audio boolean not null default true,
  greeting_audio_id uuid references audio_files(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, mailbox)
);

create table devices (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  extension_id uuid not null references extensions(id) on delete cascade,
  kind text not null check (kind in ('ip_phone','softphone','webrtc','mobile')),
  vendor text check (vendor in ('yealink','grandstream','fanvil','other')),
  model text,
  mac macaddr,
  provisioned_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, mac)
);
create index on devices (extension_id);

-- ───────────────────────── Trunklar ─────────────────────────
create table trunks (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null,
  auth_mode text not null check (auth_mode in ('register','ip')),
  host text not null,
  port int not null default 5060 check (port between 1 and 65535),
  transport text not null default 'udp' check (transport in ('udp','tcp','tls')),
  username text,
  password_enc text,
  from_domain text,
  match_ips cidr[] not null default '{}',     -- ip rejimida kiruvchi qo'ng'iroqni tanish
  codecs text[] not null default '{alaw,ulaw}',
  max_channels int check (max_channels > 0),
  outbound_callerid text,
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, name),
  constraint register_needs_credentials check (auth_mode = 'ip' or (username is not null and password_enc is not null)),
  constraint ip_needs_match check (auth_mode = 'register' or cardinality(match_ips) > 0)
);

-- Sog'lik — fon tekshiruvi yozadi (registratsiya holati, OPTIONS qualify, oxirgi qo'ng'iroq).
-- IP-trunk sog'ligi registratsiya bilan O'LCHANMAYDI (arxiv saboq'i).
create table trunk_health (
  trunk_id uuid primary key references trunks(id) on delete cascade,
  state text not null check (state in ('ok','degraded','down','unknown')),
  registration text check (registration in ('registered','rejected','timeout','not_required')),
  qualify_rtt_ms int,
  last_inbound_at timestamptz,
  last_outbound_ok_at timestamptz,
  reason text,
  checked_at timestamptz not null default now()
);

-- ───────────────────────── Ish vaqti ─────────────────────────
create table time_groups (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, name)
);

create table time_ranges (
  id uuid primary key default gen_random_uuid(),
  time_group_id uuid not null references time_groups(id) on delete cascade,
  weekdays smallint[] not null check (weekdays <@ array[1,2,3,4,5,6,7]::smallint[] and cardinality(weekdays) > 0),
  start_time time not null,
  end_time time not null,
  constraint range_order check (end_time > start_time)
);
create index on time_ranges (time_group_id);

create table holidays (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null,
  day date not null,
  recurring_yearly boolean not null default false,  -- Navro'z: har yil 21-mart
  unique (tenant_id, day)
);

create table time_conditions (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  target_id uuid not null unique references call_targets(id) on delete cascade,
  name text not null,
  time_group_id uuid not null references time_groups(id) on delete restrict,
  honor_holidays boolean not null default true,
  open_target_id uuid not null references call_targets(id) on delete restrict,
  closed_target_id uuid not null references call_targets(id) on delete restrict,
  override text not null default 'auto' check (override in ('auto','force_open','force_closed')),
  toggle_code text check (toggle_code ~ '^\*[0-9]{2,4}$'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, name)
);
create index on time_conditions (time_group_id);
create index on time_conditions (open_target_id);
create index on time_conditions (closed_target_id);

-- ───────────────────────── IVR, e'lon, guruh, navbat, konferensiya, tashqi ─────────────────────────
create table announcements (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  target_id uuid not null unique references call_targets(id) on delete cascade,
  name text not null,
  audio_file_id uuid not null references audio_files(id) on delete restrict,
  next_target_id uuid not null references call_targets(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index on announcements (audio_file_id);
create index on announcements (next_target_id);

create table ivrs (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  target_id uuid not null unique references call_targets(id) on delete cascade,
  name text not null,
  greeting_audio_id uuid not null references audio_files(id) on delete restrict,
  invalid_audio_id uuid references audio_files(id) on delete restrict,
  timeout_seconds int not null default 7 check (timeout_seconds between 1 and 60),
  repeats int not null default 2 check (repeats between 0 and 5),
  direct_dial boolean not null default false,
  timeout_target_id uuid not null references call_targets(id) on delete restrict,
  invalid_target_id uuid not null references call_targets(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, name)
);
create index on ivrs (greeting_audio_id);
create index on ivrs (timeout_target_id);
create index on ivrs (invalid_target_id);

create table ivr_options (
  ivr_id uuid not null references ivrs(id) on delete cascade,
  digit text not null check (digit ~ '^[0-9*#]$'),
  target_id uuid not null references call_targets(id) on delete restrict,
  primary key (ivr_id, digit)
);
create index on ivr_options (target_id);

create table ring_groups (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  target_id uuid not null unique references call_targets(id) on delete cascade,
  name text not null,
  strategy text not null default 'ringall' check (strategy in ('ringall','hunt','memoryhunt')),
  ring_seconds int not null default 20 check (ring_seconds between 5 and 300),
  no_answer_target_id uuid not null references call_targets(id) on delete restrict,
  callerid_prefix text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index on ring_groups (no_answer_target_id);

create table ring_group_members (
  ring_group_id uuid not null references ring_groups(id) on delete cascade,
  position int not null,
  extension_id uuid references extensions(id) on delete cascade,
  external_number text check (external_number ~ '^\+?[0-9]{3,15}$'),
  primary key (ring_group_id, position),
  constraint one_member_kind check ((extension_id is null) <> (external_number is null))
);
create index on ring_group_members (extension_id);

create table queues (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  target_id uuid not null unique references call_targets(id) on delete cascade,
  name text not null,
  strategy text not null default 'rrmemory'
    check (strategy in ('ringall','leastrecent','fewestcalls','random','rrmemory','linear','wrandom')),
  moh_class_id uuid references moh_classes(id) on delete set null,
  agent_ring_seconds int not null default 15 check (agent_ring_seconds between 5 and 120),
  retry_seconds int not null default 5,
  wrapup_seconds int not null default 0 check (wrapup_seconds >= 0),
  max_wait_seconds int not null default 300 check (max_wait_seconds > 0),
  max_callers int check (max_callers > 0),
  announce_position boolean not null default true,
  announce_frequency_seconds int not null default 60,
  sla_seconds int not null default 20,
  join_empty boolean not null default false,
  record boolean not null default true,
  timeout_target_id uuid not null references call_targets(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, name)
);
create index on queues (timeout_target_id);
create index on queues (moh_class_id);

create table queue_members (                  -- statik a'zolar; dinamik login/logout — Asterisk (astdb)
  queue_id uuid not null references queues(id) on delete cascade,
  extension_id uuid not null references extensions(id) on delete cascade,
  penalty int not null default 0 check (penalty between 0 and 10),
  primary key (queue_id, extension_id)
);
create index on queue_members (extension_id);

create table conferences (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  target_id uuid not null unique references call_targets(id) on delete cascade,
  name text not null,
  pin_hash text,
  admin_pin_hash text,
  record boolean not null default false,
  max_members int check (max_members > 1),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table external_numbers (               -- manzil sifatida tashqi raqam (masalan, direktor mobili)
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  target_id uuid not null unique references call_targets(id) on delete cascade,
  number text not null check (number ~ '^\+?[0-9]{3,15}$'),
  label text not null
);

-- ───────────────────────── Marshrutlar ─────────────────────────
create table inbound_routes (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null,
  did text not null default '',               -- '' = hamma DID (catch-all)
  callerid_pattern text not null default '',  -- '' = har qanday
  target_id uuid not null references call_targets(id) on delete restrict,
  callerid_name_prefix text,
  record_override text check (record_override in ('always','never')),
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, did, callerid_pattern)   -- bir xil kirish uchun ikki marshrut — imkonsiz
);
create index on inbound_routes (target_id);

create table outbound_routes (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null,
  priority int not null,                      -- kichik = birinchi tekshiriladi
  callerid text,
  override_extension_callerid boolean not null default false,
  pin_hash text,
  international boolean not null default false,  -- toll fraud: xalqaro marshrut alohida belgilanadi
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, name),
  unique (tenant_id, priority) deferrable initially deferred  -- drag-drop qayta tartiblash bitta tranzaksiyada
);

create table outbound_route_patterns (
  id uuid primary key default gen_random_uuid(),
  route_id uuid not null references outbound_routes(id) on delete cascade,
  strip_prefix text not null default '',      -- '9' terib chiqish
  pattern text not null check (pattern ~ '^[0-9XZN.\[\]*#+-]+$'),  -- Asterisk naqshi
  add_prefix text not null default '',
  callerid_match text not null default ''
);
create index on outbound_route_patterns (route_id);

create table outbound_route_trunks (
  route_id uuid not null references outbound_routes(id) on delete cascade,
  trunk_id uuid not null references trunks(id) on delete restrict,
  position int not null,
  primary key (route_id, position),
  unique (route_id, trunk_id)
);
create index on outbound_route_trunks (trunk_id);

create table extension_outbound_routes (       -- extensions.outbound_allowed=true bo'lsa ham, ro'yxat bo'sh = hammasi
  extension_id uuid not null references extensions(id) on delete cascade,
  route_id uuid not null references outbound_routes(id) on delete cascade,
  primary key (extension_id, route_id)
);
create index on extension_outbound_routes (route_id);

-- ───────────────────────── Qo'shimcha ─────────────────────────
create table feature_codes (
  tenant_id uuid not null references tenants(id) on delete cascade,
  feature text not null check (feature in ('voicemail','voicemail_other','dnd_toggle','cf_always_on','cf_always_off',
        'pickup_group','pickup_direct','park','queue_login','queue_logout','queue_pause','call_flow_toggle',
        'echo_test','speaking_clock','record_now')),
  code text not null check (code ~ '^\*[0-9*#]{1,6}$'),
  enabled boolean not null default true,
  primary key (tenant_id, feature),
  unique (tenant_id, code)
);

create table blacklist (
  tenant_id uuid not null references tenants(id) on delete cascade,
  number text not null,                       -- 'anonymous' = yashirin raqam
  reason text,
  created_at timestamptz not null default now(),
  primary key (tenant_id, number)
);

create table system_settings (                -- tenant bo'yicha bitta qator; tez-tez o'zgarmaydi
  tenant_id uuid primary key references tenants(id) on delete cascade,
  external_ip inet,
  external_host text,
  local_nets cidr[] not null default '{10.0.0.0/8,172.16.0.0/12,192.168.0.0/16}',
  sip_udp_port int not null default 5060,
  sip_tls_port int not null default 5061,
  rtp_start int not null default 10000,
  rtp_end int not null default 20000,
  recording_retention_days int not null default 365 check (recording_retention_days between 7 and 3650),
  toll_fraud jsonb not null default '{"max_concurrent_outbound":10,"max_international_per_hour":0,"night_alert":true}',
  telegram jsonb not null default '{}',       -- bot token shifrlangan holda
  updated_at timestamptz not null default now(),
  constraint rtp_order check (rtp_end > rtp_start)
);

-- ───────────────────────── Konfiguratsiya reviziyalari ─────────────────────────
-- Har «saqlash» → kompilyator yangi dialplan chiqaradi; xato bo'lsa oldingi reviziyaga qaytiladi.
create table config_revisions (
  id bigint generated always as identity primary key,
  tenant_id uuid not null references tenants(id) on delete cascade,
  user_id uuid references users(id) on delete set null,
  status text not null check (status in ('compiled','applied','failed','rolled_back')),
  dialplan_sha256 text not null,
  dialplan text not null,
  error text,
  created_at timestamptz not null default now()
);
create index on config_revisions (tenant_id, id desc);

create table backups (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  target text not null check (target in ('local','s3','sftp')),
  status text not null check (status in ('running','ok','failed')),
  size_bytes bigint,
  path text,
  error text,
  started_at timestamptz not null default now(),
  finished_at timestamptz
);
create index on backups (tenant_id, started_at desc);

-- ───────────────────────── Asterisk yozadigan jadvallar (CDR/CEL/queue_log) ─────────────────────────
-- Ustun nomlari Asterisk cdr_pgsql/cel_pgsql/realtime queue_log talabiga mos (o'zgartirmang).
-- MUHIM (sinovda topilgan): `id` SHART bigserial (klassik nextval() default),
-- `generated always as identity` EMAS. Sabab: cdr_pgsql.so modul ustun
-- ro'yxatini `information_schema.columns.column_default`dan o'qiydi; u
-- Asterisk'ning o'zi tanimaydigan "id" ustuniga mos default topa olmasa,
-- INSERT'da "id" uchun bo'sh satr ('') yuboradi. PostgreSQL identity-ustunlar
-- uchun `column_default` har doim NULL qaytaradi (bigserial'dan farqli
-- o'laroq, u "nextval(...)" deb ko'rsatadi) — shu sababli identity bilan
-- har bir CDR yozishda "invalid input syntax for type bigint: ''" xatosi
-- bilan MUTLAQO ishlamay qoladi (end-to-end SIPp sinovida qo'lga tushirilgan).
create table cdr (
  id bigserial primary key,
  calldate timestamptz not null default now(),
  clid text, src text, dst text, dcontext text, channel text, dstchannel text,
  lastapp text, lastdata text,
  duration int not null default 0, billsec int not null default 0,
  disposition text, amaflags int, accountcode text, uniqueid text not null, linkedid text,
  userfield text, peeraccount text, sequence int,
  recordingfile text                          -- dialplan CDR(recordingfile) ga yozadi
);
create index on cdr (calldate);
create index on cdr (uniqueid);
create index on cdr (linkedid);
create index on cdr (accountcode, calldate);  -- accountcode = tenant code

-- cdr jadvalidagi xuddi shu sabab (yuqoridagi izohga qarang) tufayli bu yerda
-- ham bigserial ishlatiladi — kelajakda cel_pgsql/queue_log realtime yozuvi
-- yoqilsa, xuddi shu "identity -> column_default NULL" muammosiga tushmaslik
-- uchun.
create table cel (
  id bigserial primary key,
  eventtype text not null, eventtime timestamptz not null, cid_name text, cid_num text, cid_ani text,
  cid_rdnis text, cid_dnid text, exten text, context text, channame text, appname text, appdata text,
  amaflags int, accountcode text, peeraccount text, uniqueid text, linkedid text, userfield text,
  peer text, extra text
);
create index on cel (linkedid);
create index on cel (eventtime);

create table queue_log (
  id bigserial primary key,
  time timestamptz not null default now(),
  callid text, queuename text, agent text, event text,
  data text, data1 text, data2 text, data3 text, data4 text, data5 text
);
create index on queue_log (time);
create index on queue_log (callid);
create index on queue_log (queuename, time);

-- ───────────────────────── Asterisk realtime VIEW'lari ─────────────────────────
-- Asterisk (res_config_pgsql, sorcery realtime) faqat O'QIYDI. Normallashgan jadvallar → Asterisk
-- kutgan shakl. Natija: ichki raqam/trunk o'zgarishi reload'siz darhol kuchga kiradi.
-- Parollar: realtime ochiq parol talab qiladi → view sip_secret() orqali deshifrlaydi; kalit faqat
-- Asterisk ulanadigan rolning sessiya sozlamasida (`innova.key`), view'ga faqat shu rol SELECT oladi.
create or replace function sip_secret(enc text) returns text language sql stable as $$
  select pgp_sym_decrypt(decode(enc, 'base64'), current_setting('innova.key'))
$$;

-- `mailboxes` ataylab NULL: M0'da ovozli pochta (voicemail) yo'q (app_voicemail
-- konfiguratsiyasi/jadvali kontraktda yo'q). Agar bu yerga raqam qo'yilsa,
-- Asterisk ro'yxatdan o'tgan contact'ga MWI NOTIFY yuborishga urinadi — bu
-- SIPp UAS proof-testida (bir martalik `-m 1` chaqiruv) kutilmagan birinchi
-- so'rov bo'lib, haqiqiy INVITE'dan OLDIN kelib testni "Unexpected"/muvaffaqiyatsiz
-- qiladi (sinovda topilgan). Voicemail M0'dan keyingi bosqich.
create view ps_endpoints as
  select t.code || '-' || e.number as id, 'transport-' || case when e.webrtc then 'wss' else 'udp' end as transport,
         t.code || '-' || e.number as aors, t.code || '-' || e.number as auth,
         t.code || '-from-internal' as context, 'all' as disallow, array_to_string(e.codecs, ',') as allow,
         'no' as direct_media, 'yes' as rtp_symmetric, 'yes' as force_rport,
         'yes' as rewrite_contact,
         '"' || coalesce(e.callerid_name, e.name) || '" <' || e.number || '>' as callerid,
         t.code as accountcode, null::text as mailboxes,
         case when e.webrtc then 'yes' else 'no' end as webrtc
  from extensions e join tenants t on t.id = e.tenant_id where t.status = 'active'
  union all
  select t.code || '-trunk-' || tr.id::text, 'transport-' || tr.transport, t.code || '-trunk-' || tr.id::text,
         case when tr.auth_mode = 'register' then t.code || '-trunk-' || tr.id::text end,
         t.code || '-from-trunk', 'all', array_to_string(tr.codecs, ','), 'no', 'yes', 'yes', 'no',
         null, t.code, null, 'no'
  from trunks tr join tenants t on t.id = tr.tenant_id where tr.enabled and t.status = 'active';

-- DIQQAT (sinovda topilgan, M0 kontraktdan chetlanish — build-log.md'ga qarang,
-- "REGISTER digest auth: username/realm/identify" bo'limi):
-- 1) `username` SOF raqam ("101") EMAS, to'liq endpoint id ("t1-101"). Sabab:
--    Asterisk'ning `res_pjsip_endpoint_identifier_user` moduli standart
--    "username" strategiyasida REGISTER so'rovining FROM-foydalanuvchisini
--    sorcery ENDPOINT ID bilan solishtiradi — ko'p-tenant muhitida id tenant
--    kodi bilan prefikslangani uchun ("t1-101") bu hech qachon mos tushmaydi.
--    Haqiqiy yechim: `pjsip.conf [global] endpoint_identifier_order`'ga
--    `auth_username` qo'shish (`ip,auth_username,anonymous`) — bu strategiya
--    Authorization sarlavhasidagi DIGEST username orqali `ps_auths`'dan auth
--    obyektini topadi, so'ng unga bog'langan endpoint'ni aniqlaydi. Shu metod
--    ps_auths.username QIYMATI bilan solishtiradi — shu sabab u ham to'liq
--    id'ga tenglashtirildi (identifikatsiya VA digest hisob-kitobi bir xil
--    qiymatni ishlatishi kerak).
-- 2) `realm` ustuni SHART (bo'sh/NULL bo'lsa ham xato bermaydi, lekin bu
--    yerda aniq "asterisk" bilan to'ldirilgan) — chaqiriq (challenge)
--    e'lon qilgan realm bilan auth obyektidagi realm bir xil bo'lishi kerak,
--    aks holda HA1=MD5(username:realm:password) ikki tomonda FARQLI
--    hisoblanadi va parol to'g'ri bo'lsa ham "Failed to authenticate"
--    qaytadi (sinovda qo'lda SIP REGISTER yuborib aniqlangan).
-- Ikkisi birga PJSIP realtime orqali to'liq REGISTER+digest(qop=auth)
-- oqimini 200 OK bilan tasdiqladi (qo'lda yozilgan UDP skript, Asterisk
-- 22.10.1, andrius/asterisk:22).
create view ps_auths as
  select t.code || '-' || e.number as id, 'userpass' as auth_type, t.code || '-' || e.number as username,
         sip_secret(e.sip_password_enc) as password, 'asterisk' as realm
  from extensions e join tenants t on t.id = e.tenant_id
  union all
  select t.code || '-trunk-' || tr.id::text, 'userpass', tr.username, sip_secret(tr.password_enc), 'asterisk'
  from trunks tr join tenants t on t.id = tr.tenant_id where tr.auth_mode = 'register';

create view ps_aors as
  select t.code || '-' || e.number as id, e.max_contacts, 'yes' as remove_existing, 60 as qualify_frequency,
         null::text as contact
  from extensions e join tenants t on t.id = e.tenant_id
  union all
  select t.code || '-trunk-' || tr.id::text, 1, 'no', 30, 'sip:' || tr.host || ':' || tr.port
  from trunks tr join tenants t on t.id = tr.tenant_id;

create view ps_endpoint_id_ips as
  select t.code || '-trunk-' || tr.id::text || '-' || i.n as id, t.code || '-trunk-' || tr.id::text as endpoint,
         host(i.ip) || '/' || masklen(i.ip) as match
  from trunks tr join tenants t on t.id = tr.tenant_id
  cross join lateral unnest(tr.match_ips) with ordinality as i(ip, n)
  where tr.auth_mode = 'ip' and tr.enabled;

create view ps_registrations as
  select t.code || '-trunk-' || tr.id::text as id, 'transport-' || tr.transport as transport,
         'sip:' || tr.host || ':' || tr.port as server_uri,
         'sip:' || tr.username || '@' || coalesce(tr.from_domain, tr.host) as client_uri,
         t.code || '-trunk-' || tr.id::text as outbound_auth, 3600 as expiration, 60 as retry_interval,
         'yes' as line, t.code || '-trunk-' || tr.id::text as endpoint
  from trunks tr join tenants t on t.id = tr.tenant_id where tr.auth_mode = 'register' and tr.enabled;

create view asterisk_queues as               -- res_config: queues => pgsql,innova,asterisk_queues
  -- 0007: ustun `musicclass` (Asterisk app_queue realtime talab qiladigan nom — `musiconhold` EMAS,
  -- app/services/moh.py `asterisk_class_name()` bilan BIR XIL formula).
  select t.code || '-q-' || q.id::text as name, q.strategy,
         case when q.moh_class_id is null then 'default'
              else t.code || '-moh-' || q.moh_class_id::text end as musicclass,
         q.agent_ring_seconds as timeout, q.retry_seconds as retry, q.wrapup_seconds as wrapuptime,
         q.max_callers as maxlen, case when q.announce_position then 'yes' else 'no' end as announce_position,
         q.announce_frequency_seconds as announce_frequency, q.sla_seconds as servicelevel,
         case when q.join_empty then 'yes' else 'no' end as joinempty, 'no' as ringinuse
  from queues q join tenants t on t.id = q.tenant_id;

create view asterisk_queue_members as
  select t.code || '-q-' || q.id::text || '-' || e.number as uniqueid, t.code || '-q-' || q.id::text as queue_name,
         'PJSIP/' || t.code || '-' || e.number as interface, e.name as membername,
         'PJSIP/' || t.code || '-' || e.number as state_interface, qm.penalty, 0 as paused
  from queue_members qm join queues q on q.id = qm.queue_id
  join extensions e on e.id = qm.extension_id join tenants t on t.id = q.tenant_id;

-- updated_at triggerlari
do $$ declare r record; begin
  for r in select table_name from information_schema.columns
           where table_schema = 'public' and column_name = 'updated_at'
             and table_name in (select table_name from information_schema.tables
                                where table_schema='public' and table_type='BASE TABLE')
  loop
    execute format('create trigger %I before update on %I for each row execute function touch_updated_at()',
                   r.table_name || '_touch', r.table_name);
  end loop;
end $$;
