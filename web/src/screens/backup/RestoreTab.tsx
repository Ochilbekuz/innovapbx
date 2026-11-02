import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CheckCircle2, RotateCcw, Upload, XCircle } from 'lucide-react';
import { useInspectBackup, useRestoreJobs, useUploadBackup } from '@/api/queries';
import { apiErrorMessage } from '@/api/errors';
import type { Backup, InspectBackupResult, RestoreJob } from '@/api/types';
import { formatDateTimeShort } from '@/lib/time';
import { useEnumText } from '@/lib/useEnumText';
import { Button } from '@/ui/Button';
import { Field, Input } from '@/ui/Field';
import { Badge } from '@/ui/Status';
import { DataTable, queryState, type Column } from '@/ui/Table';
import { useToast } from '@/ui/Toast';
import { restoreStatusTone, startedByLabel } from './backupForms';
import { RestoreRunner, type RestoreTarget } from './RestoreRunner';

type Stage = 'upload' | 'passphrase' | 'result';
type Translate = (k: string, o?: Record<string, unknown>) => string;

/** Bosqich 1 — `.ibk` faylni tanlash va yuklash. */
function UploadStage({
  file, uploading, onPick, onUpload, t,
}: { file: File | null; uploading: boolean; onPick: (f: File | null) => void; onUpload: () => void; t: Translate }) {
  const fileRef = useRef<HTMLInputElement>(null);
  return (
    <div className="flex items-center gap-2">
      <Button size="sm" variant="secondary" onClick={() => fileRef.current?.click()}>{file ? file.name : t('restore.upload.label')}</Button>
      <input
        ref={fileRef} type="file" accept=".ibk" className="sr-only" data-testid="restore-upload-input"
        onChange={(e) => onPick(e.target.files?.[0] ?? null)}
      />
      <Button size="sm" variant="primary" icon={<Upload />} disabled={!file} loading={uploading} onClick={onUpload}>
        {uploading ? t('restore.upload.uploading') : t('restore.upload.button')}
      </Button>
    </div>
  );
}

/** Bosqich 2 — ixtiyoriy parolni kiritib faylni tekshirish (`inspect`). */
function PassphraseStage({
  passphrase, setPassphrase, inspecting, onInspect, onCancel, t,
}: { passphrase: string; setPassphrase: (v: string) => void; inspecting: boolean; onInspect: () => void; onCancel: () => void; t: Translate }) {
  return (
    <div className="flex flex-col gap-3">
      <Field label={t('restore.passphraseLabel')} hint={t('restore.passphraseHint')}>
        {(a) => <Input {...a} type="password" value={passphrase} onChange={(e) => setPassphrase(e.target.value)} />}
      </Field>
      <div className="flex items-center gap-2">
        <Button variant="primary" loading={inspecting} onClick={onInspect}>
          {inspecting ? t('restore.inspect.inspecting') : t('restore.inspect.button')}
        </Button>
        <Button variant="ghost" onClick={onCancel}>{t('cancel')}</Button>
      </div>
    </div>
  );
}

const COMPATIBILITY_VARIANT = {
  yes: { cls: 'flex items-center gap-1.5 text-sm text-success', Icon: CheckCircle2, key: 'restore.inspect.compatible' },
  no: { cls: 'flex items-center gap-1.5 text-sm text-danger', Icon: XCircle, key: 'restore.inspect.incompatible' },
} as const;

/** Muvofiqlik qatori — ikon/rang/matn bitta lookupdan olinadi (koʻp ternary oʻrniga). */
function CompatibilityLine({ compatible, t }: { compatible: boolean; t: Translate }) {
  const v = COMPATIBILITY_VARIANT[compatible ? 'yes' : 'no'];
  const Icon = v.Icon;
  return (
    <p className={v.cls}>
      <Icon aria-hidden className="size-4 shrink-0" />
      {t(v.key)}
    </p>
  );
}

/** Inspect ogohlantirishlari roʻyxati — boʻsh boʻlsa hech narsa chiqmaydi. */
function WarningsList({ warnings, t }: { warnings: string[]; t: Translate }) {
  if (warnings.length === 0) return null;
  return (
    <div>
      <p className="text-sm font-medium text-warning">{t('restore.inspect.warningsTitle')}</p>
      <ul className="list-disc pl-5 text-sm text-muted">{warnings.map((w) => <li key={w}>{w}</li>)}</ul>
    </div>
  );
}

/** Tekshirish natijasidagi muvofiqlik va ogohlantirishlar qatori. */
function ResultCompatibility({ result, t }: { result: InspectBackupResult; t: Translate }) {
  return (
    <>
      <CompatibilityLine compatible={result.compatible} t={t} />
      <WarningsList warnings={result.warnings} t={t} />
    </>
  );
}

/** Bosqich 3 — inspect natijasi (manifest, muvofiqlik, ogohlantirishlar) va «Davom etish». */
function ResultStage({
  result, componentLabel, canManage, onContinue, onCancel, t,
}: {
  result: InspectBackupResult; componentLabel: Record<string, string>; canManage: boolean;
  onContinue: () => void; onCancel: () => void; t: Translate;
}) {
  return (
    <div className="flex flex-col gap-3">
      <h4 className="font-display text-sm font-semibold">{t('restore.inspect.resultTitle')}</h4>
      <dl className="grid grid-cols-2 gap-2 text-sm">
        <div><dt className="text-muted">{t('restore.inspect.createdAt')}</dt><dd className="num">{formatDateTimeShort(result.manifest.created_at)}</dd></div>
        <div><dt className="text-muted">{t('restore.inspect.version')}</dt><dd className="num">{result.manifest.product_version}</dd></div>
        <div><dt className="text-muted">{t('restore.inspect.host')}</dt><dd>{result.manifest.source_host}</dd></div>
        <div><dt className="text-muted">{t('restore.inspect.components')}</dt><dd>{result.manifest.components.map((c) => componentLabel[c]).join(', ')}</dd></div>
      </dl>
      <ResultCompatibility result={result} t={t} />
      {canManage && (
        <div className="flex items-center gap-2">
          <Button variant="danger" disabled={!result.compatible} onClick={onContinue}>{t('restore.inspect.continue')}</Button>
          <Button variant="ghost" onClick={onCancel}>{t('cancel')}</Button>
        </div>
      )}
    </div>
  );
}

/** `UploadInspectFlow`'ning holati va `upload`/`inspect`/`reset` mantiqi — bitta hookka ajratilgan,
 * shu bilan ularning ichidagi `onSuccess`/`onError` shartlari komponentning oʻz CC'siga qoʻshilmaydi. */
function useUploadInspectFlow(toast: ReturnType<typeof useToast>, t: Translate) {
  const uploadM = useUploadBackup();
  const inspectM = useInspectBackup();
  const [file, setFile] = useState<File | null>(null);
  const [uploaded, setUploaded] = useState<Backup | null>(null);
  const [passphrase, setPassphrase] = useState('');
  const [result, setResult] = useState<InspectBackupResult | null>(null);

  const reset = () => { setFile(null); setUploaded(null); setPassphrase(''); setResult(null); uploadM.reset(); inspectM.reset(); };

  const upload = () => {
    if (!file) return;
    uploadM.mutate(file, {
      onSuccess: (res) => { setUploaded(res.item); toast({ kind: 'success', title: t('restore.upload.uploaded') }); },
      onError: (e) => toast({ kind: 'error', title: apiErrorMessage(e) }),
    });
  };
  const inspect = () => {
    if (!uploaded) return;
    inspectM.mutate({ id: uploaded.id, payload: passphrase ? { passphrase } : {} }, {
      onSuccess: setResult,
      onError: (e) => toast({ kind: 'error', title: apiErrorMessage(e) }),
    });
  };

  return { uploadM, inspectM, file, setFile, uploaded, passphrase, setPassphrase, result, reset, upload, inspect };
}

/** Joriy bosqich — natija bor boʻlsa `result`, fayl yuklangan boʻlsa `passphrase`, aks holda `upload`. */
function uploadStage(result: InspectBackupResult | null, uploaded: Backup | null): Stage {
  if (result) return 'result';
  if (uploaded) return 'passphrase';
  return 'upload';
}

/** Joriy bosqichga mos komponentni tanlab chiqaradi — `UploadInspectFlow`'ning render shartlarini oʻziga oladi. */
function StageContent({
  stage, canManage, flow, componentLabel, onRestore, t,
}: {
  stage: Stage; canManage: boolean; flow: ReturnType<typeof useUploadInspectFlow>;
  componentLabel: Record<string, string>; onRestore: (uploaded: Backup) => void; t: Translate;
}) {
  if (stage === 'upload') {
    return canManage ? <UploadStage file={flow.file} uploading={flow.uploadM.isPending} onPick={flow.setFile} onUpload={flow.upload} t={t} /> : null;
  }
  if (stage === 'passphrase') {
    return (
      <PassphraseStage
        passphrase={flow.passphrase} setPassphrase={flow.setPassphrase} inspecting={flow.inspectM.isPending}
        onInspect={flow.inspect} onCancel={flow.reset} t={t}
      />
    );
  }
  if (!flow.result || !flow.uploaded) return null;
  return (
    <ResultStage
      result={flow.result} componentLabel={componentLabel} canManage={canManage}
      onContinue={() => onRestore(flow.uploaded as Backup)} onCancel={flow.reset} t={t}
    />
  );
}

/** Fayl yuklash → parol → inspect → tasdiqlash (`RestoreRunner`'ga topshiriladi). Shartnoma §3. */
function UploadInspectFlow({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('backup');
  const toast = useToast();
  const flow = useUploadInspectFlow(toast, t);
  const [restoring, setRestoring] = useState<RestoreTarget | null>(null);
  const componentLabel = useEnumText('backup', 'components', ['config', 'history', 'sounds', 'voicemail', 'recordings', 'certs'] as const);
  const stage = uploadStage(flow.result, flow.uploaded);

  return (
    <section className="flex max-w-2xl flex-col gap-4 rounded-lg border border-line bg-surface p-4 shadow-card">
      <p className="text-sm text-muted">{t('restore.intro')}</p>
      <StageContent
        stage={stage} canManage={canManage} flow={flow} componentLabel={componentLabel} t={t}
        onRestore={(uploaded) => setRestoring({ id: uploaded.id, fileName: uploaded.file_name ?? uploaded.id })}
      />
      <RestoreRunner target={restoring} initialPassphrase={flow.passphrase} onClose={() => { setRestoring(null); flow.reset(); }} />
    </section>
  );
}

function restoreHistoryColumns(
  t: (k: string, o?: Record<string, unknown>) => string,
  sourceLabel: Record<RestoreJob['source'], string>,
  statusLabel: Record<RestoreJob['status'], string>,
  onUndo: (backupId: string) => void,
): Column<RestoreJob>[] {
  return [
    { key: 'started_at', header: t('restore.history.column.startedAt'), sortValue: (r) => r.started_at, cell: (r) => <span className="num text-sm">{formatDateTimeShort(r.started_at)}</span> },
    { key: 'source', header: t('restore.history.column.source'), cell: (r) => <span className="text-sm text-muted">{sourceLabel[r.source]}</span> },
    { key: 'status', header: t('restore.history.column.status'), cell: (r) => <Badge tone={restoreStatusTone(r.status)}>{statusLabel[r.status]}</Badge> },
    { key: 'who', header: t('restore.history.column.who'), cell: (r) => <span className="text-sm text-muted">{startedByLabel(r, t('restore.history.unknownUser'))}</span> },
    {
      key: 'result',
      header: t('restore.history.column.result'),
      align: 'right',
      cell: (r) => {
        if (r.status === 'failed') return <span className="text-sm text-danger">{r.error}</span>;
        if (r.status === 'ok' && r.pre_restore_backup_id) {
          return (
            <Button size="sm" variant="ghost" icon={<RotateCcw />} onClick={() => onUndo(r.pre_restore_backup_id as string)}>
              {t('restore.history.preRestoreLink')}
            </Button>
          );
        }
        return <span className="text-sm text-muted">—</span>;
      },
    },
  ];
}

function RestoreHistory() {
  const { t } = useTranslation('backup');
  const { data, isLoading, isError, refetch } = useRestoreJobs();
  const [undoTarget, setUndoTarget] = useState<RestoreTarget | null>(null);
  const sourceLabel = useEnumText('backup', 'restore.history.sourceLabel', ['local', 'upload'] as const);
  const statusLabel = useEnumText('backup', 'restore.history.statusLabel', ['running', 'ok', 'failed'] as const);
  const items = data?.items ?? [];
  const columns = restoreHistoryColumns(t, sourceLabel, statusLabel, (backupId) => setUndoTarget({ id: backupId, fileName: backupId }));
  return (
    <div>
      <h4 className="mb-2 font-display text-sm font-semibold">{t('restore.history.title')}</h4>
      <DataTable
        caption={t('restore.history.title')} rows={items} columns={columns} rowId={(r) => r.id}
        searchText={(r) => `${sourceLabel[r.source]} ${statusLabel[r.status]}`}
        state={queryState(isLoading, isError)} onRetry={() => void refetch()}
        empty={{ title: t('restore.history.empty'), body: '' }}
      />
      <RestoreRunner target={undoTarget} onClose={() => setUndoTarget(null)} />
    </div>
  );
}

/** «Fayldan tiklash» tabi — yuklash→parol→inspect→tasdiqlash oqimi va tiklash tarixi (shartnoma §3). */
export function RestoreTab({ canManage }: { canManage: boolean }) {
  return (
    <div className="flex flex-col gap-6">
      <UploadInspectFlow canManage={canManage} />
      <RestoreHistory />
    </div>
  );
}
