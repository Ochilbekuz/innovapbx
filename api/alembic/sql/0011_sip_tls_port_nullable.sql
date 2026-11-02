-- M1c bo'lim 3: SIP TLS. `sip_tls_port` NOT NULL DEFAULT 5061 edi (0001_schema.sql),
-- lekin API qatlami (`_NULLABLE` to'plami, `UpdateSipSettingsItem.sip_tls_port: int | None`,
-- `app/services/sip_transport.py::SipConfig.sip_tls_port`) allaqachon TLS'ni o'chirish
-- uchun aniq `null`ni qabul qiladi/kutadi — ustun shu semantikaga moslashtiriladi.
-- Default 5061 saqlanadi (yangi tenant'lar uchun TLS porti tayyor turadi,
-- faqat sertifikat yuklanmaguncha `tls_enabled` false bo'ladi).
alter table system_settings alter column sip_tls_port drop not null;
