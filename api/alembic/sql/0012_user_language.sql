-- M1c §4: foydalanuvchi o'z interfeys tilini tanlaydi. NULL = tenant standarti.
alter table users add column if not exists language text check (language in ('uz','ru','en'));
