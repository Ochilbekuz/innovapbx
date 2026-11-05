import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pencil, Phone, Plus, ShieldAlert, Trash2 } from 'lucide-react';
import { apiClient } from '@/api';
import {
  useAudio, useCreateRingGroup, useDeleteRingGroup, useExtensions, useMohClasses, useRingGroups, useTargets,
  useUpdateRingGroup,
} from '@/api/queries';
import { isApiError } from '@/api/errors';
import type {
  RingGroup, RingGroupMemberInput, RingGroupRecordingPolicy, RingGroupStrategy, RingGroupStrategySound,
} from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { applyToast } from '@/lib/applyToast';
import { formatDurationMs } from '@/lib/time';
import { usagesOf } from '@/lib/usageError';
import { normalizeNumber, type Catalog, type Destination } from '@/domain/destination';
import { AudioPlayer } from '@/pbx/AudioPlayer';
import { DestinationPicker } from '@/pbx/DestinationPicker';
import { toCatalog } from '@/pbx/catalog';
import { NumberField } from '@/pbx/NumberField';
import { SortableList } from '@/pbx/SortableList';
import { UsageList } from '@/pbx/UsageList';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Drawer, Modal } from '@/ui/Dialog';
import { Field, Input, Select } from '@/ui/Field';
import { Badge } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

const EXTERNAL_NUMBER = /^\+?\d{3,15}$/;

const NAME_MAX = 60;
const M1A_TARGETS = ['extension', 'ring_group', 'queue', 'ivr', 'time_condition', 'conference', 'hangup', 'busy', 'announcement', 'misc'] as const;
const NONE = '__none';

/** FreePBX Ring Groups'dagi toʻliq strategiya toʻplami (0038). "random" — faqat Queue'da boʻladi, bu yerda yoʻq. */
const STRATEGIES: RingGroupStrategy[] = [
  'ringall', 'ringall-prim', 'hunt', 'hunt-prim', 'memoryhunt', 'memoryhunt-prim', 'firstavailable', 'firstnotonphone',
];
const RECORDING_POLICIES: RingGroupRecordingPolicy[] = ['dontcare', 'force', 'no'];

/** S21 — Qoʻngʻiroq guruhlari: bir vaqtda yoki ketma-ket bir nechta ichki raqamga qoʻngʻiroq. */
export function RingGroupsPage() {
  const { t } = useTranslation('ringgroups');
  const strategyLabel = useMemo(() => Object.fromEntries(STRATEGIES.map((s) => [s, t(`strategy.${s}`)])) as Record<RingGroupStrategy, string>, [t]);
  const { data, isLoading, isError, refetch } = useRingGroups();
  const { data: extensions } = useExtensions({ size: 200 });
  const { data: targets } = useTargets({ kind: M1A_TARGETS.join(',') });
  const { data: audio } = useAudio();
  const { data: mohClasses } = useMohClasses();
  const canManage = useCanEdit('routing');
  const toast = useToast();
  const [editing, setEditing] = useState<RingGroup | 'new' | null>(null);
  const [deleting, setDeleting] = useState<RingGroup | null>(null);
  const [deleteErr, setDeleteErr] = useState<ReturnType<typeof usagesOf> | null>(null);

  const createM = useCreateRingGroup();
  const updateM = useUpdateRingGroup();
  const deleteM = useDeleteRingGroup();
  const close = () => { setEditing(null); createM.reset(); updateM.reset(); };
  const mutation = editing === 'new' ? createM : updateM;
  const catalog: Catalog = useMemo(() => toCatalog(targets?.items ?? []), [targets]);

  const columns: Column<RingGroup>[] = [
    { key: 'name', header: t('column.name'), sortValue: (r) => r.name, cell: (r) => <span className="block max-w-[220px] truncate font-medium" title={r.name}>{r.name}</span> },
    { key: 'number', header: t('column.number'), cell: (r) => <span className="num text-muted">{r.number ?? '—'}</span> },
    { key: 'strategy', header: t('column.strategy'), cell: (r) => strategyLabel[r.strategy] },
    { key: 'members', header: t('column.members'), cell: (r) => <Badge tone="accent" mono>{r.members.length}</Badge> },
    { key: 'na', header: t('column.noAnswer'), cell: (r) => <span className="truncate text-sm text-muted">{r.no_answer_target.label}</span> },
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
        empty={{ title: t('empty.title'), body: t('empty.body'), action: canManage ? <Button size="sm" onClick={() => setEditing('new')}>{t('empty.action')}</Button> : undefined }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setEditing('new')}>{t('newGroup')}</Button> : undefined}
      />

      {editing && (
        <RingGroupDrawer
          group={editing === 'new' ? undefined : editing}
          extensions={extensions?.items ?? []}
          audio={audio?.items ?? []}
          mohClasses={mohClasses?.items ?? []}
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
type MemberRow = { key: string; kind: 'extension'; ext: ExtRef } | { key: string; kind: 'external'; number: string };
type AudioRef = { id: string; name: string; duration_ms: number };
type MohRef = { id: string; name: string };

function toMemberRows(members: RingGroup['members']): MemberRow[] {
  return members.map((m) => (
    m.extension
      ? { key: `ext:${m.extension.id}`, kind: 'extension', ext: m.extension }
      : { key: `ext_num:${m.external_number}`, kind: 'external', number: m.external_number ?? '' }
  ));
}

type RingGroupSubmitPayload = {
  name: string; number: string | null; strategy: RingGroupStrategy; ring_seconds: number;
  members: RingGroupMemberInput[]; no_answer_target_id: string; callerid_prefix: string | null;
  announcement_audio_id?: string; announcement_audio_id_clear?: boolean;
  ring_strategy_sound: RingGroupStrategySound; moh_class_id?: string; moh_class_id_clear?: boolean;
  alert_info?: string; alert_info_clear?: boolean;
  skip_busy_agent: boolean; confirm_calls: boolean;
  remote_announce_audio_id?: string; remote_announce_audio_id_clear?: boolean;
  recording_policy: RingGroupRecordingPolicy;
};

function RingGroupDrawer({
  group, extensions, audio, mohClasses, catalog, onClose, onSubmit, pending, errorField, errorMessage,
}: {
  group?: RingGroup;
  extensions: ExtRef[];
  audio: AudioRef[];
  mohClasses: MohRef[];
  catalog: Catalog;
  onClose: () => void;
  onSubmit: (payload: RingGroupSubmitPayload) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('ringgroups');
  const strategyLabel = useMemo(() => Object.fromEntries(STRATEGIES.map((s) => [s, t(`strategy.${s}`)])) as Record<RingGroupStrategy, string>, [t]);
  const recordingLabel = useMemo(() => Object.fromEntries(RECORDING_POLICIES.map((p) => [p, t(`form.recordingPolicy.${p}`)])) as Record<RingGroupRecordingPolicy, string>, [t]);
  const [name, setName] = useState(group?.name ?? '');
  const [number, setNumber] = useState(group?.number ?? '');
  const [strategy, setStrategy] = useState<RingGroupStrategy>(group?.strategy ?? 'ringall');
  const [ringSeconds, setRingSeconds] = useState(group?.ring_seconds ?? 20);
  const [prefix, setPrefix] = useState(group?.callerid_prefix ?? '');
  const [members, setMembers] = useState<MemberRow[]>(() => toMemberRows(group?.members ?? []));
  const [externalInput, setExternalInput] = useState('');
  const [externalErr, setExternalErr] = useState<string | null>(null);
  const [noAnswer, setNoAnswer] = useState<Destination | null>(group ? { kind: group.no_answer_target.kind, targetId: group.no_answer_target.id } : null);

  // 0038 (FreePBX Ring Groups parity) — "Jiringlash va e'lonlar"/"Kengaytirilgan".
  const [announcementId, setAnnouncementId] = useState(group?.announcement?.id ?? '');
  const [ringStrategySound, setRingStrategySound] = useState<RingGroupStrategySound>(group?.ring_strategy_sound ?? 'ring');
  const [mohClassId, setMohClassId] = useState(group?.moh_class?.id ?? '');
  const [alertInfo, setAlertInfo] = useState(group?.alert_info ?? '');
  const [skipBusyAgent, setSkipBusyAgent] = useState(group?.skip_busy_agent ?? false);
  const [confirmCalls, setConfirmCalls] = useState(group?.confirm_calls ?? false);
  const [remoteAnnounceId, setRemoteAnnounceId] = useState(group?.remote_announce?.id ?? '');
  const [recordingPolicy, setRecordingPolicy] = useState<RingGroupRecordingPolicy>(group?.recording_policy ?? 'dontcare');

  const available = extensions.filter((e) => !members.some((m) => m.kind === 'extension' && m.ext.id === e.id));
  const valid = name.trim().length > 0 && members.length > 0 && !!noAnswer && noAnswer.kind !== 'external';
  const announcementAudio = audio.find((a) => a.id === announcementId);
  const remoteAnnounceAudio = audio.find((a) => a.id === remoteAnnounceId);

  const addExternal = () => {
    const normalized = normalizeNumber(externalInput.trim());
    if (!EXTERNAL_NUMBER.test(normalized)) { setExternalErr(t('error.externalFormat')); return; }
    if (members.some((m) => m.kind === 'external' && m.number === normalized)) { setExternalErr(t('error.externalDuplicate')); return; }
    setMembers((ms) => [...ms, { key: `ext_num:${normalized}:${Date.now()}`, kind: 'external', number: normalized }]);
    setExternalInput('');
    setExternalErr(null);
  };

  const submit = () => {
    if (!valid || !noAnswer) return;
    const memberInputs: RingGroupMemberInput[] = members.map((m) => (m.kind === 'extension' ? { extension_id: m.ext.id } : { external_number: m.number }));
    onSubmit({
      name: name.trim(), number: number.trim() || null, strategy, ring_seconds: ringSeconds, members: memberInputs,
      no_answer_target_id: noAnswer.targetId, callerid_prefix: prefix.trim() || null,
      announcement_audio_id: announcementId || undefined, announcement_audio_id_clear: !announcementId && !!group?.announcement,
      ring_strategy_sound: ringStrategySound,
      moh_class_id: mohClassId || undefined, moh_class_id_clear: !mohClassId && !!group?.moh_class,
      alert_info: alertInfo.trim() || undefined, alert_info_clear: !alertInfo.trim() && !!group?.alert_info,
      skip_busy_agent: skipBusyAgent, confirm_calls: confirmCalls,
      remote_announce_audio_id: remoteAnnounceId || undefined, remote_announce_audio_id_clear: !remoteAnnounceId && !!group?.remote_announce,
      recording_policy: recordingPolicy,
    });
  };

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={group ? t('form.editTitle', { name: group.name }) : t('form.newTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={submit}>{group ? t('save') : t('add')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errorMessage && errorField !== 'number' && errorField !== 'members' && <p className="text-sm text-danger">{errorMessage}</p>}

        <h3 className="font-display text-base font-semibold">{t('form.section.general')}</h3>
        <Field label={t('form.nameLabel')} required hint={t('nameHint', { max: NAME_MAX })}>
          {(a) => <Input {...a} autoFocus maxLength={NAME_MAX} value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <NumberField value={number} onChange={setNumber} error={errorField === 'number' ? errorMessage : undefined} hint={t('form.numberHint')} />
        <Field label={t('form.strategyLabel')} required>
          {({ id }) => <Select id={id} value={strategy} onValueChange={(v) => setStrategy(v as RingGroupStrategy)} options={STRATEGIES.map((s) => ({ value: s, label: strategyLabel[s] }))} />}
        </Field>
        <Field label={t('form.ringSecondsLabel')} required>
          {(a) => <Input {...a} mono type="number" min={5} max={120} value={ringSeconds} onChange={(e) => setRingSeconds(Number(e.target.value))} />}
        </Field>

        <div className="flex flex-col gap-4 border-t border-line pt-4">
          <h3 className="font-display text-base font-semibold">{t('form.section.members')}</h3>
          <p className="mb-2 text-sm font-medium text-fg">{t('form.membersLabel')} <span className="text-muted">{t('form.membersCount', { count: members.length })}</span></p>
          {members.length === 0 ? (
            <p className="rounded-md border border-dashed border-line px-3 py-4 text-center text-sm text-muted">{t('form.noMembers')}</p>
          ) : (
            <SortableList
              items={members}
              onChange={setMembers}
              itemId={(m) => m.key}
              itemLabel={(m) => (m.kind === 'extension' ? m.ext.name : m.number)}
              label={t('form.membersListAriaLabel')}
              render={(m) => (
                <div className="flex min-w-0 flex-1 items-center justify-between gap-2">
                  {m.kind === 'extension' ? (
                    <span className="truncate text-sm">{m.ext.name} <span className="num text-muted">{m.ext.number}</span></span>
                  ) : (
                    <span className="flex items-center gap-1.5 truncate text-sm"><Phone aria-hidden className="size-3.5 text-muted" /> <span className="num">{m.number}</span> <span className="text-muted">({t('external')})</span></span>
                  )}
                  <Button size="sm" variant="ghost" onClick={() => setMembers((ms) => ms.filter((x) => x.key !== m.key))}>{t('form.remove')}</Button>
                </div>
              )}
            />
          )}
          {errorField === 'members' && errorMessage && <p className="mt-1.5 text-sm text-danger">{errorMessage}</p>}
          {available.length > 0 && (
            <div className="mt-2">
              <Select
                value="__add" onValueChange={(v) => { const ext = available.find((e) => e.id === v); if (ext) setMembers((ms) => [...ms, { key: `ext:${ext.id}`, kind: 'extension', ext }]); }}
                options={[{ value: '__add', label: t('form.addExtensionOption') }, ...available.map((e) => ({ value: e.id, label: `${e.name} (${e.number})` }))]}
              />
            </div>
          )}
          <div className="mt-2 flex items-start gap-2">
            <div className="flex-1">
              <Input value={externalInput} onChange={(e) => { setExternalInput(e.target.value); setExternalErr(null); }} placeholder={t('externalPlaceholder')} aria-label={t('externalInputAriaLabel')} />
              {externalErr && <p className="mt-1 text-sm text-danger">{externalErr}</p>}
            </div>
            <Button variant="secondary" onClick={addExternal} disabled={!externalInput.trim()}>{t('form.addExtensionAdd')}</Button>
          </div>
        </div>

        <div className="flex flex-col gap-4 border-t border-line pt-4">
          <h3 className="font-display text-base font-semibold">{t('form.section.ringingAnnounce')}</h3>
          <Field label={t('form.announcementLabel')} aside={t('form.optional')} hint={t('form.announcementHint')}>
            {({ id }) => (
              <Select
                id={id} value={announcementId || NONE} onValueChange={(v) => setAnnouncementId(v === NONE ? '' : v)}
                options={[{ value: NONE, label: t('form.none') }, ...audio.map((a) => ({ value: a.id, label: a.name, hint: formatDurationMs(a.duration_ms) }))]}
              />
            )}
          </Field>
          {announcementAudio && <AudioPlayer variant="inline" src={() => apiClient.fetchAudio(announcementAudio.id)} seed={announcementAudio.name.length} />}

          <Field label={t('form.ringStrategySoundLabel')}>
            {({ id }) => (
              <Select
                id={id} value={ringStrategySound} onValueChange={(v) => setRingStrategySound(v as RingGroupStrategySound)}
                options={[{ value: 'ring', label: t('form.ringStrategySound.ring') }, { value: 'moh', label: t('form.ringStrategySound.moh') }]}
              />
            )}
          </Field>
          {ringStrategySound === 'moh' && (
            <Field label={t('form.mohClassLabel')}>
              {({ id }) => (
                <Select
                  id={id} value={mohClassId || NONE} onValueChange={(v) => setMohClassId(v === NONE ? '' : v)}
                  options={[{ value: NONE, label: t('form.mohClassNone') }, ...mohClasses.map((m) => ({ value: m.id, label: m.name }))]}
                />
              )}
            </Field>
          )}

          <Field label={t('form.alertInfoLabel')} aside={t('form.optional')} hint={t('form.alertInfoHint')}>
            {(a) => <Input {...a} value={alertInfo} onChange={(e) => setAlertInfo(e.target.value)} placeholder={t('form.alertInfoPlaceholder')} />}
          </Field>

          <Toggle checked={skipBusyAgent} onCheckedChange={setSkipBusyAgent} label={t('form.skipBusyAgentLabel')} description={t('form.skipBusyAgentDesc')} />
          <Toggle checked={confirmCalls} onCheckedChange={setConfirmCalls} label={t('form.confirmCallsLabel')} description={t('form.confirmCallsDesc')} />
          {confirmCalls && (
            <>
              <Field label={t('form.remoteAnnounceLabel')} aside={t('form.optional')} hint={t('form.remoteAnnounceHint')}>
                {({ id }) => (
                  <Select
                    id={id} value={remoteAnnounceId || NONE} onValueChange={(v) => setRemoteAnnounceId(v === NONE ? '' : v)}
                    options={[{ value: NONE, label: t('form.none') }, ...audio.map((a) => ({ value: a.id, label: a.name }))]}
                  />
                )}
              </Field>
              {remoteAnnounceAudio && <AudioPlayer variant="inline" src={() => apiClient.fetchAudio(remoteAnnounceAudio.id)} seed={remoteAnnounceAudio.name.length} />}
            </>
          )}
        </div>

        <div className="flex flex-col gap-4 border-t border-line pt-4">
          <h3 className="font-display text-base font-semibold">{t('form.section.callerId')}</h3>
          <Field label={t('form.prefixLabel')} aside={t('form.optional')} hint={t('form.prefixHint')}>
            {(a) => <Input {...a} value={prefix} onChange={(e) => setPrefix(e.target.value)} placeholder={t('form.prefixPlaceholder')} />}
          </Field>
        </div>

        <div className="flex flex-col gap-4 border-t border-line pt-4">
          <h3 className="font-display text-base font-semibold">{t('form.section.advanced')}</h3>
          <Field label={t('form.recordingPolicyLabel')}>
            {({ id }) => <Select id={id} value={recordingPolicy} onValueChange={(v) => setRecordingPolicy(v as RingGroupRecordingPolicy)} options={RECORDING_POLICIES.map((p) => ({ value: p, label: recordingLabel[p] }))} />}
          </Field>
          <DestinationPicker label={t('form.noAnswerLabel')} required kinds={['extension', 'ring_group', 'queue', 'ivr', 'time_condition', 'conference', 'hangup', 'busy', 'announcement', 'misc']} value={noAnswer} onChange={setNoAnswer} catalog={catalog} />
        </div>
      </div>
    </Drawer>
  );
}
