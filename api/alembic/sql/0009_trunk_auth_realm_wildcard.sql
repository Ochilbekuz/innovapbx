-- `ps_auths.realm` trunk (auth_mode='register') qatorlari uchun ham
-- qattiq "asterisk" qiymati bilan to'ldirilgan edi -- bu ICHKI
-- (kiruvchi, extension) autentifikatsiya uchun TO'G'RI (Asterisk o'zi
-- CHALLENGE yuboradi, demak realm'ni o'zi belgilaydi -- 0001_schema.sql
-- 627-qatordagi izohga qarang), LEKIN TASHQI (chiquvchi, trunk REGISTER)
-- autentifikatsiya uchun ISHLAB CHIQARISH XATOSI edi: bu holda Asterisk
-- CLIENT (UAC), realm'ni HAQIQIY provayder (registrar) belgilaydi va u
-- deyarli hech qachon so'zma-so'z "asterisk" bo'lmaydi (masalan haqiqiy
-- operator o'z domenini yoki "sip-trunk" kabi nom beradi). Natijada
-- `res_pjsip_outbound_authenticator_digest` har doim
-- "No auth objects matching realm/algorithm(s) '<provider-realm>/' from
-- challenge found" bilan yiqilib, Asterisk birinchi 401'dan keyin umuman
-- urinishni to'xtatadi ("Fatal response '401' received ... stopping
-- outbound registration") -- ya'ni REGISTER-REJIMLI TRUNKLAR HECH QACHON
-- haqiqiy provayderga muvaffaqiyatli registratsiyadan o'ta olmasdi
-- (m1b-proof.sh ssenariy 7 orqali, soxta registrator realm="innova-test-
-- registrar" bilan CHALLENGE berganda, topilgan -- 2026-10-28).
--
-- Rasmiy Asterisk tavsiyasi (PJSIP Authentication qo'llanmasi): CHIQUVCHI
-- (outbound/UAC) auth obyektlari uchun `realm` BO'SH/NULL qoldirilishi
-- kerak -- shunda `res_pjsip_outbound_authenticator_digest` har qanday
-- realm'ni qabul qiladi ("empty realm matches any challenge"). Faqat
-- KIRUVCHI (inbound/UAS) auth obyektlari uchun aniq realm kerak (bu
-- extension qatorlarida o'zgarishsiz qoladi).
create or replace view ps_auths as
  select t.code || '-' || e.number as id, 'userpass' as auth_type, t.code || '-' || e.number as username,
         sip_secret(e.sip_password_enc) as password, 'asterisk' as realm
  from extensions e join tenants t on t.id = e.tenant_id
  union all
  select t.code || '-trunk-' || tr.id::text, 'userpass', tr.username, sip_secret(tr.password_enc), null::text as realm
  from trunks tr join tenants t on t.id = tr.tenant_id where tr.auth_mode = 'register';
