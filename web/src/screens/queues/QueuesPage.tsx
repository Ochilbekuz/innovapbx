import { useMemo, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Pencil, Plus, ShieldAlert, Trash2 } from 'lucide-react';
import { useAudio, useCreateQueue, useDeleteQueue, useExtensions, useMohClasses, useQueues, useTargets, useUpdateQueue } from '@/api/queries';
import { isApiError } from '@/api/errors';
import type {
  MohClass, Queue, QueueAnnounceHoldTime, QueueAnnouncePosition, QueueAutoPause, QueueJoinEmpty, QueueMaxWaitMode,
  QueueRingMode, QueueStrategy,
} from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { cn } from '@/lib/cn';
import { applyToast } from '@/lib/applyToast';
import { usagesOf } from '@/lib/usageError';
import { type Catalog, type Destination } from '@/domain/destination';
import { DestinationPicker } from '@/pbx/DestinationPicker';
import { toCatalog } from '@/pbx/catalog';
import { NumberField } from '@/pbx/NumberField';
import { SortableList } from '@/pbx/SortableList';
import { UsageList } from '@/pbx/UsageList';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Drawer, Modal } from '@/ui/Dialog';
import { Field, Input, Select, type FieldA11y } from '@/ui/Field';
import { Badge } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

const NAME_MAX = 60;
const M1A_TARGETS = ['extension', 'ring_group', 'queue', 'ivr', 'time_condition', 'conference', 'hangup', 'busy', 'announcement', 'misc'] as const;
// 0037 (Queues FreePBX parity) — Alert-Info'ning server tomonidagi aynan oʻzi (`_ALERT_INFO_PATTERN`, `schemas.py`).
const ALERT_INFO_RE = /^[A-Za-z0-9=<>:;/._@-]{1,128}$/;

/** S10 — Navbatlar: operatorlar orasida qoʻngʻiroqni taqsimlash, kutish/SLA, jonli holat. */
export function QueuesPage() {
  const { t } = useTranslation('queues');
  const { data, isLoading, isError, refetch } = useQueues();
  const { data: extensions } = useExtensions({ size: 200 });
  const { data: targets } = useTargets({ kind: M1A_TARGETS.join(',') });
  const { data: mohClasses } = useMohClasses();
  const { data: audioData } = useAudio();
  const canManage = useCanEdit('routing');
  const toast = useToast();
  const [editing, setEditing] = useState<Queue | 'new' | null>(null);
  const [deleting, setDeleting] = useState<Queue | null>(null);
  const [deleteErr, setDeleteErr] = useState<ReturnType<typeof usagesOf> | null>(null);

  const createM = useCreateQueue();
  const updateM = useUpdateQueue();
  const deleteM = useDeleteQueue();
  const close = () => { setEditing(null); createM.reset(); updateM.reset(); };
  const mutation = editing === 'new' ? createM : updateM;
  const catalog: Catalog = useMemo(() => toCatalog(targets?.items ?? []), [targets]);
  const strategyLabel: Record<QueueStrategy, string> = {
    ringall: t('strategy.ringall'), leastrecent: t('strategy.leastrecent'), fewestcalls: t('strategy.fewestcalls'),
    random: t('strategy.random'), rrmemory: t('strategy.rrmemory'), linear: t('strategy.linear'), wrandom: t('strategy.wrandom'),
  };

  const columns: Column<Queue>[] = [
    { key: 'name', header: t('column.name'), sortValue: (r) => r.name, cell: (r) => <span className="block max-w-[200px] truncate font-medium" title={r.name}>{r.name}</span> },
    { key: 'number', header: t('column.number'), cell: (r) => <span className="num text-muted">{r.number ?? '—'}</span> },
    { key: 'strategy', header: t('column.strategy'), cell: (r) => strategyLabel[r.strategy] },
    { key: 'members', header: t('column.members'), cell: (r) => <Badge tone="accent" mono>{r.members.length}</Badge> },
    {
      key: 'live', header: t('column.live'), cell: (r) => r.live ? (
        <span className="inline-flex items-center gap-1.5 text-sm">
          <span className={cn('inline-flex size-1.5 rounded-pill', r.live.waiting > 0 ? 'bg-warning' : 'bg-success')} aria-hidden />
          {t('live.waitingAndOnline', { waiting: r.live.waiting, online: r.live.members_online })}
        </span>
      ) : <span className="text-muted">—</span>,
    },
    {
      key: 'actions', header: '', align: 'right', cell: (r) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('editAriaLabel', { name: r.name })} disabled={!canManage} onClick={() => setEditing(r)} />
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('deleteAriaLabel', { name: r.name })} disabled={!canManage} onClick={() => setDeleting(r)} />
        </div>
      ),
    },
  ];

  return (
    <AppShellPage title={t('title')}>
      {!canManage && (
        <p className="mb-3 flex items-center gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2 text-sm text-muted">
          <ShieldAlert aria-hidden className="size-4 shrink-0" />
          {t('readOnlyNotice')}
        </p>
      )}
      <DataTable
        caption={t('caption')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(r) => r.id}
        searchText={(r) => `${r.name} ${r.number ?? ''}`}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        onRowOpen={canManage ? (r) => setEditing(r) : undefined}
        empty={{
          title: t('empty.title'),
          body: t('empty.body'),
          action: canManage ? <Button size="sm" onClick={() => setEditing('new')}>{t('empty.action')}</Button> : undefined,
        }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setEditing('new')}>{t('newQueue')}</Button> : undefined}
      />

      {editing && (
        <QueueDrawer
          queue={editing === 'new' ? undefined : editing}
          extensions={extensions?.items ?? []}
          mohClasses={mohClasses?.items ?? []}
          audio={audioData?.items ?? []}
          catalog={catalog}
          pending={mutation.isPending}
          errorField={isApiError(mutation.error) ? mutation.error.field : undefined}
          errorMessage={isApiError(mutation.error) ? mutation.error.message : undefined}
          onClose={close}
          onSubmit={(payload) => {
            if (editing === 'new') createM.mutate(payload, { onSuccess: (res) => { close(); toast(applyToast(res.apply, t('toast.added'))); } });
            else updateM.mutate({ id: editing.id, payload: { ...payload, updated_at: editing.updated_at } }, { onSuccess: (res) => { close(); toast(applyToast(res.apply, t('toast.saved'))); } });
          }}
        />
      )}

      <Modal
        open={!!deleting}
        onOpenChange={(v) => !v && (setDeleting(null), setDeleteErr(null))}
        title={deleting ? t('deleteModal.title', { name: deleting.name }) : ''}
        footer={
          <>
            <Button variant="ghost" onClick={() => { setDeleting(null); setDeleteErr(null); }}>{t('cancel')}</Button>
            {!deleteErr && (
              <Button
                variant="danger" loading={deleteM.isPending}
                onClick={() => deleting && deleteM.mutate(deleting.id, {
                  onSuccess: () => { toast({ kind: 'success', title: t('toast.deleted', { name: deleting.name }) }); setDeleting(null); },
                  onError: (e) => { if (isApiError(e) && e.code === 'in_use') setDeleteErr(usagesOf(e)); else toast({ kind: 'error', title: t('toast.deleteFailed'), description: e.message }); },
                })}
              >
                {t('delete')}
              </Button>
            )}
          </>
        }
      >
        {deleteErr ? (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-danger">{t('deleteModal.usagePrefix', { name: deleting?.name })}</p>
            <UsageList usages={deleteErr} />
          </div>
        ) : (
          <p className="text-sm text-muted">{t('deleteModal.body', { name: deleting?.name })}</p>
        )}
      </Modal>
    </AppShellPage>
  );
}

type ExtRef = { id: string; number: string; name: string };
type MemberRow = ExtRef & { penalty: number; dynamic?: boolean; logged_in?: boolean; paused?: boolean; pause_reason?: string | null };
type AudioRef = { id: string; name: string };

/** FreePBX uslubidagi bo'lim sarlavhasi (CampaignForm.tsx'dagi `Section` bilan bir xil naqsh). */
function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3.5 border-t border-line pt-4 first:border-t-0 first:pt-0">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">{title}</h3>
      {children}
    </section>
  );
}

function QueueDrawer({
  queue, extensions, mohClasses, audio, catalog, onClose, onSubmit, pending, errorField, errorMessage,
}: {
  queue?: Queue;
  extensions: ExtRef[];
  mohClasses: MohClass[];
  audio: AudioRef[];
  catalog: Catalog;
  onClose: () => void;
  onSubmit: (payload: {
    name: string; number: string | null; strategy: QueueStrategy; agent_ring_seconds: number; retry_seconds: number;
    wrapup_seconds: number; max_wait_seconds: number; max_callers: number | null; announce_position: QueueAnnouncePosition;
    announce_frequency_seconds: number; sla_seconds: number; join_empty: QueueJoinEmpty; record: boolean;
    members: { extension_id: string; penalty: number }[]; timeout_target_id: string; moh_class_id?: string | null;
    skip_busy_agents: boolean; weight: number; autofill: boolean; report_hold_time: boolean; member_delay_seconds: number;
    penalty_members_limit: number; auto_pause: QueueAutoPause; auto_pause_delay_seconds: number; auto_pause_busy: boolean;
    auto_pause_unavail: boolean; agent_timeout_restart: boolean; max_wait_mode: QueueMaxWaitMode; leave_when_empty: QueueJoinEmpty;
    announce_position_limit: number; announce_hold_time: QueueAnnounceHoldTime; min_announce_frequency_seconds: number;
    periodic_announce_audio_id: string | null; periodic_announce_audio_id_clear: boolean; periodic_announce_frequency_seconds: number;
    ring_mode: QueueRingMode; mark_answered_elsewhere: boolean;
    cid_name_prefix: string | null; cid_name_prefix_clear: boolean; alert_info: string | null; alert_info_clear: boolean;
    join_announcement_audio_id: string | null; join_announcement_audio_id_clear: boolean;
    agent_announcement_audio_id: string | null; agent_announcement_audio_id_clear: boolean;
    breakout_target_id: string | null; breakout_target_id_clear: boolean;
  }) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('queues');
  const strategyLabel: Record<QueueStrategy, string> = {
    ringall: t('strategy.ringall'), leastrecent: t('strategy.leastrecent'), fewestcalls: t('strategy.fewestcalls'),
    random: t('strategy.random'), rrmemory: t('strategy.rrmemory'), linear: t('strategy.linear'), wrandom: t('strategy.wrandom'),
  };
  const [name, setName] = useState(queue?.name ?? '');
  const [number, setNumber] = useState(queue?.number ?? '');
  const [strategy, setStrategy] = useState<QueueStrategy>(queue?.strategy ?? 'ringall');
  const [agentRing, setAgentRing] = useState(queue?.agent_ring_seconds ?? 15);
  const [retry, setRetry] = useState(queue?.retry_seconds ?? 5);
  const [wrapup, setWrapup] = useState(queue?.wrapup_seconds ?? 5);
  const [maxWait, setMaxWait] = useState(queue?.max_wait_seconds ?? 300);
  const [maxCallers, setMaxCallers] = useState(queue?.max_callers != null ? String(queue.max_callers) : '');
  const [announcePos, setAnnouncePos] = useState<QueueAnnouncePosition>(queue?.announce_position ?? 'yes');
  const [announceFreq, setAnnounceFreq] = useState(queue?.announce_frequency_seconds ?? 30);
  const [sla, setSla] = useState(queue?.sla_seconds ?? 20);
  const [joinEmpty, setJoinEmpty] = useState<QueueJoinEmpty>(queue?.join_empty ?? 'no');
  const [record, setRecord] = useState(queue?.record ?? false);
  const [mohClassId, setMohClassId] = useState(queue?.moh_class?.id ?? '');
  const [members, setMembers] = useState<MemberRow[]>(() => (queue?.members ?? []).map((m) => ({
    ...m.extension, penalty: m.penalty, dynamic: m.dynamic, logged_in: m.logged_in, paused: m.paused, pause_reason: m.pause_reason,
  })));
  const [timeoutTarget, setTimeoutTarget] = useState<Destination | null>(queue ? { kind: queue.timeout_target.kind, targetId: queue.timeout_target.id } : null);

  // 0037 (Queues FreePBX parity) — "Vaqt va agentlar".
  const [ringMode, setRingMode] = useState<QueueRingMode>(queue?.ring_mode ?? 'moh');
  const [weight, setWeight] = useState(queue?.weight ?? 0);
  const [autofill, setAutofill] = useState(queue?.autofill ?? false);
  const [skipBusyAgents, setSkipBusyAgents] = useState(queue?.skip_busy_agents ?? true);
  const [markAnsweredElsewhere, setMarkAnsweredElsewhere] = useState(queue?.mark_answered_elsewhere ?? false);
  const [agentTimeoutRestart, setAgentTimeoutRestart] = useState(queue?.agent_timeout_restart ?? false);
  const [memberDelay, setMemberDelay] = useState(queue?.member_delay_seconds ?? 0);
  const [maxWaitMode, setMaxWaitMode] = useState<QueueMaxWaitMode>(queue?.max_wait_mode ?? 'strict');

  // "Sig'im".
  const [leaveWhenEmpty, setLeaveWhenEmpty] = useState<QueueJoinEmpty>(queue?.leave_when_empty ?? 'no');
  const [penaltyMembersLimit, setPenaltyMembersLimit] = useState(queue?.penalty_members_limit ?? 0);

  // "E'lonlar".
  const [announcePosLimit, setAnnouncePosLimit] = useState(queue?.announce_position_limit ?? 10);
  const [announceHoldTime, setAnnounceHoldTime] = useState<QueueAnnounceHoldTime>(queue?.announce_hold_time ?? 'yes');
  const [minAnnounceFreq, setMinAnnounceFreq] = useState(queue?.min_announce_frequency_seconds ?? 15);
  const [reportHoldTime, setReportHoldTime] = useState(queue?.report_hold_time ?? false);
  const [periodicAudioId, setPeriodicAudioId] = useState(queue?.periodic_announce_audio?.id ?? '');
  const [periodicFreq, setPeriodicFreq] = useState(queue?.periodic_announce_frequency_seconds ?? 60);
  const [joinAudioId, setJoinAudioId] = useState(queue?.join_announcement_audio?.id ?? '');
  const [agentAudioId, setAgentAudioId] = useState(queue?.agent_announcement_audio?.id ?? '');

  // "Kengaytirilgan".
  const [cidNamePrefix, setCidNamePrefix] = useState(queue?.cid_name_prefix ?? '');
  const [alertInfo, setAlertInfo] = useState(queue?.alert_info ?? '');
  const [autoPause, setAutoPause] = useState<QueueAutoPause>(queue?.auto_pause ?? 'no');
  const [autoPauseDelay, setAutoPauseDelay] = useState(queue?.auto_pause_delay_seconds ?? 0);
  const [autoPauseBusy, setAutoPauseBusy] = useState(queue?.auto_pause_busy ?? false);
  const [autoPauseUnavail, setAutoPauseUnavail] = useState(queue?.auto_pause_unavail ?? false);
  const [breakoutTarget, setBreakoutTarget] = useState<Destination | null>(
    queue?.breakout_target ? { kind: queue.breakout_target.kind, targetId: queue.breakout_target.id } : null,
  );

  const available = extensions.filter((e) => !members.some((m) => m.id === e.id));
  const alertInfoError = alertInfo.trim() !== '' && !ALERT_INFO_RE.test(alertInfo.trim()) ? t('form.alertInfoError') : undefined;
  const valid = name.trim().length > 0 && members.length > 0 && !!timeoutTarget && timeoutTarget.kind !== 'external' && !alertInfoError;

  const submit = () => {
    if (!valid || !timeoutTarget) return;
    onSubmit({
      name: name.trim(), number: number.trim() || null, strategy, agent_ring_seconds: agentRing, retry_seconds: retry,
      wrapup_seconds: wrapup, max_wait_seconds: maxWait, max_callers: maxCallers.trim() ? Number(maxCallers) : null,
      announce_position: announcePos, announce_frequency_seconds: announceFreq, sla_seconds: sla, join_empty: joinEmpty, record,
      members: members.map((m) => ({ extension_id: m.id, penalty: m.penalty })), timeout_target_id: timeoutTarget.targetId,
      moh_class_id: mohClassId || null,
      skip_busy_agents: skipBusyAgents, weight, autofill, report_hold_time: reportHoldTime, member_delay_seconds: memberDelay,
      penalty_members_limit: penaltyMembersLimit, auto_pause: autoPause, auto_pause_delay_seconds: autoPauseDelay,
      auto_pause_busy: autoPauseBusy, auto_pause_unavail: autoPauseUnavail, agent_timeout_restart: agentTimeoutRestart,
      max_wait_mode: maxWaitMode, leave_when_empty: leaveWhenEmpty, announce_position_limit: announcePosLimit,
      announce_hold_time: announceHoldTime, min_announce_frequency_seconds: minAnnounceFreq,
      periodic_announce_audio_id: periodicAudioId || null, periodic_announce_audio_id_clear: !periodicAudioId,
      periodic_announce_frequency_seconds: periodicFreq, ring_mode: ringMode, mark_answered_elsewhere: markAnsweredElsewhere,
      cid_name_prefix: cidNamePrefix.trim() || null, cid_name_prefix_clear: !cidNamePrefix.trim(),
      alert_info: alertInfo.trim() || null, alert_info_clear: !alertInfo.trim(),
      join_announcement_audio_id: joinAudioId || null, join_announcement_audio_id_clear: !joinAudioId,
      agent_announcement_audio_id: agentAudioId || null, agent_announcement_audio_id_clear: !agentAudioId,
      breakout_target_id: breakoutTarget?.kind === 'external' ? null : breakoutTarget?.targetId ?? null,
      breakout_target_id_clear: !breakoutTarget || breakoutTarget.kind === 'external',
    });
  };

  const audioOptions = (noneLabel: string) => [{ value: '__none', label: noneLabel }, ...audio.map((a) => ({ value: a.id, label: a.name }))];

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={queue ? t('form.editTitle', { name: queue.name }) : t('form.newTitle')}
      description={queue?.live ? t('form.liveNow', { waiting: queue.live.waiting, online: queue.live.members_online }) : undefined}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={submit}>{queue ? t('save') : t('add')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errorMessage && errorField !== 'number' && errorField !== 'members' && <p className="text-sm text-danger">{errorMessage}</p>}

        <Section title={t('section.general')}>
          <Field label={t('form.nameLabel')} required hint={t('form.nameHint', { max: NAME_MAX })}>
            {(a) => <Input {...a} autoFocus maxLength={NAME_MAX} value={name} onChange={(e) => setName(e.target.value)} />}
          </Field>
          <NumberField value={number} onChange={setNumber} error={errorField === 'number' ? errorMessage : undefined} hint={t('form.numberHint')} />
          <Field label={t('form.strategyLabel')} required>
            {({ id }) => <Select id={id} value={strategy} onValueChange={(v) => setStrategy(v as QueueStrategy)} options={Object.entries(strategyLabel).map(([value, label]) => ({ value, label }))} />}
          </Field>

          <div>
            <p className="mb-2 text-sm font-medium text-fg">{t('form.membersLabel')} <span className="text-muted">{t('form.membersCount', { count: members.length })}</span></p>
            {members.length === 0 ? (
              <p className="rounded-md border border-dashed border-line px-3 py-4 text-center text-sm text-muted">{t('form.noMembers')}</p>
            ) : (
              <SortableList
                items={members}
                onChange={setMembers}
                itemId={(m) => m.id}
                itemLabel={(m) => m.name}
                label={t('form.membersListAriaLabel')}
                render={(m) => (
                  <div className="flex min-w-0 flex-1 items-center justify-between gap-2">
                    <span className="flex min-w-0 items-center gap-2 truncate text-sm">
                      {m.name} <span className="num text-muted">{m.number}</span>
                      {m.dynamic && <Badge tone="accent">{t('form.dynamic')}</Badge>}
                      {m.logged_in !== undefined && (
                        <span title={m.paused && m.pause_reason ? m.pause_reason : undefined}>
                          <Badge tone={!m.logged_in ? 'neutral' : m.paused ? 'warning' : 'success'}>
                            {!m.logged_in ? t('form.stateLoggedOut') : m.paused ? t('form.statePaused') : t('form.stateLoggedIn')}
                          </Badge>
                        </span>
                      )}
                    </span>
                    <div className="flex items-center gap-2">
                      <label className="flex items-center gap-1.5 text-xs text-muted">
                        {t('form.penalty')}
                        <input
                          type="number" min={0} max={10} value={m.penalty}
                          onChange={(e) => setMembers((ms) => ms.map((x) => (x.id === m.id ? { ...x, penalty: Number(e.target.value) } : x)))}
                          className="num h-7 w-14 rounded-sm border border-line bg-surface px-1.5 text-center text-fg"
                        />
                      </label>
                      <Button size="sm" variant="ghost" onClick={() => setMembers((ms) => ms.filter((x) => x.id !== m.id))}>{t('form.remove')}</Button>
                    </div>
                  </div>
                )}
              />
            )}
            {errorField === 'members' && errorMessage && <p className="mt-1.5 text-sm text-danger">{errorMessage}</p>}
            {available.length > 0 && (
              <div className="mt-2">
                <Select
                  aria-label={t('form.addMemberAriaLabel')}
                  value="__add" onValueChange={(v) => { const ext = available.find((e) => e.id === v); if (ext) setMembers((ms) => [...ms, { ...ext, penalty: 0 }]); }}
                  options={[{ value: '__add', label: t('form.addMemberOption') }, ...available.map((e) => ({ value: e.id, label: `${e.name} (${e.number})` }))]}
                />
              </div>
            )}
          </div>

          <DestinationPicker label={t('form.timeoutLabel')} required kinds={['extension', 'ring_group', 'queue', 'ivr', 'time_condition', 'conference', 'hangup', 'busy', 'announcement', 'misc']} value={timeoutTarget} onChange={setTimeoutTarget} catalog={catalog} />

          <Field label={t('form.mohLabel')} aside={t('form.mohAside')} hint={t('form.mohHint')}>
            {({ id }) => (
              <Select
                id={id} value={mohClassId || '__none'} onValueChange={(v) => setMohClassId(v === '__none' ? '' : v)}
                options={[{ value: '__none', label: t('form.mohDefault') }, ...mohClasses.map((m) => ({ value: m.id, label: m.name }))]}
              />
            )}
          </Field>
          <Field label={t('ringMode.label')}>
            {({ id }) => (
              <Select
                id={id} value={ringMode} onValueChange={(v) => setRingMode(v as QueueRingMode)}
                options={[{ value: 'moh', label: t('ringMode.moh') }, { value: 'ring', label: t('ringMode.ring') }]}
              />
            )}
          </Field>
        </Section>

        <Section title={t('section.timeAgents')}>
          <div className="grid grid-cols-2 gap-3">
            <Field label={t('form.agentRing')}>{(a) => <Numeric a11y={a} value={agentRing} onChange={setAgentRing} min={5} max={120} />}</Field>
            <Field label={t('form.retry')}>{(a) => <Numeric a11y={a} value={retry} onChange={setRetry} min={1} max={60} />}</Field>
            <Field label={t('form.wrapup')}>{(a) => <Numeric a11y={a} value={wrapup} onChange={setWrapup} min={0} max={60} />}</Field>
            <Field label={t('form.maxWait')}>{(a) => <Numeric a11y={a} value={maxWait} onChange={setMaxWait} min={10} max={1800} />}</Field>
            <Field label={t('weightLabel')} hint={t('weightHint')}>{(a) => <Numeric a11y={a} value={weight} onChange={setWeight} min={0} max={100} />}</Field>
            <Field label={t('memberDelayLabel')}>{(a) => <Numeric a11y={a} value={memberDelay} onChange={setMemberDelay} min={0} max={60} />}</Field>
          </div>
          <Field label={t('maxWaitModeLabel')}>
            {({ id }) => (
              <Select
                id={id} value={maxWaitMode} onValueChange={(v) => setMaxWaitMode(v as QueueMaxWaitMode)}
                options={[{ value: 'strict', label: t('maxWaitModeStrict') }, { value: 'loose', label: t('maxWaitModeLoose') }]}
              />
            )}
          </Field>
          <Toggle checked={autofill} onCheckedChange={setAutofill} label={t('autofillLabel')} description={t('autofillDesc')} />
          <Toggle checked={skipBusyAgents} onCheckedChange={setSkipBusyAgents} label={t('skipBusyLabel')} description={t('skipBusyDesc')} />
          <Toggle checked={markAnsweredElsewhere} onCheckedChange={setMarkAnsweredElsewhere} label={t('markAnsweredElsewhereLabel')} description={t('markAnsweredElsewhereDesc')} />
          <Toggle checked={agentTimeoutRestart} onCheckedChange={setAgentTimeoutRestart} label={t('agentTimeoutRestartLabel')} description={t('agentTimeoutRestartDesc')} />
        </Section>

        <Section title={t('section.capacity')}>
          <Field label={t('form.maxCallersLabel')} aside={t('form.maxCallersAside')} hint={t('form.maxCallersHint')}>
            {(a) => <Input {...a} mono type="number" min={1} value={maxCallers} onChange={(e) => setMaxCallers(e.target.value)} placeholder={t('form.maxCallersPlaceholder')} />}
          </Field>
          <Field label={t('form.joinEmptyLabel')} hint={t('form.joinEmptyDesc')}>
            {({ id }) => (
              <Select
                id={id} value={joinEmpty} onValueChange={(v) => setJoinEmpty(v as QueueJoinEmpty)}
                options={[
                  { value: 'no', label: t('autoPauseNo') }, { value: 'yes', label: t('autoPauseYes') },
                  { value: 'strict', label: 'strict' }, { value: 'loose', label: 'loose' },
                ]}
              />
            )}
          </Field>
          <Field label={t('leaveWhenEmptyLabel')}>
            {({ id }) => (
              <Select
                id={id} value={leaveWhenEmpty} onValueChange={(v) => setLeaveWhenEmpty(v as QueueJoinEmpty)}
                options={[
                  { value: 'no', label: t('autoPauseNo') }, { value: 'yes', label: t('autoPauseYes') },
                  { value: 'strict', label: 'strict' }, { value: 'loose', label: 'loose' },
                ]}
              />
            )}
          </Field>
          <Field label={t('penaltyMembersLimitLabel')} hint={t('penaltyMembersLimitHint')}>
            {(a) => <Numeric a11y={a} value={penaltyMembersLimit} onChange={setPenaltyMembersLimit} min={0} max={10} />}
          </Field>
        </Section>

        <Section title={t('section.announcements')}>
          <div className="grid grid-cols-2 gap-3">
            <Field label={t('form.announceFreq')}>{(a) => <Numeric a11y={a} value={announceFreq} onChange={setAnnounceFreq} min={0} max={300} />}</Field>
            <Field label={t('minAnnounceFreqLabel')}>{(a) => <Numeric a11y={a} value={minAnnounceFreq} onChange={setMinAnnounceFreq} min={0} max={300} />}</Field>
            <Field label={t('announcePosLimitLabel')}>{(a) => <Numeric a11y={a} value={announcePosLimit} onChange={setAnnouncePosLimit} min={1} max={50} />}</Field>
            <Field label={t('periodicAnnounceFreqLabel')}>{(a) => <Numeric a11y={a} value={periodicFreq} onChange={setPeriodicFreq} min={0} max={1800} />}</Field>
          </div>
          <Field label={t('form.announcePosLabel')} hint={t('form.announcePosDesc')}>
            {({ id }) => (
              <Select
                id={id} value={announcePos} onValueChange={(v) => setAnnouncePos(v as QueueAnnouncePosition)}
                options={[
                  { value: 'no', label: t('autoPauseNo') }, { value: 'yes', label: t('autoPauseYes') },
                  { value: 'limit', label: 'limit' }, { value: 'more', label: 'more' },
                ]}
              />
            )}
          </Field>
          <Field label={t('announceHoldTimeLabel')}>
            {({ id }) => (
              <Select
                id={id} value={announceHoldTime} onValueChange={(v) => setAnnounceHoldTime(v as QueueAnnounceHoldTime)}
                options={[{ value: 'no', label: t('autoPauseNo') }, { value: 'yes', label: t('autoPauseYes') }, { value: 'once', label: 'once' }]}
              />
            )}
          </Field>
          <Toggle checked={reportHoldTime} onCheckedChange={setReportHoldTime} label={t('reportHoldTimeLabel')} description={t('reportHoldTimeDesc')} />
          <Field label={t('periodicAnnounceLabel')}>
            {({ id }) => <Select id={id} value={periodicAudioId || '__none'} onValueChange={(v) => setPeriodicAudioId(v === '__none' ? '' : v)} options={audioOptions(t('none'))} />}
          </Field>
          <Field label={t('joinAnnounceLabel')} hint={t('joinAnnounceHint')}>
            {({ id }) => <Select id={id} value={joinAudioId || '__none'} onValueChange={(v) => setJoinAudioId(v === '__none' ? '' : v)} options={audioOptions(t('none'))} />}
          </Field>
          <Field label={t('agentAnnounceLabel')} hint={t('agentAnnounceHint')}>
            {({ id }) => <Select id={id} value={agentAudioId || '__none'} onValueChange={(v) => setAgentAudioId(v === '__none' ? '' : v)} options={audioOptions(t('none'))} />}
          </Field>
        </Section>

        <Section title={t('section.advanced')}>
          <Field label={t('form.sla')}>{(a) => <Numeric a11y={a} value={sla} onChange={setSla} min={5} max={600} />}</Field>
          <Toggle checked={record} onCheckedChange={setRecord} label={t('form.recordLabel')} />
          <Field label={t('cidPrefixLabel')} hint={t('cidPrefixHint')}>
            {(a) => <Input {...a} maxLength={64} value={cidNamePrefix} onChange={(e) => setCidNamePrefix(e.target.value)} />}
          </Field>
          <Field label={t('alertInfoLabel')} hint={t('alertInfoHint')} error={alertInfoError}>
            {(a) => <Input {...a} mono maxLength={128} value={alertInfo} onChange={(e) => setAlertInfo(e.target.value)} />}
          </Field>
          <Field label={t('autoPauseLabel')}>
            {({ id }) => (
              <Select
                id={id} value={autoPause} onValueChange={(v) => setAutoPause(v as QueueAutoPause)}
                options={[{ value: 'no', label: t('autoPauseNo') }, { value: 'yes', label: t('autoPauseYes') }, { value: 'all', label: t('autoPauseAll') }]}
              />
            )}
          </Field>
          {autoPause !== 'no' && (
            <>
              <Field label={t('autoPauseDelayLabel')}>{(a) => <Numeric a11y={a} value={autoPauseDelay} onChange={setAutoPauseDelay} min={0} max={300} />}</Field>
              <Toggle checked={autoPauseBusy} onCheckedChange={setAutoPauseBusy} label={t('autoPauseBusyLabel')} />
              <Toggle checked={autoPauseUnavail} onCheckedChange={setAutoPauseUnavail} label={t('autoPauseUnavailLabel')} />
            </>
          )}
          <div className="flex flex-col gap-1.5">
            <DestinationPicker label={t('breakoutLabel')} hint={t('breakoutHint')} kinds={['extension', 'ring_group', 'queue', 'ivr', 'time_condition', 'conference', 'announcement', 'misc']} value={breakoutTarget} onChange={setBreakoutTarget} catalog={catalog} />
            {breakoutTarget && <Button size="sm" variant="ghost" className="self-start" onClick={() => setBreakoutTarget(null)}>{t('form.remove')}</Button>}
          </div>
        </Section>
      </div>
    </Drawer>
  );
}

function Numeric({ value, onChange, min, max, a11y }: { value: number; onChange: (v: number) => void; min: number; max: number; a11y: FieldA11y }) {
  return <Input {...a11y} mono type="number" min={min} max={max} value={value} onChange={(e) => onChange(Number(e.target.value))} />;
}
