-- 0037 — Navbatlar (Queues): FreePBX Queues moduli bilan maksimal mos
-- keluvchi, lekin FAQAT Asterisk 22 `queues.conf`/`Queue()` orqali
-- HAQIQATDA ishlaydigan maydonlar (manba: asterisk/apps/app_queue.c
-- `queue_set_param()`/`init_queue()`, FreePBX admin/modules/queues PHP
-- manbasi — tafsilot `docs/qollanma/queues.md`).
--
-- Yangi ustunlarning SUKUT qiymati HOZIRGI ishlab chiqarish xatti-
-- harakatini O'ZGARTIRMAYDI:
--   * `skip_busy_agents` default TRUE -> pastdagi view'da `ringinuse='no'`
--     (ilgari `0007_moh_musicclass.sql`da QATTIQ yozilgan edi — aynan shu
--     qiymat, endi sozlanadigan bo'ldi).
--   * `announce_hold_time` default 'yes', `announce_position_limit` default
--     10, `min_announce_frequency_seconds` default 15 — bu ustunlar ILGARI
--     view'da umuman YO'Q edi, demak Asterisk o'zining ICHKI sukutini
--     ishlatgan (`init_queue()`: announceholdtime=ALWAYS, announcepositionlimit=10,
--     minannouncefrequency=15) — endi BIZ xuddi shu qiymatni aniq yozamiz.
--   * qolgan barcha yangi ustun (weight, autofill, reportholdtime,
--     memberdelay, penaltymemberslimit, autopause*, leavewhenempty,
--     periodic-announce*, context, mark-answered-elsewhere, Alert-Info,
--     CID prefiks, agent/join e'lon audio, MOH/ring-only rejimi) — Asterisk
--     sukuti bo'sh/"no"/0 bilan bir xil (yo'q bo'lgach ta'sir qilmaydi).
-- `join_empty`/`announce_position` — `bool`dan matn enumga (Asterisk
-- `parse_empty_options()`/`announce-position` to'liq qiymat to'plami)
-- KENGAYTIRILDI, eski True/False qiymat LOSSLESS 'yes'/'no'ga o'tkaziladi.
alter table queues
  add column if not exists skip_busy_agents boolean not null default true,
  add column if not exists weight integer not null default 0,
  add column if not exists autofill boolean not null default false,
  add column if not exists report_hold_time boolean not null default false,
  add column if not exists member_delay_seconds integer not null default 0,
  add column if not exists penalty_members_limit integer not null default 0,
  add column if not exists auto_pause text not null default 'no',
  add column if not exists auto_pause_delay_seconds integer not null default 0,
  add column if not exists auto_pause_busy boolean not null default false,
  add column if not exists auto_pause_unavail boolean not null default false,
  add column if not exists agent_timeout_restart boolean not null default false,
  add column if not exists max_wait_mode text not null default 'strict',
  add column if not exists leave_when_empty text not null default 'no',
  add column if not exists announce_position_limit integer not null default 10,
  add column if not exists announce_hold_time text not null default 'yes',
  add column if not exists min_announce_frequency_seconds integer not null default 15,
  add column if not exists periodic_announce_audio_file_id uuid references audio_files(id) on delete set null,
  add column if not exists periodic_announce_frequency_seconds integer not null default 60,
  add column if not exists ring_mode text not null default 'moh',
  add column if not exists mark_answered_elsewhere boolean not null default false,
  add column if not exists cid_name_prefix text,
  add column if not exists alert_info text,
  add column if not exists join_announcement_audio_file_id uuid references audio_files(id) on delete set null,
  add column if not exists agent_announcement_audio_file_id uuid references audio_files(id) on delete set null,
  add column if not exists breakout_target_id uuid references call_targets(id) on delete set null;

alter table queues alter column join_empty drop default;
alter table queues
  alter column join_empty type text using (case when join_empty then 'yes' else 'no' end);
alter table queues alter column join_empty set default 'no';

alter table queues alter column announce_position drop default;
alter table queues
  alter column announce_position type text using (case when announce_position then 'yes' else 'no' end);
alter table queues alter column announce_position set default 'yes';

-- `asterisk_queues` — faqat USTUN QO'SHISH (oxiriga) + mavjud ustunlarning
-- IFODASINI o'zgartirish ruxsat etilgan (`create or replace view`: nom/tur/
-- tartib o'zgarmaydi — 0007's izohiga qarang). `ringinuse`/`joinempty`/
-- `announce_position` ENDI sozlanadigan ustunlardan hisoblanadi (ilgari
-- qattiq 'no'/bool-case edi) — qiymatlari HOZIRGI sukut bilan bir xil.
create or replace view asterisk_queues as   -- res_config: queues => pgsql,innova,asterisk_queues
  select t.code || '-q-' || q.id::text as name, q.strategy,
         case when q.moh_class_id is null then 'default'
              else t.code || '-moh-' || q.moh_class_id::text end as musicclass,
         q.agent_ring_seconds as timeout, q.retry_seconds as retry, q.wrapup_seconds as wrapuptime,
         q.max_callers as maxlen, q.announce_position as announce_position,
         q.announce_frequency_seconds as announce_frequency, q.sla_seconds as servicelevel,
         q.join_empty as joinempty,
         case when q.skip_busy_agents then 'no' else 'yes' end as ringinuse,
         q.weight as weight,
         case when q.autofill then 'yes' else 'no' end as autofill,
         case when q.report_hold_time then 'yes' else 'no' end as reportholdtime,
         q.member_delay_seconds as memberdelay,
         q.penalty_members_limit as penaltymemberslimit,
         q.auto_pause as autopause,
         q.auto_pause_delay_seconds as autopausedelay,
         case when q.auto_pause_busy then 'yes' else 'no' end as autopausebusy,
         case when q.auto_pause_unavail then 'yes' else 'no' end as autopauseunavail,
         case when q.agent_timeout_restart then 'yes' else 'no' end as timeoutrestart,
         case when q.max_wait_mode = 'loose' then 'conf' else 'app' end as timeoutpriority,
         q.leave_when_empty as leavewhenempty,
         q.announce_position_limit as announce_position_limit,
         q.announce_hold_time as announce_holdtime,
         q.min_announce_frequency_seconds as min_announce_frequency,
         -- `periodic-announce`/`announce` queues.conf kalitlari ovoz fayli
         -- YO'LINI kutadi (`ast_streamfile()` mutlaq yo'lni ham qo'llaydi —
         -- xuddi IVR/e'lon audio uchun `compiler.py` qiladigani kabi).
         case when pa.id is null then null else '/var/lib/innova/' || pa.storage_path end as periodic_announce,
         case when pa.id is null then null else q.periodic_announce_frequency_seconds end as periodic_announce_frequency,
         case when q.breakout_target_id is null then null
              else t.code || '-dest-' || q.breakout_target_id::text end as context
  from queues q join tenants t on t.id = q.tenant_id
  left join audio_files pa on pa.id = q.periodic_announce_audio_file_id;
