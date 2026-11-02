-- M2a §4/§5: konferensiya (realtime a'zo soni AMI orqali, jadval allaqachon
-- 0001_schema.sql'da) va qora ro'yxat (realtime, reload/apply shart emas) +
-- oldingi agentdan qolgan 2 kamchilikni tuzatish.
--
-- Tuzatish (a): `forward_always`/`forward_busy` boshida "+" bo'lsa dialplan
-- `_X.` patterni mos kelmaydi. Mavjud qiymatlarni normalizatsiya (bo'shliq/-/()/+
-- olib tashlanadi — `app/services/number_normalize.py` BILAN BIR XIL qoida,
-- Python regexp `[^0-9]` ga teng) va CHECK'ni "+" ga ruxsat bermaydigan qilib qattiqlashtirish.
update extensions set forward_always = regexp_replace(forward_always, '[^0-9]', '', 'g')
  where forward_always is not null;
update extensions set forward_busy = regexp_replace(forward_busy, '[^0-9]', '', 'g')
  where forward_busy is not null;

alter table extensions drop constraint if exists extensions_forward_always_check;
alter table extensions add constraint extensions_forward_always_check
  check (forward_always ~ '^[0-9]{2,15}$');
alter table extensions drop constraint if exists extensions_forward_busy_check;
alter table extensions add constraint extensions_forward_busy_check
  check (forward_busy ~ '^[0-9]{2,15}$');

-- §5 Qora ro'yxat: raqam formati — 'anonymous' (yashirin/bo'sh CallerID) yoki
-- 3-15 ta raqam (xuddi shu `number_normalize.normalize_number()` natijasi).
alter table blacklist drop constraint if exists blacklist_number_check;
alter table blacklist add constraint blacklist_number_check
  check (number = 'anonymous' or number ~ '^[0-9]{3,15}$');

-- Realtime view — kiruvchi marshrutlashdan OLDIN tekshiriladi (API-yoz, Asterisk
-- faqat o'qiydi — trigger kerak emas, `asterisk_ext_state`dan farqli). Kalit —
-- `asterisk_ext_state` bilan BIR XIL qolip: '<tenant_code>-<raqam>'.
-- `coalesce(reason,'blocked')`: `reason` bazada NULL bo'lishi mumkin (ixtiyoriy) —
-- `REALTIME_FIELD()` bo'sh natijani "mos kelmadi" deb talqin qiladi, shu sabab
-- qator MAVJUD bo'lsa har doim bo'sh bo'lmagan qiymat qaytariladi (dialplan
-- `blacklist_check_lines()` shunga tayanadi). API/audit haqiqiy `reason`ni
-- (NULL bo'lsa ham) to'g'ridan-to'g'ri `blacklist` jadvalidan o'qiydi — bu
-- view FAQAT Asterisk uchun.
create or replace view asterisk_blacklist as
  select t.code || '-' || b.number as endpoint, coalesce(b.reason, 'blocked') as reason
  from blacklist b join tenants t on t.id = b.tenant_id where t.status = 'active';
