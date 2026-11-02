-- 0007 — M1b: `asterisk_queues` real xato tuzatildi — ustun `musiconhold`
-- deb nomlangan edi, lekin Asterisk app_queue realtime "static" jadvalida
-- qator KATEGORIYA emas, HAR BIR USTUN o'ZI queues.conf direktivasi nomi
-- bo'lishi SHART (voip-info.org/asterisk-realtime-queue: "musicclass" —
-- "musiconhold" EMAS). Shu sabab navbatga MOH sinfi biriktirilgan bo'lsa ham,
-- Asterisk uni HECH QACHON o'qimagan (ustun nomi mos kelmagani uchun jim
-- e'tiborsiz qolgan).
--
-- Qiymat ham o'zgartirildi: endi tenant kodi + MOH sinf ID'si asosida
-- (`t.code || '-moh-' || q.moh_class_id`) — bu `app/services/moh.py`
-- `asterisk_class_name()` BILAN AYNAN BIR XIL formula (ikkisi ham shu
-- formulaga ishora qiladi, biri o'zgarsa ikkinchisi albatta yangilansin).
-- `moh_class_id IS NULL` holati o'zgarmadi — tarixiy "default" (Asterisk
-- musiconhold.conf'da bunday sinf generatsiya qilinmaydi, demak klassik
-- "musiconhold.conf topilmadi" sukut holati — bu M0'dan beri bor edi).
-- Postgres `create or replace view` ustun NOMINI o'zgartirishga yo'l qo'ymaydi
-- ("cannot change name of view column... Use ALTER VIEW ... RENAME COLUMN")
-- — shu sabab `drop`+`create` (hech qanday boshqa SQL obyekt bu view'ga
-- bog'liq emas, faqat Asterisk tashqaridan extconfig.conf orqali o'qiydi).
drop view asterisk_queues;
create view asterisk_queues as               -- res_config: queues => pgsql,innova,asterisk_queues
  select t.code || '-q-' || q.id::text as name, q.strategy,
         case when q.moh_class_id is null then 'default'
              else t.code || '-moh-' || q.moh_class_id::text end as musicclass,
         q.agent_ring_seconds as timeout, q.retry_seconds as retry, q.wrapup_seconds as wrapuptime,
         q.max_callers as maxlen, case when q.announce_position then 'yes' else 'no' end as announce_position,
         q.announce_frequency_seconds as announce_frequency, q.sla_seconds as servicelevel,
         case when q.join_empty then 'yes' else 'no' end as joinempty, 'no' as ringinuse
  from queues q join tenants t on t.id = q.tenant_id;
