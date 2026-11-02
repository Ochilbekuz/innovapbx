-- M2b §0/§1: navbat agentlari — dinamik login/logout va pauza.
--
-- Yagona haqiqat manbai — `queue_members` jadvali (PostgreSQL). Telefon
-- (*45/*46) `Set(REALTIME(agent_state,...))` orqali yozadi — `asterisk_ext_state`
-- (0013) BILAN BIR XIL qolip: view + INSTEAD OF UPDATE trigger `queue_members`ni
-- cascada qiladi. Admin/portal — to'g'ridan-to'g'ri ORM UPDATE. Ikki yo'l ham
-- BIR XIL jadvalga tegadi, shu sabab bitta `BEFORE UPDATE` trigger (pastda)
-- manbadan qat'i nazar `agent_events`ga yozadi (manba — `innova.agent_event_source`
-- transaction-local GUC, sukut "phone": dialplan uni o'rnatmaydi, shu sabab
-- SOF *-kod yozuvlari avtomatik "phone" bo'lib qoladi).

alter table queue_members add column if not exists dynamic boolean not null default false;
alter table queue_members add column if not exists logged_in boolean not null default false;
alter table queue_members add column if not exists paused boolean not null default false;
alter table queue_members add column if not exists pause_reason text
  check (pause_reason is null or char_length(pause_reason) <= 64);
alter table queue_members add column if not exists state_at timestamptz not null default now();

create table if not exists agent_events (
  id bigserial primary key,
  tenant_id uuid not null references tenants(id) on delete cascade,
  extension_id uuid not null references extensions(id) on delete cascade,
  queue_id uuid references queues(id) on delete cascade,
  event text not null check (event in ('login', 'logout', 'pause', 'unpause')),
  reason text check (reason is null or char_length(reason) <= 64),
  source text not null check (source in ('phone', 'portal', 'admin')),
  at timestamptz not null default now()
);
create index if not exists agent_events_tenant_at_idx on agent_events (tenant_id, at);
create index if not exists agent_events_extension_at_idx on agent_events (extension_id, at);
create index if not exists agent_events_queue_at_idx on agent_events (queue_id, at);

-- Har `queue_members` UPDATE (manbadan qat'i nazar — view trigger KASKADI
-- ham, ORM to'g'ridan-to'g'ri yozuvi ham) -> `state_at` yangilanadi VA
-- logged_in/paused HAQIQATDA o'zgargan bo'lsa `agent_events`ga bir yozuv.
create or replace function queue_members_log_agent_event() returns trigger language plpgsql as $$
declare
  v_source text := coalesce(current_setting('innova.agent_event_source', true), 'phone');
  v_tenant_id uuid;
begin
  new.state_at := now();
  if old.logged_in is distinct from new.logged_in or old.paused is distinct from new.paused then
    select q.tenant_id into v_tenant_id from queues q where q.id = new.queue_id;
  end if;
  if old.logged_in is distinct from new.logged_in then
    insert into agent_events (tenant_id, extension_id, queue_id, event, reason, source)
      values (v_tenant_id, new.extension_id, new.queue_id,
              case when new.logged_in then 'login' else 'logout' end, null, v_source);
  end if;
  if old.paused is distinct from new.paused then
    insert into agent_events (tenant_id, extension_id, queue_id, event, reason, source)
      values (v_tenant_id, new.extension_id, new.queue_id,
              case when new.paused then 'pause' else 'unpause' end, new.pause_reason, v_source);
  end if;
  return new;
end $$;
drop trigger if exists queue_members_log_agent_event on queue_members;
create trigger queue_members_log_agent_event before update on queue_members
  for each row execute function queue_members_log_agent_event();

-- Realtime holat view'i (extconfig `agent_state`): kalit — `asterisk_ext_state`
-- bilan BIR XIL qolip ('<tenant_code>-<raqam>'). `logged_in` — FAQAT dinamik
-- a'zoliklar ustida o'qiladi/yoziladi (statik a'zo doim navbatda, login/logout
-- unga tegishli emas); `paused` — BARCHA a'zoliklarga (static ham, dynamic ham).
create or replace view asterisk_agent_state as
  select t.code || '-' || e.number as endpoint,
         coalesce(bool_or(qm.logged_in) filter (where qm.dynamic), false) as logged_in,
         coalesce(bool_or(qm.paused), false) as paused
  from extensions e
  join tenants t on t.id = e.tenant_id
  left join queue_members qm on qm.extension_id = e.id
  where t.status = 'active'
  group by t.code, e.number;

create or replace function asterisk_agent_state_update() returns trigger language plpgsql as $$
declare
  v_ext_id uuid;
begin
  select e.id into v_ext_id from extensions e join tenants t on t.id = e.tenant_id
   where t.code || '-' || e.number = old.endpoint;
  if v_ext_id is null then
    return new;
  end if;
  if new.logged_in is distinct from old.logged_in then
    update queue_members set logged_in = new.logged_in
     where extension_id = v_ext_id and dynamic;
  end if;
  if new.paused is distinct from old.paused then
    update queue_members set paused = new.paused,
           pause_reason = case when new.paused then pause_reason else null end
     where extension_id = v_ext_id;
  end if;
  return new;
end $$;
drop trigger if exists asterisk_agent_state_update on asterisk_agent_state;
create trigger asterisk_agent_state_update instead of update on asterisk_agent_state
  for each row execute function asterisk_agent_state_update();

-- `asterisk_queue_members` (0001) qayta ta'riflanadi: dinamik-lekin-kirmagan
-- a'zo Asterisk'ga UMUMAN ko'rinmaydi (realtime qator yo'q = a'zo yo'q —
-- Asterisk faqat Queue() kirishida qayta o'qiydi, M2b-contract.md §0/§1
-- tadqiqotda tasdiqlangan xulosa); `paused` endi haqiqiy ustundan + DND'dan.
-- MUHIM: PostgreSQL `CREATE OR REPLACE VIEW` mavjud ustunlarni o'chirish/
-- qayta nomlashga YO'L QO'YMAYDI (faqat oxiriga ustun qo'shish mumkin) —
-- shu sabab `reason_paused` (0005'dan beri bor, Asterisk realtime sxemasi
-- kutadi) saqlanib qolishi SHART; endi haqiqiy `qm.pause_reason`'dan to'ladi.
create or replace view asterisk_queue_members as
  select t.code || '-q-' || q.id::text || '-' || e.number as uniqueid,
         t.code || '-q-' || q.id::text as queue_name,
         'PJSIP/' || t.code || '-' || e.number as interface, e.name as membername,
         'PJSIP/' || t.code || '-' || e.number as state_interface, qm.penalty,
         case when qm.paused or e.dnd then 1 else 0 end as paused,
         coalesce(qm.pause_reason, '')::varchar(80) as reason_paused
  from queue_members qm join queues q on q.id = qm.queue_id
  join extensions e on e.id = qm.extension_id join tenants t on t.id = q.tenant_id
  where not qm.dynamic or qm.logged_in;

-- Xususiyat kodlari: *45 (navbat login/logout), *46 (pauza almashtirish) —
-- `feature_codes_feature_check` 0013'da ALLAQACHON ikkisini ham ruxsat etadi.
insert into feature_code_defaults (feature, code, position) values
  ('queue_login', '*45', 13), ('queue_pause', '*46', 14)
on conflict (feature) do nothing;

insert into feature_codes (tenant_id, feature, code, enabled)
  select t.id, d.feature, d.code, true from tenants t
  cross join feature_code_defaults d where d.feature in ('queue_login', 'queue_pause')
on conflict do nothing;
