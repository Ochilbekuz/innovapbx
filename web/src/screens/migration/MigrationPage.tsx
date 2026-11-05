import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, ShieldAlert, Trash2 } from 'lucide-react';
import type { MigrationJob } from '@/api/types';
import { useAnalyzeMigrationJob, useDeleteMigrationJob, useMigrationJob, useMigrationJobs } from '@/api/queries';
import { usePermission } from '@/auth/permissions';
import { AppShellPage } from '@/shell/AppShellPage';
import { formatDateTime } from '@/lib/time';
import { useEnumText } from '@/lib/useEnumText';
import { formatBytes } from '@/screens/backup/backupForms';
import { Badge } from '@/ui/Status';
import { Button } from '@/ui/Button';
import { ConfirmDeleteModal } from '@/ui/ConfirmDeleteModal';
import { DataTable, queryState, type Column } from '@/ui/Table';
import { useToast } from '@/ui/Toast';
import { cn } from '@/lib/cn';
import { migrationJobStatusTone, wizardStep, type WizardStep } from './migrationForms';
import { SourceStep } from './SourceStep';
import { AnalyzeStep } from './AnalyzeStep';
import { ReviewStep } from './ReviewStep';
import { ApplyStep } from './ApplyStep';
import { ResultStep } from './ResultStep';

const STEP_ORDER: WizardStep[] = ['source', 'analyze', 'review', 'apply', 'result'];

/** Kichik, oddiy bosqich ko'rsatkichi — mavjud `Stepper` ui komponenti yo'q (grep bilan tasdiqlangan). */
function WizardStepper({ current }: { current: WizardStep }) {
  const { t } = useTranslation('migration');
  const idx = STEP_ORDER.indexOf(current);
  return (
    <ol aria-label={t('title')} className="flex flex-wrap gap-x-1 gap-y-2 text-sm">
      {STEP_ORDER.map((s, i) => (
        <li key={s} className="flex items-center gap-1">
          <span
            className={cn(
              'flex items-center gap-1.5 rounded-pill px-2.5 py-1',
              i === idx && 'bg-accent-soft font-medium text-on-accent-soft',
              i < idx && 'text-success',
              i > idx && 'text-muted',
            )}
            aria-current={i === idx ? 'step' : undefined}
          >
            {i < idx ? <Check aria-hidden className="size-3.5" /> : <span className="num text-xs">{i + 1}</span>}
            {t(`steps.${s}`)}
          </span>
          {i < STEP_ORDER.length - 1 && <span aria-hidden className="text-muted/50">/</span>}
        </li>
      ))}
    </ol>
  );
}

function WizardBody({
  step, job, canManage, setReviewConfirmed, rotateWeakSecrets, setRotateWeakSecrets,
  confirmText, setConfirmText, onNewImport,
}: {
  step: WizardStep; job: MigrationJob | null; canManage: boolean;
  setReviewConfirmed: (v: boolean) => void;
  rotateWeakSecrets: boolean; setRotateWeakSecrets: (v: boolean) => void;
  confirmText: string; setConfirmText: (v: string) => void;
  onNewImport: () => void;
}) {
  const analyzeM = useAnalyzeMigrationJob();
  // Qo'llash 409 `plan_stale` qaytarsa — joriy ishni qayta tahlil qiladi (status `analyzed`dan ham
  // ishlaydi, qarang `api/fake.ts: analyzeMigrationJob`), Ko'rib chiqish bosqichiga qaytaradi.
  const reanalyze = () => {
    if (!job) return;
    analyzeM.mutate(job.id, {
      onSuccess: () => { setReviewConfirmed(false); setConfirmText(''); },
    });
  };

  if (step === 'source' || !job) return <SourceStep canManage={canManage} />;
  if (step === 'analyze') return <AnalyzeStep job={job} canManage={canManage} />;
  if (step === 'review') {
    return (
      <ReviewStep
        job={job} canManage={canManage} rotateWeakSecrets={rotateWeakSecrets} onRotateWeakSecretsChange={setRotateWeakSecrets}
        onContinue={() => setReviewConfirmed(true)}
      />
    );
  }
  if (step === 'apply') {
    return (
      <ApplyStep
        job={job} canManage={canManage} rotateWeakSecrets={rotateWeakSecrets}
        confirmText={confirmText} onConfirmTextChange={setConfirmText} onReanalyze={reanalyze}
      />
    );
  }
  return <ResultStep job={job} onNewImport={onNewImport} />;
}

function HistoryRowActions({ job, canManage }: { job: MigrationJob; canManage: boolean }) {
  const { t } = useTranslation('migration');
  const toast = useToast();
  const deleteM = useDeleteMigrationJob();
  const [confirming, setConfirming] = useState(false);
  if (!canManage || !job.source_meta?.file_name) return null;
  return (
    <>
      <Button size="sm" variant="ghost" iconOnly icon={<Trash2 aria-hidden className="size-3.5" />} aria-label={t('history.deleteConfirm.title')} onClick={() => setConfirming(true)} />
      <ConfirmDeleteModal
        open={confirming}
        onClose={() => setConfirming(false)}
        loading={deleteM.isPending}
        onConfirm={() => deleteM.mutate(job.id, { onSuccess: () => { toast({ kind: 'success', title: t('history.deletedToast') }); setConfirming(false); } })}
        title={t('history.deleteConfirm.title')}
        body={t('history.deleteConfirm.body')}
        cancelLabel={t('cancel')}
        deleteLabel={t('history.deleteConfirm.title')}
      />
    </>
  );
}

function HistoryTable({ jobs, loading, error, canManage }: { jobs: MigrationJob[]; loading: boolean; error: boolean; canManage: boolean }) {
  const { t } = useTranslation('migration');
  const statusText = useEnumText('migration', 'statusLabel', ['uploaded', 'analyzing', 'analyzed', 'applying', 'ok', 'failed'] as const);
  const sourceText = useEnumText('migration', 'sourceLabel', ['upload', 'ssh'] as const);

  const columns: Column<MigrationJob>[] = [
    { key: 'created', header: t('history.column.created'), cell: (r) => formatDateTime(r.created_at), sortValue: (r) => r.created_at },
    { key: 'source', header: t('history.column.source'), cell: (r) => sourceText[r.source] },
    { key: 'status', header: t('history.column.status'), cell: (r) => <Badge tone={migrationJobStatusTone(r.status)}>{statusText[r.status]}</Badge> },
    {
      key: 'summary',
      header: t('history.column.summary'),
      cell: (r) => (r.result ? `${Object.values(r.result.created).reduce((a, b) => a + (b ?? 0), 0)} / ${r.result.skipped} / ${r.result.warnings}`
        : r.source_meta?.size_bytes != null ? formatBytes(r.source_meta.size_bytes) : '—'),
    },
    { key: 'actions', header: '', cell: (r) => <HistoryRowActions job={r} canManage={canManage} /> },
  ];

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold text-fg">{t('history.title')}</h2>
      <DataTable
        caption={t('history.caption')}
        rows={jobs}
        columns={columns}
        rowId={(r) => r.id}
        searchText={(r) => `${r.source_meta?.file_name ?? ''} ${r.source_meta?.host ?? ''}`}
        state={queryState(loading, error)}
        empty={{ title: t('history.empty.title'), body: t('history.empty.body') }}
      />
    </section>
  );
}

/** S36 — /settings/migration: FreePBX'dan ko'chirish (M5a). Faqat `system.manage` huquqi bilan to'liq boshqariladi. */
export function MigrationPage() {
  const { t } = useTranslation('migration');
  const canManage = usePermission('*');
  const jobsQ = useMigrationJobs();
  const jobs = jobsQ.data?.items ?? [];
  const latestJob = jobs[0] ?? null;
  const jobQ = useMigrationJob(latestJob?.id ?? null);
  const job = jobQ.data?.item ?? latestJob;

  const [reviewConfirmed, setReviewConfirmed] = useState(false);
  const [rotateWeakSecrets, setRotateWeakSecrets] = useState(false);
  const [confirmText, setConfirmText] = useState('');
  const [dismissedResultId, setDismissedResultId] = useState<string | null>(null);

  const lastJobIdRef = useRef<string | null>(null);
  useEffect(() => {
    if (job?.id !== lastJobIdRef.current) {
      lastJobIdRef.current = job?.id ?? null;
      setReviewConfirmed(false);
      setRotateWeakSecrets(false);
      setConfirmText('');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.id]);

  const showingResult = job && (job.status === 'ok' || job.status === 'failed') && job.id !== dismissedResultId;
  const step: WizardStep = showingResult ? 'result' : wizardStep(job && job.status !== 'ok' && job.status !== 'failed' ? job : null, reviewConfirmed);
  const effectiveJob = step === 'source' && !showingResult ? null : job;

  return (
    <AppShellPage title={t('title')} crumbs={[t('title')]}>
      <div data-testid="migration-page" className="flex flex-col gap-8">
        {!canManage && (
          <p className="flex items-center gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2 text-sm text-muted">
            <ShieldAlert aria-hidden className="size-4 shrink-0" />
            {t('readOnlyBanner')}
          </p>
        )}

        <div className="flex flex-col gap-6 rounded-lg border border-line bg-surface p-4 shadow-card sm:p-6">
          <WizardStepper current={step} />
          <WizardBody
            step={step} job={effectiveJob} canManage={canManage}
            setReviewConfirmed={setReviewConfirmed}
            rotateWeakSecrets={rotateWeakSecrets} setRotateWeakSecrets={setRotateWeakSecrets}
            confirmText={confirmText} setConfirmText={setConfirmText}
            onNewImport={() => { if (job) setDismissedResultId(job.id); }}
          />
        </div>

        <HistoryTable jobs={jobs} loading={jobsQ.isLoading} error={jobsQ.isError} canManage={canManage} />
      </div>
    </AppShellPage>
  );
}
