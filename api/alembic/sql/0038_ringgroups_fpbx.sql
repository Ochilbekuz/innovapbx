-- 0038: FreePBX Ring Groups moduli parity (hisobot: docs/qollanma/ringgroups.md).
-- Barcha yangi ustunlar SUKUT bo'yicha HOZIRGI xatti-harakatni saqlaydi
-- (kompilyator ularni faqat ANIQ sozlanganda qo'llaydi).

-- Strategiya: to'liq FreePBX ro'yxati (random — Queue strategiyasi, Ring Group'da
-- yo'q, shuning uchun qo'shilmagan; hisobotda ayt).
alter table ring_groups drop constraint if exists ring_groups_strategy_check;
alter table ring_groups add constraint ring_groups_strategy_check check (strategy in (
  'ringall', 'ringall-prim', 'hunt', 'hunt-prim',
  'memoryhunt', 'memoryhunt-prim', 'firstavailable', 'firstnotonphone'));

alter table ring_groups add column if not exists announcement_audio_id uuid
  references audio_files(id) on delete set null;

alter table ring_groups add column if not exists ring_strategy_sound text not null default 'ring';
alter table ring_groups drop constraint if exists ring_groups_ring_strategy_sound_check;
alter table ring_groups add constraint ring_groups_ring_strategy_sound_check
  check (ring_strategy_sound in ('ring', 'moh'));

alter table ring_groups add column if not exists moh_class_id uuid
  references moh_classes(id) on delete set null;

alter table ring_groups add column if not exists alert_info text;

alter table ring_groups add column if not exists skip_busy_agent boolean not null default false;
alter table ring_groups add column if not exists confirm_calls boolean not null default false;

alter table ring_groups add column if not exists remote_announce_audio_id uuid
  references audio_files(id) on delete set null;

alter table ring_groups add column if not exists recording_policy text not null default 'dontcare';
alter table ring_groups drop constraint if exists ring_groups_recording_policy_check;
alter table ring_groups add constraint ring_groups_recording_policy_check
  check (recording_policy in ('dontcare', 'force', 'no'));

create index if not exists ix_ring_groups_moh_class on ring_groups (moh_class_id);
