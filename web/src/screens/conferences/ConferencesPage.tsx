import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pencil, Plus, ShieldAlert, Trash2, Users } from 'lucide-react';
import { useConferences, useCreateConference, useDeleteConference, useUpdateConference } from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { Conference, Usage } from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { applyToast } from '@/lib/applyToast';
import { usagesOf } from '@/lib/usageError';
import { UsageList } from '@/pbx/UsageList';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Drawer, Modal } from '@/ui/Dialog';
import { Field, Input } from '@/ui/Field';
import { Badge } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

// M2a — qarang ../../../replica/m2a-contract.md §4
const CONFERENCE_PIN_RE = /^\d{4,8}$/;

type FormState = {
  name: string; number: string;
  pinEnabled: boolean; pin: string;
  adminPinEnabled: boolean; adminPin: string;
  record: boolean;
  maxLimited: boolean; maxMembers: string;
};

function toForm(c?: Conference): FormState {
  return {
    name: c?.name ?? '', number: c?.number ?? '',
    pinEnabled: c?.has_pin ?? false, pin: '',
    adminPinEnabled: c?.has_admin_pin ?? false, adminPin: '',
    record: c?.record ?? false,
    maxLimited: c?.max_members != null, maxMembers: c?.max_members != null ? String(c.max_members) : '',
  };
}

/** Berilgan maydon qiymati toʻgʻrimi — boʻlsa yangi qiymat, boʻsh boʻlsa (va avval bor edi) oʻzgarmaydi. */
function secretValid(enabled: boolean, value: string, hadBefore: boolean): boolean {
  if (!enabled) return true;
  if (value.trim() !== '') return CONFERENCE_PIN_RE.test(value.trim());
  return hadBefore;
}
function secretPayload(enabled: boolean, value: string, hadBefore: boolean): string | null | undefined {
  if (!enabled) return hadBefore ? null : undefined;
  if (value.trim() !== '') return value.trim();
  return hadBefore ? undefined : null;
}

/** S25 — konferensiyalar: nom/raqam/PIN, hozirgi ishtirokchilar, yaratish/tahrirlash/oʻchirish (409 in_use). */
export function ConferencesPage() {
  const { t } = useTranslation('conferences');
  const { data, isLoading, isError, refetch } = useConferences();
  const canManage = useCanEdit('apps');
  const toast = useToast();
  const [editing, setEditing] = useState<Conference | 'new' | null>(null);
  const [deleting, setDeleting] = useState<Conference | null>(null);
  const [deleteErr, setDeleteErr] = useState<Usage[] | null>(null);

  const createM = useCreateConference();
  const updateM = useUpdateConference();
  const deleteM = useDeleteConference();
  const close = () => { setEditing(null); createM.reset(); updateM.reset(); };
  const mutation = editing === 'new' ? createM : updateM;

  const columns: Column<Conference>[] = [
    { key: 'name', header: t('column.name'), sortValue: (c) => c.name, cell: (c) => <span className="font-medium">{c.name}</span> },
    { key: 'number', header: t('column.number'), cell: (c) => <span className="num text-muted">{c.number}</span> },
    { key: 'pin', header: t('column.pin'), cell: (c) => <Badge tone={c.has_pin ? 'info' : 'neutral'}>{c.has_pin ? t('hasPin') : t('noPin')}</Badge> },
    {
      key: 'live', header: t('column.live'), cell: (c) => c.live.members > 0 ? (
        <span className="flex items-center gap-1.5 text-fg"><Users aria-hidden className="size-3.5 text-brand" /> {t('liveCount', { count: c.live.members })}</span>
      ) : <span className="text-muted">{t('liveNone')}</span>,
    },
    {
      key: 'actions', header: '', align: 'right', cell: (c) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('editAriaLabel', { name: c.name })} disabled={!canManage} onClick={() => setEditing(c)} />
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('deleteAriaLabel', { name: c.name })} disabled={!canManage} onClick={() => setDeleting(c)} />
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
        rowId={(c) => c.id}
        searchText={(c) => `${c.name} ${c.number}`}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        onRowOpen={canManage ? (c) => setEditing(c) : undefined}
        empty={{ title: t('empty.title'), body: t('empty.body'), action: canManage ? <Button size="sm" onClick={() => setEditing('new')}>{t('empty.action')}</Button> : undefined }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setEditing('new')}>{t('newConference')}</Button> : undefined}
      />

      {editing && (
        <ConferenceForm
          conference={editing === 'new' ? undefined : editing}
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

function ConferenceForm({
  conference, onClose, onSubmit, pending, errorField, errorMessage,
}: {
  conference?: Conference;
  onClose: () => void;
  onSubmit: (payload: { name: string; number?: string; pin?: string | null; admin_pin?: string | null; record: boolean; max_members: number | null }) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('conferences');
  const [form, setForm] = useState<FormState>(() => toForm(conference));
  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => setForm((f) => ({ ...f, [k]: v }));

  const pinValid = secretValid(form.pinEnabled, form.pin, conference?.has_pin ?? false);
  const adminPinValid = secretValid(form.adminPinEnabled, form.adminPin, conference?.has_admin_pin ?? false);
  const maxValid = !form.maxLimited || (/^\d+$/.test(form.maxMembers.trim()) && +form.maxMembers >= 2 && +form.maxMembers <= 100);
  const valid = form.name.trim().length > 0 && pinValid && adminPinValid && maxValid;

  const submit = () => {
    if (!valid) return;
    onSubmit({
      name: form.name.trim(),
      number: form.number.trim() || undefined,
      pin: secretPayload(form.pinEnabled, form.pin, conference?.has_pin ?? false),
      admin_pin: secretPayload(form.adminPinEnabled, form.adminPin, conference?.has_admin_pin ?? false),
      record: form.record,
      max_members: form.maxLimited ? Number(form.maxMembers.trim()) : null,
    });
  };

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={conference ? t('form.editTitle', { name: conference.name }) : t('form.newTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={submit}>{conference ? t('save') : t('add')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errorMessage && !['name', 'number', 'pin', 'admin_pin', 'max_members'].includes(errorField ?? '') && (
          <p className="text-sm text-danger">{errorMessage}</p>
        )}

        <Field label={t('form.nameLabel')} required error={errorField === 'name' ? errorMessage : undefined}>
          {(a) => <Input {...a} autoFocus value={form.name} onChange={(e) => set('name', e.target.value)} />}
        </Field>

        <Field label={t('form.numberLabel')} hint={t('form.numberHint')} error={errorField === 'number' ? errorMessage : undefined}>
          {(a) => <Input {...a} mono value={form.number} onChange={(e) => set('number', e.target.value)} />}
        </Field>

        <div className="flex flex-col gap-2">
          <Toggle checked={form.pinEnabled} onCheckedChange={(v) => set('pinEnabled', v)} label={t('form.pinLabel')} description={t('form.pinHint')} />
          {form.pinEnabled && (
            <Field label={t('form.pinLabel')} error={!pinValid ? t('error.badPin') : errorField === 'pin' ? errorMessage : undefined}>
              {(a) => <Input {...a} mono inputMode="numeric" maxLength={8} value={form.pin} onChange={(e) => set('pin', e.target.value)} />}
            </Field>
          )}
        </div>

        <div className="flex flex-col gap-2">
          <Toggle checked={form.adminPinEnabled} onCheckedChange={(v) => set('adminPinEnabled', v)} label={t('form.adminPinLabel')} description={t('form.adminPinHint')} />
          {form.adminPinEnabled && (
            <Field label={t('form.adminPinLabel')} error={!adminPinValid ? t('error.badPin') : errorField === 'admin_pin' ? errorMessage : undefined}>
              {(a) => <Input {...a} mono inputMode="numeric" maxLength={8} value={form.adminPin} onChange={(e) => set('adminPin', e.target.value)} />}
            </Field>
          )}
        </div>

        <Toggle checked={form.record} onCheckedChange={(v) => set('record', v)} label={t('form.recordLabel')} />

        <div className="flex flex-col gap-2">
          <Toggle checked={form.maxLimited} onCheckedChange={(v) => set('maxLimited', v)} label={t('form.maxMembersLabel')} description={t('form.maxMembersHint')} />
          {form.maxLimited ? (
            <Field label={t('form.maxMembersLabel')} error={!maxValid ? t('error.badMaxMembers') : errorField === 'max_members' ? errorMessage : undefined}>
              {(a) => <Input {...a} mono inputMode="numeric" maxLength={3} value={form.maxMembers} onChange={(e) => set('maxMembers', e.target.value)} />}
            </Field>
          ) : (
            <p className="text-sm text-muted">{t('form.maxMembersUnlimited')}</p>
          )}
        </div>
      </div>
    </Drawer>
  );
}
