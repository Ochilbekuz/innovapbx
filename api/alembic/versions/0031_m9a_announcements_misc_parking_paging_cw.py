"""M9 Bo'lak A: e'lonlar (allow_skip/repeat_key/answer), boshqa manzillar
(`misc_destinations`) + ilovalar (`misc_applications`), parking sozlamalari
(`parking_settings`), paging/intercom guruhlari (`page_groups` +
`page_group_members`), ichki raqamlarda kutish qo'ng'irog'i (`call_waiting`).

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-03
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0031_m9a_announcements_misc_parking_paging_cw.sql")


def downgrade() -> None:
    run_sql_text(
        "drop table if exists page_group_members;"
        "drop table if exists page_groups;"
        "drop table if exists parking_settings;"
        "drop table if exists misc_applications;"
        "drop table if exists misc_destinations;"

        "alter table call_targets drop constraint if exists call_targets_kind_check;"
        "alter table call_targets add constraint call_targets_kind_check check (kind in ("
        "  'extension','ring_group','queue','ivr','time_condition','announcement','voicemail',"
        "  'conference','external','hangup','busy','feature'));"

        "alter table feature_codes drop constraint if exists feature_codes_feature_check;"
        "alter table feature_codes add constraint feature_codes_feature_check check (feature in ("
        "  'voicemail','voicemail_other','dnd_toggle','cf_always_on','cf_always_off','cf_busy_on','cf_busy_off',"
        "  'pickup_group','pickup_direct','park','echo_test','speaking_clock','queue_login','queue_pause',"
        "  'followme_toggle'));"
        "delete from feature_codes where feature in ('intercom', 'cw_on', 'cw_off');"
        "delete from feature_code_defaults where feature in ('intercom', 'cw_on', 'cw_off');"

        "create or replace view asterisk_ext_state as"
        "  select e.number as endpoint, e.dnd, e.forward_always, e.forward_busy,"
        "         e.recording,"
        "         case when coalesce((s.recording ->> 'external_only')::boolean, false) then 't' else 'f' end"
        "           as rec_external_only,"
        "         coalesce((e.follow_me ->> 'enabled')::boolean, false) as fm_enabled,"
        "         e.follow_me ->> 'strategy' as fm_strategy,"
        "         (e.follow_me ->> 'ring_seconds')::int as fm_ring,"
        "         case when coalesce((e.follow_me ->> 'confirm')::boolean, true) then 't' else 'f' end as fm_confirm,"
        "         (select string_agg(n, '&' order by o) from jsonb_array_elements_text(e.follow_me -> 'numbers')"
        "            with ordinality as x(n, o)) as fm_numbers,"
        "         (select string_agg('Local/' || n || '@' || t.code || '-fm-leg/n', '&' order by o)"
        "            from (select e.number as n, 0::bigint as o"
        "                   where coalesce((e.follow_me ->> 'include_extension')::boolean, true)"
        "                  union all"
        "                  select n, o from jsonb_array_elements_text(e.follow_me -> 'numbers') with ordinality as x(n, o)) legs)"
        "           as fm_dial,"
        "         e.recording_out"
        "  from extensions e join tenants t on t.id = e.tenant_id"
        "  left join system_settings s on s.tenant_id = e.tenant_id"
        "  where t.status = 'active';"

        "create or replace function asterisk_ext_state_update() returns trigger language plpgsql as $$"
        "begin"
        "  update extensions e set dnd = new.dnd,"
        "         forward_always = nullif(new.forward_always, ''),"
        "         forward_busy = nullif(new.forward_busy, ''),"
        "         follow_me = case when new.fm_enabled is distinct from old.fm_enabled"
        "                          then jsonb_set(e.follow_me, '{enabled}', to_jsonb(coalesce(new.fm_enabled, false)))"
        "                          else e.follow_me end"
        "    from tenants t"
        "   where t.id = e.tenant_id and e.number = old.endpoint;"
        "  return new;"
        "end $$;"

        "alter table extensions drop column if exists call_waiting;"

        "alter table announcements drop constraint if exists announcements_repeat_key_check;"
        "alter table announcements drop column if exists answer;"
        "alter table announcements drop column if exists repeat_key;"
        "alter table announcements drop column if exists allow_skip;"
    )
