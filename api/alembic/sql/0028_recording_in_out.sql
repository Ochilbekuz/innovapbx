-- Ichki raqamda ikkita ALOHIDA yozuv siyosati: kiruvchi va chiquvchi.
--
-- `extensions.recording` nomi O'ZGARMAYDI (FreePBX import, public API, fake API
-- ko'p joyda shu nomni ishlatadi) — endi aniq KIRUVCHI (shu raqamga kelgan
-- qo'ng'iroq) siyosat sifatida o'qiladi. Yangi `recording_out` — CHIQUVCHI (shu
-- raqamdan chiqqan qo'ng'iroq) siyosat; boshlang'ich qiymat = mavjud `recording`
-- (xulq o'zgarmasin: oldin bitta siyosat ikki tomonga ham tegishli edi).

alter table extensions add column if not exists recording_out text;
update extensions set recording_out = recording where recording_out is null;
alter table extensions alter column recording_out set default 'always';
alter table extensions alter column recording_out set not null;

-- asterisk_ext_state: PostgreSQL faqat view OXIRIGA ustun qo'shishga ruxsat
-- beradi (mavjud ustunlar/tartib o'zgarmasin) — 0027'ning oxirgi ta'rifi + `recording_out`.
create or replace view asterisk_ext_state as
  select e.number as endpoint, e.dnd, e.forward_always, e.forward_busy,
         e.recording,
         case when coalesce((s.recording ->> 'external_only')::boolean, false) then 't' else 'f' end
           as rec_external_only,
         coalesce((e.follow_me ->> 'enabled')::boolean, false) as fm_enabled,
         e.follow_me ->> 'strategy' as fm_strategy,
         (e.follow_me ->> 'ring_seconds')::int as fm_ring,
         case when coalesce((e.follow_me ->> 'confirm')::boolean, true) then 't' else 'f' end as fm_confirm,
         (select string_agg(n, '&' order by o) from jsonb_array_elements_text(e.follow_me -> 'numbers')
            with ordinality as x(n, o)) as fm_numbers,
         (select string_agg('Local/' || n || '@' || t.code || '-fm-leg/n', '&' order by o)
            from (select e.number as n, 0::bigint as o
                   where coalesce((e.follow_me ->> 'include_extension')::boolean, true)
                  union all
                  select n, o from jsonb_array_elements_text(e.follow_me -> 'numbers') with ordinality as x(n, o)) legs)
           as fm_dial,
         e.recording_out
  from extensions e join tenants t on t.id = e.tenant_id
  left join system_settings s on s.tenant_id = e.tenant_id
  where t.status = 'active';
