import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Moon, Pencil, Plus, ShieldAlert, Sun, Trash2 } from 'lucide-react';
import { useCreateDayNight, useDayNight, useDeleteDayNight, useTargets, useToggleDayNight, useUpdateDayNight } from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { DayNight, Usage } from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { toCatalog } from '@/pbx/catalog';
import { DestinationPicker } from '@/pbx/DestinationPicker';
import { applyToast } from '@/lib/applyToast';
import { usagesOf } from '@/lib/usageError';
import { UsageList } from '@/pbx/UsageList';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Drawer, Modal } from '@/ui/Dialog';
import { Field, Input } from '@/ui/Field';
import { DataTable, type Column } from '@/ui/Table';
import { Badge } from '@/ui/Status';
import { useToast } from '@/ui/Toast';
import type { Destination } from '@/domain/destination';

// Day/night manzili boshqa day_night/disa yoʻnaltirmasin — tsikllarni oldindan oldini olish (serverda ham tekshiriladi).
const TARGET_KINDS = ['extension', 'ring_group', 'queue', 'ivr', 'time_condition', 'conference', 'hangup', 'busy', 'announcement', 'misc'] as const;
const CODE_RE = /^[0-9]$/;
const PIN_RE = /^\d{4,8}$/;

/** M12 A1 — shartnomada S-raqam berilmagan. Kun/tun rejimi: *28N xizmat kodi orqali kunduzgi/tungi manzil almashtiriladi. */
export function DayNightPage() {
  const { t } = useTranslation('daynight');
  const { data, isLoading, isError, refetch } = useDayNight();
  const { data: targetsData } = useTargets({ kind: TARGET_KINDS.join(',') });
  const catalog = useMemo(() => toCatalog(targetsData?.items ?? []), [targetsData]);
  const canManage = useCanEdit('routing');
  const toast = useToast();
  const [editing, setEditing] = useState<DayNight | 'new' | null>(null);
  const [deleting, setDeleting] = useState<DayNight | null>(null);
  const [deleteErr, setDeleteErr] = useState<Usage[] | null>(null);

  const createM = useCreateDayNight();
  const updateM = useUpdateDayNight();
  const deleteM = useDeleteDayNight();
  const toggleM = useToggleDayNight();
  const close = () => { setEditing(null); createM.reset(); updateM.reset(); };
  const mutation = editing === 'new' ? createM : updateM;

  const columns: Column<DayNight>[] = [
    { key: 'name', header: t('column.name'), sortValue: (r) => r.name, cell: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'code', header: t('column.code'), cell: (r) => <span className="num text-muted">*28{r.code}</span> },
    {
      key: 'mode', header: t('column.mode'),
      cell: (r) => <Badge tone={r.mode === 'day' ? 'success' : 'neutral'}>{r.mode === 'day' ? t('modeDay') : t('modeNight')}</Badge>,
    },
    { key: 'dayTarget', header: t('column.dayTarget'), cell: (r) => <span className="truncate text-sm text-muted">{r.day_target.label}</span> },
    { key: 'nightTarget', header: t('column.nightTarget'), cell: (r) => <span className="truncate text-sm text-muted">{r.night_target.label}</span> },
    {
      key: 'actions', header: '', align: 'right', cell: (r) => (
        <div className="flex justify-end gap-1">
          <Button
            size="sm" variant="ghost" iconOnly disabled={!canManage} loading={toggleM.isPending && toggleM.variables === r.id}
            icon={r.mode === 'day' ? <Moon /> : <Sun />}
            aria-label={t('toggleAriaLabel', { name: r.name })}
            onClick={() => toggleM.mutate(r.id, {
              onSuccess: (res) => toast(applyToast(res.apply, t('toggled', { name: r.name, mode: res.item.mode === 'day' ? t('modeDay') : t('modeNight') }))),
              onError: (e) => toast({ kind: 'error', title: t('toast.toggleFailed'), description: e.message }),
            })}
          />
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
        searchText={(r) => `${r.name} *28${r.code}`}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        onRowOpen={canManage ? (r) => setEditing(r) : undefined}
        empty={{ title: t('empty.title'), body: t('empty.body'), action: canManage ? <Button size="sm" onClick={() => setEditing('new')}>{t('empty.action')}</Button> : undefined }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setEditing('new')}>{t('newRule')}</Button> : undefined}
      />

      {editing && (
        <DayNightForm
          rule={editing === 'new' ? undefined : editing}
          catalog={catalog}
          pending={mutation.isPending}
          errorField={isApiError(mutation.error) ? mutation.error.field : undefined}
          errorMessage={isApiError(mutation.error) ? mutation.error.message : undefined}
          onClose={close}
          onSubmit={(payload) => {
            if (editing === 'new') {
              createM.mutate(payload, { onSuccess: (res) => { close(); toast(applyToast(res.apply, t('toast.added'))); } });
            } else {
              updateM.mutate({ id: editing.id, payload: { ...payload, updated_at: editing.updated_at } }, {
                onSuccess: (res) => { close(); toast(applyToast(res.apply, t('toast.saved'))); },
              });
            }
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

function DayNightForm({
  rule, catalog, onClose, onSubmit, pending, errorField, errorMessage,
}: {
  rule?: DayNight;
  catalog: ReturnType<typeof toCatalog>;
  onClose: () => void;
  onSubmit: (payload: { name: string; code: string; day_target_id: string; night_target_id: string; pin?: string | null; pin_clear?: boolean }) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('daynight');
  const [name, setName] = useState(rule?.name ?? '');
  const [code, setCode] = useState(rule?.code ?? '');
  const [dayTarget, setDayTarget] = useState<Destination | null>(
    rule ? { kind: rule.day_target.kind, targetId: rule.day_target.id } : null,
  );
  const [nightTarget, setNightTarget] = useState<Destination | null>(
    rule ? { kind: rule.night_target.kind, targetId: rule.night_target.id } : null,
  );
  const [pin, setPin] = useState('');
  const [pinClear, setPinClear] = useState(false);

  const codeValid = CODE_RE.test(code);
  const pinValid = pin === '' || PIN_RE.test(pin);
  const valid = name.trim().length > 0 && codeValid && !!dayTarget && dayTarget.kind !== 'external'
    && !!nightTarget && nightTarget.kind !== 'external' && pinValid;

  const submit = () => {
    if (!dayTarget || dayTarget.kind === 'external' || !nightTarget || nightTarget.kind === 'external' || !valid) return;
    onSubmit({
      name: name.trim(), code, day_target_id: dayTarget.targetId, night_target_id: nightTarget.targetId,
      pin: pin || undefined, pin_clear: pinClear,
    });
  };

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={rule ? t('form.editTitle', { name: rule.name }) : t('form.newTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={submit}>{rule ? t('save') : t('add')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errorMessage && !['name', 'code', 'day_target_id', 'night_target_id', 'pin'].includes(errorField ?? '') && (
          <p className="text-sm text-danger">{errorMessage}</p>
        )}

        <Field label={t('form.nameLabel')} required error={errorField === 'name' ? errorMessage : undefined}>
          {(a) => <Input {...a} autoFocus value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>

        <Field label={t('form.codeLabel')} hint={t('form.codeHint')} required error={errorField === 'code' ? errorMessage : (code && !codeValid ? t('form.codeHint') : undefined)}>
          {(a) => (
            <div className="flex items-center gap-2">
              <span className="num text-muted">{t('form.codePrefix')}</span>
              <Input {...a} className="w-16" maxLength={1} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 1))} />
            </div>
          )}
        </Field>

        <DestinationPicker label={t('form.dayTargetLabel')} hint={t('form.dayTargetHint')} required kinds={[...TARGET_KINDS]} value={dayTarget} onChange={setDayTarget} catalog={catalog} />
        <DestinationPicker label={t('form.nightTargetLabel')} hint={t('form.nightTargetHint')} required kinds={[...TARGET_KINDS]} value={nightTarget} onChange={setNightTarget} catalog={catalog} />

        <Field label={t('form.pinLabel')} hint={t('form.pinHint')} error={errorField === 'pin' ? errorMessage : (pin && !pinValid ? t('form.pinHint') : undefined)}>
          {(a) => <Input {...a} type="password" inputMode="numeric" value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 8))} placeholder={rule?.has_pin ? '••••' : undefined} />}
        </Field>
        {rule?.has_pin && (
          <label className="flex items-center gap-2 text-sm text-muted">
            <input type="checkbox" checked={pinClear} onChange={(e) => setPinClear(e.target.checked)} />
            {t('form.pinClearLabel')}
          </label>
        )}
      </div>
    </Drawer>
  );
}
