-- 1.0.4 §3: ovozli pochta bildirishnomasi KO'PI-BILAN-BIR-MARTA edi (claim alohida
-- `commit()` bilan yozilardi — yetkazish o'rtasida jarayon o'lsa qator `pending`da
-- abadiy qolib ketardi, chunki qayta urinish faqat `status='failed'` qatorni topardi).
-- Endi: claim+yetkazish+yakun BITTA tranzaksiyada (bitta `commit()`) — jarayon
-- o'lsa HAMMASI qaytariladi (rollback) va keyingi skanida qayta urinadi
-- (KAMIDA-BIR-MARTA). Qayta urinish jadvali `integrations`dagi outbox qolipi
-- bilan BIR XIL (`outbox.parse_schedule`/`transition`, `vm_notify_retry_schedule_s`).

alter table voicemail_notifications
  add column next_attempt_at timestamptz not null default now();

alter table voicemail_notifications drop constraint if exists voicemail_notifications_status_check;
alter table voicemail_notifications
  add constraint voicemail_notifications_status_check check (status in ('pending', 'sent', 'failed', 'dead'));

create index on voicemail_notifications (status, next_attempt_at);
