-- Innova PBX — M1a: `asterisk_queue_members`ga `reason_paused` ustuni.
--
-- Sabab (sinovda topilgan): Asterisk 22'ning `res_config_pgsql`/`app_queue`
-- realtime a'zolar jadvali/view'ida ixtiyoriy `reason_paused varchar(80)`
-- ustunini kutadi (pauza sababini saqlash uchun, `PauseQueueMember` AMI/CLI
-- buyrug'ining `reason` argumenti). Ustun yo'q bo'lsa `res_config_pgsql`
-- ishga tushishda WARNING beradi: "Table asterisk_queue_members requires
-- a column 'reason_paused' of size '80', but no such column exists."
-- M1a kontraktida pauza sababi funksiyasi yo'q (faqat a'zo qo'shish/o'chirish),
-- shu sabab doimiy bo'sh qiymat kifoya — maqsad shu ogohlantirishni yo'qotish
-- va `app_queue`ning to'liq, xatosiz ishga tushishini ta'minlash.
create or replace view asterisk_queue_members as
  select t.code || '-q-' || q.id::text || '-' || e.number as uniqueid, t.code || '-q-' || q.id::text as queue_name,
         'PJSIP/' || t.code || '-' || e.number as interface, e.name as membername,
         'PJSIP/' || t.code || '-' || e.number as state_interface, qm.penalty, 0 as paused,
         ''::varchar(80) as reason_paused
  from queue_members qm join queues q on q.id = qm.queue_id
  join extensions e on e.id = qm.extension_id join tenants t on t.id = q.tenant_id;
