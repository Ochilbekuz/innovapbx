-- schema.sql tutun sinovi: asosiy cheklovlar haqiqatan ishlaydimi (har blok kutilgan xatoni tekshiradi)
\set ON_ERROR_STOP on
set innova.key = 'sinov-kaliti';
insert into tenants (id, code, name) values ('00000000-0000-0000-0000-000000000001', 'acme', 'Acme');

-- manzil: hangup + ichki raqam 101
insert into call_targets (id, tenant_id, kind, label) values
  ('00000000-0000-0000-0000-0000000000a1', '00000000-0000-0000-0000-000000000001', 'hangup', 'Osish'),
  ('00000000-0000-0000-0000-0000000000a2', '00000000-0000-0000-0000-000000000001', 'extension', '101 Ali');
insert into extensions (id, tenant_id, target_id, number, name, sip_password_enc) values
  ('00000000-0000-0000-0000-0000000000e1', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000a2',
   '101', 'Ali', encode(pgp_sym_encrypt('Parol-101', 'sinov-kaliti'), 'base64'));
insert into dial_numbers values ('00000000-0000-0000-0000-000000000001', '101', '00000000-0000-0000-0000-0000000000a2');
insert into inbound_routes (tenant_id, name, target_id) values
  ('00000000-0000-0000-0000-000000000001', 'Hammasi', '00000000-0000-0000-0000-0000000000a2');

-- 1) ishlatilayotgan manzilni o'chirib bo'lmaydi
do $$ begin
  delete from call_targets where id = '00000000-0000-0000-0000-0000000000a2';
  raise exception 'XATO: singan manzilga yo''l qo''yildi';
exception when foreign_key_violation then raise notice 'OK 1: ishlatilayotgan manzil o''chirilmadi';
end $$;

-- 2) terish raqami to'qnashuvi
do $$ begin
  insert into call_targets (id, tenant_id, kind, label) values
    ('00000000-0000-0000-0000-0000000000a3', '00000000-0000-0000-0000-000000000001', 'queue', 'Navbat');
  insert into dial_numbers values ('00000000-0000-0000-0000-000000000001', '101', '00000000-0000-0000-0000-0000000000a3');
  raise exception 'XATO: raqam to''qnashuvi o''tdi';
exception when unique_violation then raise notice 'OK 2: 101 raqami band';
end $$;

-- 3) ip-trunk match_ips siz — imkonsiz
do $$ begin
  insert into trunks (tenant_id, name, auth_mode, host) values ('00000000-0000-0000-0000-000000000001', 'UzT', 'ip', '1.2.3.4');
  raise exception 'XATO';
exception when check_violation then raise notice 'OK 3: ip-trunk match_ips talab qiladi';
end $$;

-- 4) realtime view'lar: ochiq parol faqat kalit bilan
insert into trunks (tenant_id, name, auth_mode, host, match_ips) values
  ('00000000-0000-0000-0000-000000000001', 'UzT', 'ip', '1.2.3.4', '{1.2.3.4/32}');
select id, context, allow, callerid from ps_endpoints order by id;
select id, username, password = 'Parol-101' as parol_togri from ps_auths;
select endpoint, match from ps_endpoint_id_ips;

-- 5) marshrut o'chirilgach manzilni o'chirish mumkin (cascade → extensions, dial_numbers)
delete from inbound_routes;
delete from call_targets where id = '00000000-0000-0000-0000-0000000000a2';
select count(*) as qolgan_ichki_raqam from extensions;
select count(*) as qolgan_raqam from dial_numbers;
