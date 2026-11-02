-- Innova PBX — M1c §2: ovozli pochta (S23).
--
-- 1) `voicemail_boxes` ga bildirishnoma manzillari: `email`, `telegram_chat_id`
--    (chat_id — butun son, guruh uchun manfiy, yoki ommaviy kanal `@nomi`).
-- 2) `notify_settings` — tenant bo'yicha bitta qator: SMTP + Telegram bot.
--    Parol/token `pgp_sym_encrypt` bilan shifrlangan (`crypto.encrypt_secret`),
--    API javobida hech qachon qaytarilmaydi (`has_*` bayroqlari).
-- 3) `voicemail_notifications` — yuborilgan (yoki urinilgan) bildirishnomalar.
--    `unique (box_id, msg_id, channel)` — bir xabar bir kanalga BIR MARTA
--    (API qayta ishga tushsa ham): fon vazifa avval qatorni «egallaydi»
--    (`insert ... on conflict do nothing`), keyin yuboradi. `msg_id` —
--    app_voicemail `msgNNNN.txt` dagi `msg_id` (INBOX -> Old ko'chganda ham
--    o'zgarmaydi, fayl raqami esa o'zgaradi).
-- 4) `ps_endpoints.mailboxes` — FAQAT qutisi bor ichki raqam uchun `<box>@<code>`
--    (MWI). Qutisiz raqamlar uchun NULL qoladi: aks holda Asterisk har
--    ro'yxatdan o'tgan contact'ga unsolicited MWI NOTIFY yuboradi va SIPp UAS
--    isbotlari (bir martalik `-m 1`) kutilmagan birinchi so'rovdan yiqiladi
--    (0001_schema.sql dagi izoh — M0 da topilgan). View'ning qolgan ustunlari
--    0004_dtmf_info.sql bilan AYNAN bir xil.
alter table voicemail_boxes
  add column email text check (email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
  add column telegram_chat_id text check (telegram_chat_id ~ '^(-?[0-9]{1,20}|@[A-Za-z0-9_]{5,32})$');
alter table voicemail_boxes add constraint voicemail_boxes_mailbox_check check (mailbox ~ '^[0-9]{2,10}$');
create index on voicemail_boxes (greeting_audio_id);

create table notify_settings (
  tenant_id uuid primary key references tenants(id) on delete cascade,
  smtp_host text,
  smtp_port int not null default 587 check (smtp_port between 1 and 65535),
  smtp_tls text not null default 'starttls' check (smtp_tls in ('none','starttls','tls')),
  smtp_user text,
  smtp_password_enc text,
  from_email text,
  telegram_token_enc text,
  telegram_api_base text not null default 'https://api.telegram.org' check (telegram_api_base ~ '^https?://'),
  updated_at timestamptz not null default now()
);
create trigger notify_settings_touch before update on notify_settings
  for each row execute function touch_updated_at();

create table voicemail_notifications (
  id bigserial primary key,
  tenant_id uuid not null references tenants(id) on delete cascade,
  box_id uuid not null references voicemail_boxes(id) on delete cascade,
  msg_id text not null,
  channel text not null check (channel in ('email','telegram')),
  status text not null default 'pending' check (status in ('pending','sent','failed')),
  attempts int not null default 0,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (box_id, msg_id, channel)
);
create index on voicemail_notifications (tenant_id, created_at);
create trigger voicemail_notifications_touch before update on voicemail_notifications
  for each row execute function touch_updated_at();

create or replace view ps_endpoints as
  select t.code || '-' || e.number as id, 'transport-' || case when e.webrtc then 'wss' else 'udp' end as transport,
         t.code || '-' || e.number as aors, t.code || '-' || e.number as auth,
         t.code || '-from-internal' as context, 'all' as disallow, array_to_string(e.codecs, ',') as allow,
         'no' as direct_media, 'yes' as rtp_symmetric, 'yes' as force_rport,
         'yes' as rewrite_contact,
         '"' || coalesce(e.callerid_name, e.name) || '" <' || e.number || '>' as callerid,
         t.code as accountcode,
         (select vb.mailbox || '@' || t.code from voicemail_boxes vb where vb.extension_id = e.id) as mailboxes,
         case when e.webrtc then 'yes' else 'no' end as webrtc,
         'info' as dtmf_mode
  from extensions e join tenants t on t.id = e.tenant_id where t.status = 'active'
  union all
  select t.code || '-trunk-' || tr.id::text, 'transport-' || tr.transport, t.code || '-trunk-' || tr.id::text,
         case when tr.auth_mode = 'register' then t.code || '-trunk-' || tr.id::text end,
         t.code || '-from-trunk', 'all', array_to_string(tr.codecs, ','), 'no', 'yes', 'yes', 'no',
         null, t.code, null, 'no', 'info'
  from trunks tr join tenants t on t.id = tr.tenant_id where tr.enabled and t.status = 'active';
