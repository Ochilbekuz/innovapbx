import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pause, Pencil, Play, Plus, ShieldAlert, Trash2 } from 'lucide-react';
import { apiErrorMessage } from '@/api/errors';
import { useCampaigns, useCreateCampaign, useDeleteCampaign, useUpdateCampaign } from '@/api/queries';
import type { Campaign } from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import {
  campaignActions, campaignProgress, canEditCampaign, formatDays, formToPayload, formToUpdate, hhmm, type CampaignForm as FormState,
} from '@/domain/campaigns';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { ConfirmDeleteModal } from '@/ui/ConfirmDeleteModal';
import { DataTable, type Column } from '@/ui/Table';
import { useToast } from '@/ui/Toast';
import { CampaignDetail, CampaignStatusBadge } from './CampaignDetail';
import { CampaignForm } from './CampaignForm';
import { CampaignProgress } from './CampaignProgress';
import { useRunCampaign } from './useRunCampaign';

const DAY_KEYS = [1, 2, 3, 4, 5, 6, 7];

function QuickRun({ c, canManage }: { c: Campaign; canManage: boolean }) {
  const { t } = useTranslation('campaigns');
  const { run, busy } = useRunCampaign();
  const actions = campaignActions(c.status);
  if (actions.includes('pause')) {
    return <Button size="sm" variant="ghost" iconOnly icon={<Pause />} aria-label={t('actionAria.pause', { name: c.name })} disabled={!canManage} loading={busy(c)} onClick={() => run(c, 'pause')} />;
  }
  return (
    <Button
      size="sm" variant="ghost" iconOnly icon={<Play />} aria-label={t('actionAria.start', { name: c.name })}
      disabled={!canManage || !actions.includes('start') || c.stats.total === 0} loading={busy(c)} onClick={() => run(c, 'start')}
    />
  );
}

function NameCell({ c, onOpen }: { c: Campaign; onOpen: () => void }) {
  const { t } = useTranslation('campaigns');
  const what = c.mode === 'message'
    ? `${t('mode.message')} · ${c.audio_name ?? '—'}`
    : `${t('mode.connect')} ${t('targetArrow', { number: c.target_number })}`;
  return (
    <div className="flex min-w-0 flex-col">
      <button type="button" className="truncate text-left font-medium hover:underline focus-visible:underline focus-visible:outline-none" onClick={onOpen}>
        {c.name}
      </button>
      <span className="truncate text-xs text-muted">{what}</span>
    </div>
  );
}

function WindowCell({ c }: { c: Campaign }) {
  const { t } = useTranslation('campaigns');
  return (
    <div className="flex flex-col">
      <span className="num text-fg">{hhmm(c.window_start)}–{hhmm(c.window_end)}</span>
      <span className="text-xs text-muted">{formatDays(c.days, DAY_KEYS.map((d) => t(`day.${d}`)))}</span>
    </div>
  );
}

function RowActions({ c, canManage, onEdit, onDelete }: { c: Campaign; canManage: boolean; onEdit: () => void; onDelete: () => void }) {
  const { t } = useTranslation('campaigns');
  const locked = !canManage || !canEditCampaign(c.status);
  return (
    <div className="flex justify-end gap-1">
      <QuickRun c={c} canManage={canManage} />
      <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('actionAria.edit', { name: c.name })} disabled={locked} onClick={onEdit} />
      <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('actionAria.delete', { name: c.name })} disabled={locked} onClick={onDelete} />
    </div>
  );
}

const searchText = (c: Campaign) => `${c.name} ${c.audio_name ?? ''} ${c.target_number ?? ''}`;
const tableState = (loading: boolean, error: boolean) => (loading ? 'loading' : error ? 'error' : 'ready');

function ReadOnlyNotice() {
  const { t } = useTranslation('campaigns');
  return (
    <p className="mb-3 flex items-center gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2 text-sm text-muted">
      <ShieldAlert aria-hidden className="size-4 shrink-0" />
      {t('readOnlyNotice')}
    </p>
  );
}

/** O'chirish tasdig'i: muvaffaqiyatda `onDeleted(id)` — ochiq karta yopilishi uchun. */
function DeleteConfirm({ campaign, onClose, onDeleted }: { campaign: Campaign | null; onClose: () => void; onDeleted: (id: string) => void }) {
  const { t } = useTranslation('campaigns');
  const toast = useToast();
  const deleteM = useDeleteCampaign();
  const remove = (c: Campaign) => deleteM.mutate(c.id, {
    onSuccess: () => {
      toast({ kind: 'success', title: t('toast.deleted', { name: c.name }) });
      onDeleted(c.id);
      onClose();
    },
    onError: (e) => toast({ kind: 'error', title: t('toast.failed'), description: apiErrorMessage(e) }),
  });
  return (
    <ConfirmDeleteModal
      open={!!campaign}
      onClose={onClose}
      onConfirm={() => campaign && remove(campaign)}
      loading={deleteM.isPending}
      title={campaign ? t('deleteModal.title', { name: campaign.name }) : ''}
      body={t('deleteModal.body')}
      cancelLabel={t('cancel')}
      deleteLabel={t('delete')}
    />
  );
}

/** Yaratish/saqlash: muvaffaqiyatda forma yopiladi, yangi kampaniya kartasi ochiladi (raqam yuklash uchun). */
function useSubmitCampaign(editing: Campaign | 'new' | null, close: () => void, open: (id: string) => void) {
  const { t } = useTranslation('campaigns');
  const toast = useToast();
  const createM = useCreateCampaign();
  const updateM = useUpdateCampaign();
  const reset = () => { close(); createM.reset(); updateM.reset(); };
  const submit = (form: FormState) => {
    if (editing === 'new') {
      createM.mutate(formToPayload(form), { onSuccess: (res) => { reset(); open(res.item.id); toast({ kind: 'success', title: t('toast.added') }); } });
    } else if (editing) {
      updateM.mutate({ id: editing.id, payload: formToUpdate(form, editing.updated_at) }, { onSuccess: () => { reset(); toast({ kind: 'success', title: t('toast.saved') }); } });
    }
  };
  return { submit, reset, mutation: editing === 'new' ? createM : updateM };
}

type Translate = (key: string) => string;

/** Bo'sh holat va asboblar paneli — yaratish tugmasi faqat boshqaruv ruxsati bilan. */
function newActions(canManage: boolean, t: Translate, onNew: () => void) {
  const empty = { title: t('empty.title'), body: t('empty.body') };
  if (!canManage) return { empty };
  return {
    empty: { ...empty, action: <Button size="sm" onClick={onNew}>{t('empty.action')}</Button> },
    toolbar: <Button size="sm" variant="primary" icon={<Plus />} onClick={onNew}>{t('newCampaign')}</Button>,
  };
}

function EditorSlot({ editing, submitter }: { editing: Campaign | 'new' | null; submitter: ReturnType<typeof useSubmitCampaign> }) {
  if (!editing) return null;
  return (
    <CampaignForm
      campaign={editing === 'new' ? undefined : editing}
      pending={submitter.mutation.isPending}
      error={submitter.mutation.error}
      onClose={submitter.reset}
      onSubmit={submitter.submit}
    />
  );
}

/** S18 — kampaniyalar (avtoinformator / avtoterish): ro'yxat, jonli jarayon, yaratish, CSV import, boshqaruv. */
export function CampaignsPage() {
  const { t } = useTranslation('campaigns');
  const { data, isLoading, isError, refetch } = useCampaigns();
  const canManage = useCanEdit('apps');
  const [editing, setEditing] = useState<Campaign | 'new' | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<Campaign | null>(null);
  const form = useSubmitCampaign(editing, () => setEditing(null), setOpenId);
  const items = data?.items ?? [];
  const opened = items.find((c) => c.id === openId);

  const columns: Column<Campaign>[] = [
    { key: 'name', header: t('column.name'), sortValue: (c) => c.name, cell: (c) => <NameCell c={c} onOpen={() => setOpenId(c.id)} /> },
    { key: 'status', header: t('column.status'), sortValue: (c) => c.status, cell: (c) => <CampaignStatusBadge status={c.status} /> },
    { key: 'progress', header: t('column.progress'), width: '28%', sortValue: (c) => campaignProgress(c.stats), cell: (c) => <CampaignProgress stats={c.stats} /> },
    { key: 'window', header: t('column.window'), cell: (c) => <WindowCell c={c} /> },
    { key: 'actions', header: '', align: 'right', cell: (c) => <RowActions c={c} canManage={canManage} onEdit={() => setEditing(c)} onDelete={() => setDeleting(c)} /> },
  ];

  return (
    <AppShellPage title={t('title')}>
      <p className="mb-3 text-sm text-muted">{t('subtitle')}</p>
      {!canManage && <ReadOnlyNotice />}
      <DataTable
        caption={t('caption')}
        rows={items}
        columns={columns}
        rowId={(c) => c.id}
        searchText={searchText}
        state={tableState(isLoading, isError)}
        onRetry={() => void refetch()}
        onRowOpen={(c) => setOpenId(c.id)}
        {...newActions(canManage, t, () => setEditing('new'))}
      />
      {opened && !editing && (
        <CampaignDetail campaign={opened} canManage={canManage} onEdit={() => setEditing(opened)} onClose={() => setOpenId(null)} />
      )}
      <EditorSlot editing={editing} submitter={form} />
      <DeleteConfirm campaign={deleting} onClose={() => setDeleting(null)} onDeleted={(id) => openId === id && setOpenId(null)} />
    </AppShellPage>
  );
}
