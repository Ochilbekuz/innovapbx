import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Download, HardDrive, RefreshCw, RotateCcw, ShieldAlert, Trash2 } from 'lucide-react';
import { useBackupJob, useBackupSettings, useBackups, useCreateBackup, useDeleteBackup, useDownloadBackup, useFetchBackupCopy } from '@/api/queries';
import { apiErrorMessage } from '@/api/errors';
import { BACKUP_COMPONENTS, BACKUP_KINDS, BACKUP_STATUSES, type Backup, type BackupComponent } from '@/api/types';
import { formatDateTimeShort } from '@/lib/time';
import { Button } from '@/ui/Button';
import { Modal } from '@/ui/Dialog';
import { ConfirmDeleteModal } from '@/ui/ConfirmDeleteModal';
import { Badge } from '@/ui/Status';
import { DataTable, queryState, type Column } from '@/ui/Table';
import { Checkbox } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';
import { useEnumText } from '@/lib/useEnumText';
import {
  backupFailedToast, backupFinishedToast, backupStatusTone, copyByTarget, copyStatusTone, COPY_TARGET_ORDER, canRestoreFrom, createBackupPayload,
  formatBytes, hasFetchableRemoteCopy, hasOkLocalCopy, nextScheduledAt, useCreateBackupForm,
} from './backupForms';
import { closeOnOpenChange } from '@/lib/formHelpers';
import { JobProgressBody } from './Progress';
import { RestoreRunner, type RestoreTarget } from './RestoreRunner';

type Translate = (k: string, o?: Record<string, unknown>) => string;

/** Oxirgi muvaffaqiyatli (yoki qisman) zaxira haqidagi qator — topilmasa "hech qachon". */
function lastBackupLine(t: Translate, backups: Backup[]): string {
  const lastOk = backups.find((b) => b.status === 'ok' || b.status === 'partial');
  return lastOk
    ? t('status.lastBackupLine', { when: formatDateTimeShort(lastOk.created_at), size: formatBytes(lastOk.size_bytes) })
    : t('status.never');
}

/** Keyingi rejalashtirilgan zaxira vaqti — jadval oʻchirilgan boʻlsa "oʻchirilgan" matni. */
function nextScheduledLine(t: Translate, settings: BackupSettingsLike | undefined): string {
  const next = settings ? nextScheduledAt(settings.schedule) : null;
  return settings?.schedule.enabled && next ? t('status.nextScheduled', { when: formatDateTimeShort(next.toISOString()) }) : t('status.scheduleOff');
}

type BackupSettingsLike = { schedule: Parameters<typeof nextScheduledAt>[0]; has_passphrase: boolean };

/** Parol hali oʻrnatilmagan boʻlsa (faqat boshqaruvchi uchun) — sozlamalarga oʻtish havolasi bilan ogohlantirish. */
function PassphraseWarning({ show, t, onGoToSettings }: { show: boolean; t: Translate; onGoToSettings: () => void }) {
  if (!show) return null;
  return (
    <p className="flex items-start gap-1.5 text-sm text-warning">
      <ShieldAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />
      <span>
        {t('status.passphraseWarning', { tab: t('tabs.settings') })}{' '}
        <button type="button" className="underline hover:no-underline" onClick={onGoToSettings}>{t('tabs.settings')}</button>
      </span>
    </p>
  );
}

/** Holat kartasi: oxirgi muvaffaqiyatli zaxira, keyingi rejalashtirilgan vaqt, parol ogohlantirishi. */
function StatusCard({ backups, canManage, onGoToSettings }: { backups: Backup[]; canManage: boolean; onGoToSettings: () => void }) {
  const { t } = useTranslation('backup');
  const { data: settings } = useBackupSettings();

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-line bg-surface p-4 shadow-card">
      <div className="flex items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-accent-soft text-on-accent-soft [&_svg]:size-4.5">
          <HardDrive aria-hidden />
        </span>
        <div>
          <h3 className="font-display text-base font-semibold">{t('status.title')}</h3>
          <p className="mt-0.5 text-sm text-muted">{lastBackupLine(t, backups)}</p>
          <p className="mt-0.5 text-sm text-muted">{nextScheduledLine(t, settings)}</p>
        </div>
      </div>
      <PassphraseWarning show={canManage && !!settings && !settings.has_passphrase} t={t} onGoToSettings={onGoToSettings} />
    </div>
  );
}

/** Nusxa holati chiplari — Lokal/S3/SFTP, tooltip orqali oʻlcham yoki xato. */
function CopyChips({ backup }: { backup: Backup }) {
  const { t } = useTranslation('backup');
  const targetLabel = useEnumText('backup', 'copyTarget', COPY_TARGET_ORDER);
  return (
    <div className="flex flex-wrap gap-1">
      {COPY_TARGET_ORDER.map((target) => {
        const copy = copyByTarget(backup, target);
        if (!copy) return null;
        const tooltip =
          copy.status === 'ok' ? t('table.copyTooltip.ok', { target: targetLabel[target], size: formatBytes(copy.size_bytes) }) :
          copy.status === 'failed' ? t('table.copyTooltip.failed', { target: targetLabel[target], error: copy.error ?? '' }) :
          copy.status === 'deleted' ? t('table.copyTooltip.deleted', { target: targetLabel[target] }) :
          t('table.copyTooltip.pending', { target: targetLabel[target] });
        return (
          <span key={target} title={tooltip}>
            <Badge tone={copyStatusTone(copy.status)}>{targetLabel[target]}</Badge>
          </span>
        );
      })}
    </div>
  );
}

/** «Hozir zaxiralash» modal — qismlar tanlovi va yuborilgandan keyingi progress. */
function CreateBackupModal({ open, onClose, onJobStarted }: { open: boolean; onClose: () => void; onJobStarted: (id: string) => void }) {
  const { t } = useTranslation('backup');
  const toast = useToast();
  const createM = useCreateBackup();
  const componentLabel = useEnumText('backup', 'components', BACKUP_COMPONENTS);
  const { components, toggle, reset } = useCreateBackupForm([...BACKUP_COMPONENTS]);

  const close = () => { createM.reset(); reset(); onClose(); };
  const submit = () => {
    createM.mutate(createBackupPayload(components), {
      onSuccess: (res) => { toast({ kind: 'success', title: t('job.startedToast') }); onJobStarted(res.job.id); close(); },
      onError: (e) => toast({ kind: 'error', title: t('job.failedToast', { error: apiErrorMessage(e) }) }),
    });
  };

  return (
    <Modal
      open={open}
      onOpenChange={(v) => closeOnOpenChange(v, close)}
      title={t('createModal.title')}
      footer={
        <>
          <Button variant="ghost" onClick={close}>{t('cancel')}</Button>
          <Button variant="primary" loading={createM.isPending} disabled={components.length === 0} onClick={submit}>
            {t('createModal.submit')}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <p className="text-sm font-medium text-fg">{t('componentsLabel')}</p>
        <div className="flex flex-col gap-2">
          {BACKUP_COMPONENTS.map((c) => (
            <label key={c} className="flex items-center gap-2 text-sm">
              <Checkbox checked={components.includes(c)} onCheckedChange={() => toggle(c)} aria-label={componentLabel[c]} />
              {componentLabel[c]}
            </label>
          ))}
        </div>
        {components.includes('recordings') && <p className="text-sm text-muted">{t('componentsHint')}</p>}
      </div>
    </Modal>
  );
}

type BackupJobQuery = ReturnType<typeof useBackupJob>;
type BackupsQuery = ReturnType<typeof useBackups>;

/** Zaxiralash ishi tugaganda (ok/failed) mos toast chiqarib, bannerni yopadi. */
function useBackupJobCompletion(status: string | undefined, jobQ: BackupJobQuery, backupsQ: BackupsQuery, toast: ReturnType<typeof useToast>, onDone: () => void, t: Translate) {
  useEffect(() => {
    if (status === 'failed') {
      toast(backupFailedToast(jobQ.data?.error, t));
      onDone();
    }
    if (status !== 'ok') return;
    void backupsQ.refetch().then((res) => {
      toast(backupFinishedToast(res.data?.items[0]?.status, t));
      onDone();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);
}

/** Joriy zaxiralash ishi progress banneri — tugagach mos toast chiqarib yopiladi. */
function BackupJobBanner({ jobId, onDone }: { jobId: string; onDone: () => void }) {
  const { t } = useTranslation('backup');
  const toast = useToast();
  const jobQ = useBackupJob(jobId);
  const backupsQ = useBackups();
  const status = jobQ.data?.status;
  useBackupJobCompletion(status, jobQ, backupsQ, toast, onDone, t);

  if (status === 'ok' || status === 'failed') return null;

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-line bg-surface p-4 shadow-card">
      <p className="text-sm font-medium text-fg">{t('job.backupTitle')}</p>
      <JobProgressBody label={t('job.backupTitle')} jobData={jobQ.data} />
    </div>
  );
}

function DeleteBackupModal({ backup, onClose }: { backup: Backup | null; onClose: () => void }) {
  const { t } = useTranslation('backup');
  const toast = useToast();
  const deleteM = useDeleteBackup();
  return (
    <ConfirmDeleteModal
      open={!!backup}
      onClose={onClose}
      loading={deleteM.isPending}
      onConfirm={() => backup && deleteM.mutate(backup.id, { onSuccess: () => { toast({ kind: 'success', title: t('deletedToast') }); onClose(); } })}
      title={t('deleteModal.title')}
      body={t('deleteModal.body', { file: backup?.file_name ?? backup?.id ?? '' })}
      cancelLabel={t('cancel')}
      deleteLabel={t('delete')}
    />
  );
}

type RowHandlers = { onRestore: (b: Backup) => void; onDelete: (b: Backup) => void };

function BackupRowActions({ backup, canManage, handlers }: { backup: Backup; canManage: boolean; handlers: RowHandlers }) {
  const { t } = useTranslation('backup');
  const toast = useToast();
  const downloadM = useDownloadBackup();
  const fetchCopyM = useFetchBackupCopy();

  const download = () => downloadM.mutate(backup.id, {
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = backup.file_name ?? backup.id;
      a.click();
      URL.revokeObjectURL(url);
    },
    onError: (e) => toast({ kind: 'error', title: apiErrorMessage(e) }),
  });
  const fetchCopy = () => fetchCopyM.mutate(backup.id, {
    onSuccess: () => toast({ kind: 'success', title: t('table.fetchCopyOk') }),
    onError: (e) => toast({ kind: 'error', title: apiErrorMessage(e) }),
  });

  return (
    <div className="flex justify-end gap-1">
      {hasFetchableRemoteCopy(backup) && (
        <Button size="sm" variant="ghost" iconOnly icon={<RefreshCw />} aria-label={t('table.fetchCopy')} loading={fetchCopyM.isPending} onClick={fetchCopy} />
      )}
      {hasOkLocalCopy(backup) && (
        <Button size="sm" variant="ghost" iconOnly icon={<Download />} aria-label={t('download')} loading={downloadM.isPending} onClick={download} />
      )}
      {canManage && canRestoreFrom(backup) && (
        <Button size="sm" variant="ghost" iconOnly icon={<RotateCcw />} aria-label={t('table.restore')} onClick={() => handlers.onRestore(backup)} />
      )}
      {canManage && (
        <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('delete')} onClick={() => handlers.onDelete(backup)} />
      )}
    </div>
  );
}

function backupColumns(
  t: (k: string, o?: Record<string, unknown>) => string,
  kindLabel: Record<Backup['kind'], string>,
  statusLabel: Record<Backup['status'], string>,
  componentLabel: Record<BackupComponent, string>,
  canManage: boolean, handlers: RowHandlers,
): Column<Backup>[] {
  return [
    {
      key: 'created_at', header: t('table.column.created'), sortValue: (r) => r.created_at,
      cell: (r) => (
        <div>
          <span className="num text-sm">{formatDateTimeShort(r.created_at)}</span>
          <div><Badge tone={backupStatusTone(r.status)}>{statusLabel[r.status]}</Badge></div>
        </div>
      ),
    },
    { key: 'kind', header: t('table.column.kind'), cell: (r) => <span className="text-sm text-muted">{kindLabel[r.kind]}</span> },
    { key: 'components', header: t('table.column.components'), cell: (r) => <span className="text-sm text-muted">{r.components.map((c) => componentLabel[c]).join(', ')}</span> },
    { key: 'size', header: t('table.column.size'), cell: (r) => <span className="num text-sm text-muted">{formatBytes(r.size_bytes)}</span> },
    { key: 'copies', header: t('table.column.copies'), cell: (r) => <CopyChips backup={r} /> },
    { key: 'actions', header: '', align: 'right', cell: (r) => <BackupRowActions backup={r} canManage={canManage} handlers={handlers} /> },
  ];
}

/** Zaxiralar tabi — holat kartasi, «Hozir zaxiralash», roʻyxat va roʻyxatdan tiklash (shartnoma §3). */
export function BackupsTab({ canManage, onGoToSettings }: { canManage: boolean; onGoToSettings: () => void }) {
  const { t } = useTranslation('backup');
  const { data, isLoading, isError, refetch } = useBackups();
  const [createOpen, setCreateOpen] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<Backup | null>(null);
  const [restoring, setRestoring] = useState<RestoreTarget | null>(null);

  const kindLabel = useEnumText('backup', 'kind', BACKUP_KINDS);
  const statusLabel = useEnumText('backup', 'statusLabel', BACKUP_STATUSES);
  const componentLabel = useEnumText('backup', 'components', BACKUP_COMPONENTS);

  const backups = data?.items ?? [];
  const columns = backupColumns(t, kindLabel, statusLabel, componentLabel, canManage, {
    onRestore: (b) => setRestoring({ id: b.id, fileName: b.file_name ?? b.id }),
    onDelete: setDeleting,
  });

  return (
    <div className="flex flex-col gap-5">
      <StatusCard backups={backups} canManage={canManage} onGoToSettings={onGoToSettings} />

      {activeJobId && <BackupJobBanner jobId={activeJobId} onDone={() => setActiveJobId(null)} />}

      <div>
        <div className="mb-3 flex items-start justify-between gap-3">
          <div />
          {canManage && <Button icon={<HardDrive />} onClick={() => setCreateOpen(true)}>{t('status.createNow')}</Button>}
        </div>
        <DataTable
          caption={t('table.caption')}
          rows={backups}
          columns={columns}
          rowId={(r) => r.id}
          searchText={(r) => `${r.file_name ?? ''} ${kindLabel[r.kind]}`}
          state={queryState(isLoading, isError)}
          onRetry={() => void refetch()}
          empty={{ title: t('table.empty.title'), body: t('table.empty.body') }}
        />
      </div>

      <CreateBackupModal open={createOpen} onClose={() => setCreateOpen(false)} onJobStarted={setActiveJobId} />
      <DeleteBackupModal backup={deleting} onClose={() => setDeleting(null)} />
      <RestoreRunner target={restoring} onClose={() => setRestoring(null)} />
    </div>
  );
}
