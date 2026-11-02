import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pencil, Plus, ShieldAlert, Trash2, X } from 'lucide-react';
import { apiClient } from '@/api';
import { useAudio, useCreateIvr, useDeleteIvr, useIvrs, useTargets, useUpdateIvr } from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { Ivr } from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { applyToast } from '@/lib/applyToast';
import { formatDurationMs } from '@/lib/time';
import { usagesOf } from '@/lib/usageError';
import { resolveDestination, type Catalog, type Destination } from '@/domain/destination';
import { AudioPlayer } from '@/pbx/AudioPlayer';
import { DestinationPicker } from '@/pbx/DestinationPicker';
import { toCatalog } from '@/pbx/catalog';
import { NumberField } from '@/pbx/NumberField';
import { UsageList } from '@/pbx/UsageList';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Drawer, Modal } from '@/ui/Dialog';
import { Field, Input, Select } from '@/ui/Field';
import { Badge } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

const NAME_MAX = 60;
const DIGITS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '0', '#'];
const M1A_TARGETS = ['extension', 'ring_group', 'queue', 'ivr', 'time_condition', 'conference', 'hangup', 'busy'] as const;

/** S09 — IVR: salomlashuv, raqamlar xaritasi (0–9 * #), kutish/takror, vaqt tugashi va notoʻgʻri tugma manzillari. */
export function IvrPage() {
  const { t } = useTranslation('ivr');
  const { data, isLoading, isError, refetch } = useIvrs();
  const { data: audio } = useAudio();
  const { data: targets } = useTargets({ kind: M1A_TARGETS.join(',') });
  const canManage = useCanEdit('routing');
  const toast = useToast();
  const [editing, setEditing] = useState<Ivr | 'new' | null>(null);
  const [deleting, setDeleting] = useState<Ivr | null>(null);
  const [deleteErr, setDeleteErr] = useState<ReturnType<typeof usagesOf> | null>(null);

  const createM = useCreateIvr();
  const updateM = useUpdateIvr();
  const deleteM = useDeleteIvr();
  const close = () => { setEditing(null); createM.reset(); updateM.reset(); };
  const mutation = editing === 'new' ? createM : updateM;
  const catalog: Catalog = useMemo(() => toCatalog(targets?.items ?? []), [targets]);

  const columns: Column<Ivr>[] = [
    { key: 'name', header: t('column.name'), sortValue: (r) => r.name, cell: (r) => <span className="block max-w-[240px] truncate font-medium" title={r.name}>{r.name}</span> },
    { key: 'number', header: t('column.number'), cell: (r) => <span className="num text-muted">{r.number ?? '—'}</span> },
    { key: 'greeting', header: t('column.greeting'), cell: (r) => <span className="truncate text-sm text-muted">{r.greeting.name}</span> },
    { key: 'options', header: t('column.options'), cell: (r) => <Badge tone="accent" mono>{r.options.length}</Badge> },
    { key: 'timeout', header: t('column.timeout'), cell: (r) => <span className="truncate text-sm text-muted">{r.timeout_target.label}</span> },
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
          title: t('empty.title'), action: canManage ? <Button size="sm" disabled={!audio?.items.length} onClick={() => setEditing('new')}>{t('empty.action')}</Button> : undefined,
          body: audio?.items.length ? t('empty.bodyWithAudio') : t('empty.bodyNoAudio'),
        }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} disabled={!audio?.items.length} onClick={() => setEditing('new')}>{t('newIvr')}</Button> : undefined}
      />

      {editing && (
        <IvrDrawer
          ivr={editing === 'new' ? undefined : editing}
          audio={audio?.items ?? []}
          catalog={catalog}
          pending={mutation.isPending}
          errorField={isApiError(mutation.error) ? mutation.error.field : undefined}
          errorMessage={isApiError(mutation.error) ? mutation.error.message : undefined}
          errorDetails={isApiError(mutation.error) ? mutation.error.details : undefined}
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

type IvrFormState = {
  name: string; number: string; greetingId: string; invalidAudioId: string;
  timeoutSeconds: number; repeats: number; directDial: boolean;
  digits: Partial<Record<string, Destination>>; timeoutTarget: Destination | null; invalidTarget: Destination | null;
};

function IvrDrawer({
  ivr, audio, catalog, onClose, onSubmit, pending, errorField, errorMessage, errorDetails,
}: {
  ivr?: Ivr;
  audio: { id: string; name: string; duration_ms: number }[];
  catalog: Catalog;
  onClose: () => void;
  onSubmit: (payload: {
    name: string; number: string | null; greeting_audio_id: string; invalid_audio_id: string | null;
    timeout_seconds: number; repeats: number; direct_dial: boolean;
    options: { digit: string; target_id: string }[]; timeout_target_id: string; invalid_target_id: string;
  }) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
  errorDetails?: Record<string, unknown>;
}) {
  const { t } = useTranslation('ivr');
  const [form, setForm] = useState<IvrFormState>(() => ({
    name: ivr?.name ?? '', number: ivr?.number ?? '', greetingId: ivr?.greeting.id ?? audio[0]?.id ?? '', invalidAudioId: ivr?.invalid_audio?.id ?? '',
    timeoutSeconds: ivr?.timeout_seconds ?? 10, repeats: ivr?.repeats ?? 2, directDial: ivr?.direct_dial ?? false,
    digits: Object.fromEntries((ivr?.options ?? []).map((o) => [o.digit, { kind: o.target.kind, targetId: o.target.id } as Destination])),
    timeoutTarget: ivr ? { kind: ivr.timeout_target.kind, targetId: ivr.timeout_target.id } : null,
    invalidTarget: ivr ? { kind: ivr.invalid_target.kind, targetId: ivr.invalid_target.id } : null,
  }));
  const set = <K extends keyof IvrFormState>(k: K, v: IvrFormState[K]) => setForm((f) => ({ ...f, [k]: v }));
  const setDigit = (d: string, dest: Destination | null) => setForm((f) => { const digits = { ...f.digits }; if (dest) digits[d] = dest; else delete digits[d]; return { ...f, digits }; });

  const greetingAudio = audio.find((a) => a.id === form.greetingId);
  const timeoutOk = resolveDestination(form.timeoutTarget, catalog).state === 'ok';
  const invalidOk = resolveDestination(form.invalidTarget, catalog).state === 'ok';
  const mappedCount = Object.keys(form.digits).length;
  const loopPath = (errorDetails?.path as string[] | undefined) ?? null;
  const valid = form.name.trim().length > 0 && !!form.greetingId && timeoutOk && invalidOk && mappedCount > 0
    && Object.values(form.digits).every((d) => d && resolveDestination(d, catalog).state === 'ok');

  const submit = () => {
    if (!valid || !form.timeoutTarget || !form.invalidTarget || form.timeoutTarget.kind === 'external' || form.invalidTarget.kind === 'external') return;
    const options = Object.entries(form.digits)
      .filter(([, d]) => d && d.kind !== 'external')
      .map(([digit, d]) => ({ digit, target_id: (d as { targetId: string }).targetId }));
    onSubmit({
      name: form.name.trim(), number: form.number.trim() || null, greeting_audio_id: form.greetingId, invalid_audio_id: form.invalidAudioId || null,
      timeout_seconds: form.timeoutSeconds, repeats: form.repeats, direct_dial: form.directDial,
      options, timeout_target_id: form.timeoutTarget.targetId, invalid_target_id: form.invalidTarget.targetId,
    });
  };

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={ivr ? t('form.editTitle', { name: ivr.name }) : t('form.newTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={submit}>{ivr ? t('save') : t('add')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errorMessage && !loopPath && errorField !== 'number' && errorField !== 'options' && <p className="text-sm text-danger">{errorMessage}</p>}
        {loopPath && (
          <p className="rounded-md border border-danger/30 bg-danger-soft px-3 py-2.5 text-sm text-on-danger-soft">
            {errorMessage} {t('loopError.path')} <span className="font-medium">{loopPath.join(' → ')}</span>
          </p>
        )}
        <Field label={t('form.nameLabel')} required hint={t('form.nameHint', { max: NAME_MAX })}>
          {(a) => <Input {...a} autoFocus maxLength={NAME_MAX} value={form.name} onChange={(e) => set('name', e.target.value)} />}
        </Field>
        <NumberField value={form.number} onChange={(v) => set('number', v)} error={errorField === 'number' ? errorMessage : undefined} hint={t('form.numberHint')} />

        <Field label={t('form.greetingLabel')} required>
          {({ id }) => (
            <Select id={id} value={form.greetingId} onValueChange={(v) => set('greetingId', v)} options={audio.map((a) => ({ value: a.id, label: a.name, hint: formatDurationMs(a.duration_ms) }))} placeholder={t('form.choose')} />
          )}
        </Field>
        {greetingAudio && <AudioPlayer variant="inline" src={() => apiClient.fetchAudio(greetingAudio.id)} seed={greetingAudio.name.length} />}

        <Field label={t('form.invalidAudioLabel')} aside={t('form.invalidAudioAside')} hint={t('form.invalidAudioHint')}>
          {({ id }) => (
            <Select
              id={id} value={form.invalidAudioId || '__none'} onValueChange={(v) => set('invalidAudioId', v === '__none' ? '' : v)}
              options={[{ value: '__none', label: t('form.none') }, ...audio.map((a) => ({ value: a.id, label: a.name }))]}
            />
          )}
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label={t('form.timeoutSecondsLabel')} required>
            {(a) => <Input {...a} mono type="number" min={3} max={60} value={form.timeoutSeconds} onChange={(e) => set('timeoutSeconds', Number(e.target.value))} />}
          </Field>
          <Field label={t('form.repeatsLabel')} required>
            {(a) => <Input {...a} mono type="number" min={1} max={5} value={form.repeats} onChange={(e) => set('repeats', Number(e.target.value))} />}
          </Field>
        </div>
        <Toggle checked={form.directDial} onCheckedChange={(v) => set('directDial', v)} label={t('form.directDialLabel')} description={t('form.directDialDesc')} />

        <div>
          <p className="mb-2 text-sm font-medium text-fg">{t('form.digitMapLabel')} <span className="text-muted">{t('form.digitMapCount', { count: mappedCount })}</span></p>
          <div className={errorField === 'options' ? 'rounded-md border border-danger/40 p-2' : undefined}>
            <DigitPad digits={form.digits} catalog={catalog} onChange={setDigit} />
          </div>
          {errorField === 'options' && errorMessage && <p className="mt-1.5 text-sm text-danger">{errorMessage}</p>}
        </div>

        <DestinationPicker label={t('form.timeoutTargetLabel')} required kinds={['extension', 'ring_group', 'queue', 'ivr', 'time_condition', 'conference', 'hangup', 'busy']} value={form.timeoutTarget} onChange={(d) => set('timeoutTarget', d)} catalog={catalog} />
        <DestinationPicker label={t('form.invalidTargetLabel')} required kinds={['extension', 'ring_group', 'queue', 'ivr', 'time_condition', 'conference', 'hangup', 'busy']} value={form.invalidTarget} onChange={(d) => set('invalidTarget', d)} catalog={catalog} />
      </div>
    </Drawer>
  );
}

function DigitPad({ digits, catalog, onChange }: { digits: Partial<Record<string, Destination>>; catalog: Catalog; onChange: (d: string, dest: Destination | null) => void }) {
  const { t } = useTranslation('ivr');
  const [open, setOpen] = useState<string | null>(null);
  return (
    <div className="grid grid-cols-3 gap-2">
      {DIGITS.map((d) => {
        const dest = digits[d];
        const resolved = dest ? resolveDestination(dest, catalog) : null;
        return (
          <div key={d} className="flex flex-col gap-1 rounded-md border border-line bg-surface p-2">
            <div className="flex items-center justify-between">
              <span className="num flex size-6 items-center justify-center rounded-sm bg-surface-2 text-sm font-semibold text-fg">{d}</span>
              {dest && (
                <Button size="sm" variant="ghost" iconOnly icon={<X />} aria-label={t('form.clearDigitAriaLabel', { digit: d })} onClick={() => onChange(d, null)} />
              )}
            </div>
            {open === d ? (
              <DestinationPicker
                label={t('form.digitFieldLabel', { digit: d })} value={dest ?? null} catalog={catalog}
                kinds={['extension', 'ring_group', 'queue', 'ivr', 'time_condition', 'conference', 'hangup', 'busy']}
                onChange={(v) => { onChange(d, v); setOpen(null); }}
              />
            ) : (
              <button
                type="button" onClick={() => setOpen(d)}
                className="truncate rounded-sm px-1 py-1 text-left text-sm text-muted hover:bg-surface-2 hover:text-fg"
              >
                {resolved && resolved.state === 'ok' ? resolved.label : resolved?.state === 'broken' ? t('form.brokenTarget') : t('form.notBound')}
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
