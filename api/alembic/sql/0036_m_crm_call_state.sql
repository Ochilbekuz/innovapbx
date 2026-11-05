-- M-CRM §2: `crm_call_links` holat ustunlari — `finish`/`attachRecord`
-- idempotentligi (dispetcher qayta urinishi `finish`ni TAKRORLAMASIN).
alter table crm_call_links add column if not exists finished_at timestamptz;
alter table crm_call_links add column if not exists record_attached boolean not null default false;
