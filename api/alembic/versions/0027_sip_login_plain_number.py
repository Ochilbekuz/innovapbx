"""SIP login = ichki raqamning o'zi: ps_endpoints/ps_auths/ps_aors,
asterisk_queue_members, asterisk_ext_state, asterisk_agent_state — tenant
kod prefiksi (`t.code || '-' ||`) ichki raqam qismidan olib tashlanadi.
Trunk endpoint'lari (`t.code || '-trunk-' || tr.id`) TEGILMAYDI.

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-02
"""
from __future__ import annotations

from pathlib import Path

from app.db.raw_sql import run_sql_file, run_sql_text

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None

_SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    run_sql_file(_SQL_DIR / "0027_sip_login_plain_number.sql")


def downgrade() -> None:
    """0027'dan oldingi (eng so'nggi tenant-prefiksli) ta'riflarni qayta tiklaydi:
    ps_endpoints — 0017, ps_auths — 0009, ps_aors — 0001, asterisk_queue_members —
    0015, asterisk_ext_state(+trigger) — 0024, asterisk_agent_state(+trigger) — 0015."""
    run_sql_text(
        "create or replace view ps_endpoints as"
        "  select t.code || '-' || e.number as id,"
        "         'transport-' || case when e.webrtc then 'wss' else 'udp' end as transport,"
        "         t.code || '-' || e.number as aors, t.code || '-' || e.number as auth,"
        "         t.code || '-from-internal' as context, 'all' as disallow,"
        "         array_to_string(e.codecs, ',') as allow,"
        "         'no' as direct_media, 'yes' as rtp_symmetric, 'yes' as force_rport,"
        "         'yes' as rewrite_contact,"
        "         '\"' || coalesce(e.callerid_name, e.name) || '\" <' || e.number || '>' as callerid,"
        "         t.code as accountcode,"
        "         (select vb.mailbox || '@' || t.code from voicemail_boxes vb"
        "            where vb.extension_id = e.id) as mailboxes,"
        "         case when e.webrtc then 'yes' else 'no' end as webrtc,"
        "         case when e.webrtc then 'rfc4733' else 'info' end as dtmf_mode,"
        "         t.code || '-' || e.pickup_group as named_call_group,"
        "         t.code || '-' || e.pickup_group as named_pickup_group"
        "  from extensions e join tenants t on t.id = e.tenant_id where t.status = 'active'"
        "  union all"
        "  select t.code || '-trunk-' || tr.id::text, 'transport-' || tr.transport,"
        "         t.code || '-trunk-' || tr.id::text,"
        "         case when tr.auth_mode = 'register' then t.code || '-trunk-' || tr.id::text end,"
        "         t.code || '-from-trunk', 'all', array_to_string(tr.codecs, ','), 'no', 'yes', 'yes', 'no',"
        "         null, t.code, null, 'no', 'info', null, null"
        "  from trunks tr join tenants t on t.id = tr.tenant_id"
        "  where tr.enabled and t.status = 'active';"

        "create or replace view ps_auths as"
        "  select t.code || '-' || e.number as id, 'userpass' as auth_type,"
        "         t.code || '-' || e.number as username,"
        "         sip_secret(e.sip_password_enc) as password, 'asterisk' as realm"
        "  from extensions e join tenants t on t.id = e.tenant_id"
        "  union all"
        "  select t.code || '-trunk-' || tr.id::text, 'userpass', tr.username,"
        "         sip_secret(tr.password_enc), null::text as realm"
        "  from trunks tr join tenants t on t.id = tr.tenant_id where tr.auth_mode = 'register';"

        "create or replace view ps_aors as"
        "  select t.code || '-' || e.number as id, e.max_contacts, 'yes' as remove_existing,"
        "         60 as qualify_frequency, null::text as contact"
        "  from extensions e join tenants t on t.id = e.tenant_id"
        "  union all"
        "  select t.code || '-trunk-' || tr.id::text, 1, 'no', 30, 'sip:' || tr.host || ':' || tr.port"
        "  from trunks tr join tenants t on t.id = tr.tenant_id;"

        "create or replace view asterisk_queue_members as"
        "  select t.code || '-q-' || q.id::text || '-' || e.number as uniqueid,"
        "         t.code || '-q-' || q.id::text as queue_name,"
        "         'PJSIP/' || t.code || '-' || e.number as interface, e.name as membername,"
        "         'PJSIP/' || t.code || '-' || e.number as state_interface, qm.penalty,"
        "         case when qm.paused or e.dnd then 1 else 0 end as paused,"
        "         coalesce(qm.pause_reason, '')::varchar(80) as reason_paused"
        "  from queue_members qm join queues q on q.id = qm.queue_id"
        "  join extensions e on e.id = qm.extension_id join tenants t on t.id = q.tenant_id"
        "  where not qm.dynamic or qm.logged_in;"

        "create or replace view asterisk_ext_state as"
        "  select t.code || '-' || e.number as endpoint, e.dnd, e.forward_always, e.forward_busy,"
        "         e.recording,"
        "         case when coalesce((s.recording ->> 'external_only')::boolean, false) then 't' else 'f' end"
        "           as rec_external_only,"
        "         coalesce((e.follow_me ->> 'enabled')::boolean, false) as fm_enabled,"
        "         e.follow_me ->> 'strategy' as fm_strategy,"
        "         (e.follow_me ->> 'ring_seconds')::int as fm_ring,"
        "         case when coalesce((e.follow_me ->> 'confirm')::boolean, true) then 't' else 'f' end"
        "           as fm_confirm,"
        "         (select string_agg(n, '&' order by o) from jsonb_array_elements_text(e.follow_me -> 'numbers')"
        "            with ordinality as x(n, o)) as fm_numbers,"
        "         (select string_agg('Local/' || n || '@' || t.code || '-fm-leg/n', '&' order by o)"
        "            from (select e.number as n, 0::bigint as o"
        "                   where coalesce((e.follow_me ->> 'include_extension')::boolean, true)"
        "                  union all"
        "                  select n, o from jsonb_array_elements_text(e.follow_me -> 'numbers')"
        "                    with ordinality as x(n, o)) legs)"
        "           as fm_dial"
        "  from extensions e join tenants t on t.id = e.tenant_id"
        "  left join system_settings s on s.tenant_id = e.tenant_id"
        "  where t.status = 'active';"

        "create or replace function asterisk_ext_state_update() returns trigger language plpgsql as $$"
        "begin"
        "  update extensions e set dnd = new.dnd,"
        "         forward_always = nullif(new.forward_always, ''),"
        "         forward_busy = nullif(new.forward_busy, ''),"
        "         follow_me = case when new.fm_enabled is distinct from old.fm_enabled"
        "                          then jsonb_set(e.follow_me, '{enabled}',"
        "                                         to_jsonb(coalesce(new.fm_enabled, false)))"
        "                          else e.follow_me end"
        "    from tenants t"
        "   where t.id = e.tenant_id and t.code || '-' || e.number = old.endpoint;"
        "  return new;"
        "end $$;"

        "create or replace view asterisk_agent_state as"
        "  select t.code || '-' || e.number as endpoint,"
        "         coalesce(bool_or(qm.logged_in) filter (where qm.dynamic), false) as logged_in,"
        "         coalesce(bool_or(qm.paused), false) as paused"
        "  from extensions e"
        "  join tenants t on t.id = e.tenant_id"
        "  left join queue_members qm on qm.extension_id = e.id"
        "  where t.status = 'active'"
        "  group by t.code, e.number;"

        "create or replace function asterisk_agent_state_update() returns trigger language plpgsql as $$"
        "declare"
        "  v_ext_id uuid;"
        "begin"
        "  select e.id into v_ext_id from extensions e join tenants t on t.id = e.tenant_id"
        "   where t.code || '-' || e.number = old.endpoint;"
        "  if v_ext_id is null then"
        "    return new;"
        "  end if;"
        "  if new.logged_in is distinct from old.logged_in then"
        "    update queue_members set logged_in = new.logged_in"
        "     where extension_id = v_ext_id and dynamic;"
        "  end if;"
        "  if new.paused is distinct from old.paused then"
        "    update queue_members set paused = new.paused,"
        "           pause_reason = case when new.paused then pause_reason else null end"
        "     where extension_id = v_ext_id;"
        "  end if;"
        "  return new;"
        "end $$;"
    )
