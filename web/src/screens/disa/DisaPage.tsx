import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pencil, Plus, ShieldAlert, Trash2 } from 'lucide-react';
import { useCreateDisa, useDeleteDisa, useDisa, useUpdateDisa } from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { Disa, Usage } from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { applyToast } from '@/lib/applyToast';
import { usagesOf } from '@/lib/usageError';
import { UsageList } from '@/pbx/UsageList';
import { AppShellPage } from '@/shell/AppShellPage';
import { Badge } from '@/ui/Status';
import { Button } from '@/ui/Button';
import { Drawer, Modal } from '@/ui/Dialog';
import { Field, Input } from '@/ui/Field';
import { DataTable, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

const PIN_RE = /^\d{4,8}$/;

/** M12 A2 — shartnomada S-raqam berilmagan. DISA: tashqaridan PIN kiritib ichkariga kirish — chiquvchi marshrutlargagina. */
export function DisaPage() {
  const { t } = useTranslation('disa');
  const { data, isLoading, isError, refetch } = useDisa();
  const canManage = useCanEdit('apps');
  const toast = useToast();
  const [editing, setEditing] = useState<Disa | 'new' | null>(null);
  const [deleting, setDeleting] = useState<Disa | null>(null);
  const [deleteErr, setDeleteErr] = useState<Usage[] | null>(null);

  const createM = useCreateDisa();
  const updateM = useUpdateDisa();
  const deleteM = useDeleteDisa();
  const close = () => { setEditing(null); createM.reset(); updateM.reset(); };
  const mutation = editing === 'new' ? createM : updateM;

  const columns: Column<Disa>[] = [
    { key: 'name', header: t('column.name'), sortValue: (r) => r.name, cell: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'pin', header: t('column.pin'), cell: (r) => <Badge tone={r.has_pin ? 'success' : 'neutral'}>{r.has_pin ? t('pinSet') : t('pinNotSet')}</Badge> },
    { key: 'allowNoPin', header: t('column.allowNoPin'), cell: (r) => <span className="text-sm text-muted">{r.allow_no_pin ? t('yes') : t('no')}</span> },
    { key: 'attempts', header: t('column.attempts'), cell: (r) => <span className="num text-muted">{r.max_attempts}</span> },
    { key: 'enabled', header: t('column.enabled'), cell: (r) => <Badge tone={r.enabled ? 'success' : 'neutral'}>{r.enabled ? t('yes') : t('no')}</Badge> },
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
        searchText={(r) => r.name}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        onRowOpen={canManage ? (r) => setEditing(r) : undefined}
        empty={{ title: t('empty.title'), body: t('empty.body'), action: canManage ? <Button size="sm" onClick={() => setEditing('new')}>{t('empty.action')}</Button> : undefined }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setEditing('new')}>{t('newDisa')}</Button> : undefined}
      />

      {editing && (
        <DisaForm
          disa={editing === 'new' ? undefined : editing}
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

function DisaForm({
  disa, onClose, onSubmit, pending, errorField, errorMessage,
}: {
  disa?: Disa;
  onClose: () => void;
  onSubmit: (payload: {
    name: string; pin?: string | null; pin_clear?: boolean; allow_no_pin: boolean; cid_override: string | null;
    digit_timeout: number; response_timeout: number; max_attempts: number; enabled: boolean;
  }) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('disa');
  const [name, setName] = useState(disa?.name ?? '');
  const [pin, setPin] = useState('');
  const [pinClear, setPinClear] = useState(false);
  const [allowNoPin, setAllowNoPin] = useState(disa?.allow_no_pin ?? false);
  const [cidOverride, setCidOverride] = useState(disa?.cid_override ?? '');
  const [digitTimeout, setDigitTimeout] = useState(disa?.digit_timeout ?? 5);
  const [responseTimeout, setResponseTimeout] = useState(disa?.response_timeout ?? 10);
  const [maxAttempts, setMaxAttempts] = useState(disa?.max_attempts ?? 3);
  const [enabled, setEnabled] = useState(disa?.enabled ?? true);

  const pinValid = pin === '' || PIN_RE.test(pin);
  // Yangi yozuvda PIN yo'q bo'lsa — faqat allowNoPin=true bo'lsa ruxsat (brief: DISA'da PIN bo'sh bo'lsa faqat allow_no_pin=true).
  const willHavePin = disa ? (pin !== '' || (disa.has_pin && !pinClear)) : pin !== '';
  const pinOk = willHavePin || allowNoPin;
  const valid = name.trim().length > 0 && pinValid && pinOk && digitTimeout > 0 && responseTimeout > 0 && maxAttempts > 0;

  const submit = () => {
    if (!valid) return;
    onSubmit({
      name: name.trim(), pin: pin || undefined, pin_clear: pinClear, allow_no_pin: allowNoPin,
      cid_override: cidOverride.trim() || null, digit_timeout: digitTimeout, response_timeout: responseTimeout,
      max_attempts: maxAttempts, enabled,
    });
  };

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={disa ? t('form.editTitle', { name: disa.name }) : t('form.newTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={submit}>{disa ? t('save') : t('add')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errorMessage && !['name', 'pin', 'allow_no_pin'].includes(errorField ?? '') && (
          <p className="text-sm text-danger">{errorMessage}</p>
        )}

        <Field label={t('form.nameLabel')} required error={errorField === 'name' ? errorMessage : undefined}>
          {(a) => <Input {...a} autoFocus value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>

        <Field label={t('form.pinLabel')} hint={t('form.pinHint')} error={errorField === 'pin' ? errorMessage : (pin && !pinValid ? t('form.pinHint') : undefined)}>
          {(a) => <Input {...a} type="password" inputMode="numeric" value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 8))} placeholder={disa?.has_pin ? '••••' : undefined} />}
        </Field>
        {disa?.has_pin && (
          <label className="flex items-center gap-2 text-sm text-muted">
            <input type="checkbox" checked={pinClear} onChange={(e) => setPinClear(e.target.checked)} />
            {t('form.pinClearLabel')}
          </label>
        )}

        <Toggle checked={allowNoPin} onCheckedChange={setAllowNoPin} label={t('form.allowNoPinLabel')} description={t('form.allowNoPinDesc')} />
        {!pinOk && <p className="text-sm text-danger">{t('pinRequiredNotice')}</p>}

        <Field label={t('form.cidOverrideLabel')} hint={t('form.cidOverrideHint')} error={errorField === 'cid_override' ? errorMessage : undefined}>
          {(a) => <Input {...a} value={cidOverride} onChange={(e) => setCidOverride(e.target.value)} />}
        </Field>

        <Field label={t('form.digitTimeoutLabel')}>
          {(a) => <Input {...a} type="number" min={1} value={digitTimeout} onChange={(e) => setDigitTimeout(Number(e.target.value) || 0)} />}
        </Field>
        <Field label={t('form.responseTimeoutLabel')}>
          {(a) => <Input {...a} type="number" min={1} value={responseTimeout} onChange={(e) => setResponseTimeout(Number(e.target.value) || 0)} />}
        </Field>
        <Field label={t('form.maxAttemptsLabel')} hint={t('form.maxAttemptsHint')}>
          {(a) => <Input {...a} type="number" min={1} value={maxAttempts} onChange={(e) => setMaxAttempts(Number(e.target.value) || 0)} />}
        </Field>

        <Toggle checked={enabled} onCheckedChange={setEnabled} label={t('form.enabledLabel')} />
      </div>
    </Drawer>
  );
}
