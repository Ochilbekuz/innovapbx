-- 0006 — M1b: `system_settings`ga global standart kodeklar (`codecs`) va
-- qayta ishga tushirish talab qilinganini saqlovchi `restart_required`
-- ustunlari (m1b-contract.md bo'lim 4: `PATCH /settings/sip` port/RTP/tarmoq
-- maydonlarini o'zgartirsa `restart_required=true` bo'ladi, `POST
-- /settings/sip/restart` muvaffaqiyatli bo'lgandan keyin `false`ga qaytadi
-- — bu holat requestlar orasida saqlanishi SHART, shu sabab ustun kerak).
--
-- Har tenant uchun o'chirib bo'lmaydigan `default` MOH sinfi (m1b-contract.md
-- bo'lim 8) — 0003'dagi `hangup`/`busy` target seed naqshi bilan BIR XIL
-- (trigger yangi tenant uchun, backfill mavjudlar uchun, idempotent).
alter table system_settings add column if not exists codecs text[] not null default array['alaw','ulaw','g722','opus'];
alter table system_settings add column if not exists restart_required boolean not null default false;

create or replace function innova_seed_tenant_moh() returns trigger as $$
begin
  insert into moh_classes (tenant_id, name, shuffle) values (new.id, 'default', false);
  return new;
end;
$$ language plpgsql;

drop trigger if exists tenants_seed_moh on tenants;
create trigger tenants_seed_moh
  after insert on tenants
  for each row execute function innova_seed_tenant_moh();

insert into moh_classes (tenant_id, name, shuffle)
select t.id, 'default', false from tenants t
where not exists (select 1 from moh_classes m where m.tenant_id = t.id and m.name = 'default');
