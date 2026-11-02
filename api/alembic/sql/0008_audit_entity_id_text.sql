-- `audit_log.entity_id` UUID edi, lekin HAMMA entity turi UUID emas —
-- `config_revisions.id` bigint (masalan 461). `POST
-- /config/revisions/{id}/restore` har doim bu ustunga entity_id=str(461) ni
-- yozishga urinardi -> asyncpg DataError ("invalid UUID") -> 500 Internal
-- Server Error, ya'ni RESTORE FUNKSIYASI ISHLAB CHIQARISHDA UMUMAN ISHLAMAYDI
-- edi (m1b-proof.sh ssenariy 6 orqali topilgan, 2026-10-28). entity_id —
-- umumiy ma'nodagi "qaysi obyekt" izi, shuning uchun erkin matn (text)
-- bo'lishi kerak, qat'iy UUID emas.
alter table audit_log alter column entity_id type text;
