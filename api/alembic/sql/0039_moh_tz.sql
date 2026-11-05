-- 0039: "Asosiy qilish" (M MOH) — `moh_classes.is_default`. Tenant bo'yicha
-- ko'pi bilan BITTA `true` qator (qisman unique indeks). Backfill: oldin
-- UI'da faqat nomi "default" bo'lgan sinf "Asosiy" deb KO'RSATILARDI (haqiqiy
-- Asterisk bog'lanishi YO'Q edi) — shu nomdagilarni `is_default=true` qilib
-- belgilaymiz, shunda yangilangan serverda ko'rinish o'zgarmaydi va ular endi
-- HAQIQATAN HAM Asterisk'ning `[default]` MOH sinfiga aylanadi
-- (`app/services/moh.py::build_musiconhold_conf`).
alter table moh_classes add column if not exists is_default boolean not null default false;

update moh_classes set is_default = true where name = 'default';

create unique index if not exists ix_moh_classes_tenant_default
  on moh_classes (tenant_id) where is_default;
