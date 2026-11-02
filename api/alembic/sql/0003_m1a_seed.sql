-- 0003 — M1a: har tenant uchun tizim manzillari `hangup`/`busy` (o'chirib
-- bo'lmaydi — API'da ularni o'chiradigan endpoint yo'q, faqat o'qish/foydalanish).
-- Yangi tenant yaratilganda (keyingi `POST /setup` chaqiruvlari) AVTOMATIK
-- qo'shiladi (trigger); allaqachon mavjud tenant(lar) uchun backfill (idempotent
-- — qayta ishga tushirilsa ham qo'shimcha qator yaratilmaydi).

create or replace function innova_seed_tenant_defaults() returns trigger as $$
begin
  insert into call_targets (tenant_id, kind, label)
  values (new.id, 'hangup', 'Qo''ng''iroqni tashlab yuborish');
  insert into call_targets (tenant_id, kind, label)
  values (new.id, 'busy', 'Band');
  return new;
end;
$$ language plpgsql;

drop trigger if exists tenants_seed_defaults on tenants;
create trigger tenants_seed_defaults
  after insert on tenants
  for each row execute function innova_seed_tenant_defaults();

insert into call_targets (tenant_id, kind, label)
select t.id, 'hangup', 'Qo''ng''iroqni tashlab yuborish' from tenants t
where not exists (select 1 from call_targets ct where ct.tenant_id = t.id and ct.kind = 'hangup');

insert into call_targets (tenant_id, kind, label)
select t.id, 'busy', 'Band' from tenants t
where not exists (select 1 from call_targets ct where ct.tenant_id = t.id and ct.kind = 'busy');

-- Navbat realtime — queues/queue_members (asterisk/etc-asterisk/extconfig.conf
-- bu view'larga ishora qiladi; view'lar 0001'da allaqachon yaratilgan).
