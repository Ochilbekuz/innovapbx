import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { CircleCheck, CircleX, Download } from 'lucide-react';
import { MIGRATION_KINDS, type MigrationJob } from '@/api/types';
import { useMigrationReport } from '@/api/queries';
import { useEnumText } from '@/lib/useEnumText';
import { Button } from '@/ui/Button';

function triggerDownload(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
}

/** Sehrgarning 5-bosqichi: natija (yaratildi/o'tkazib yuborildi/ogohlantirish), CSV hisobot,
 * `pre_import` zaxirasiga bekor qilish havolasi, yoki muvaffaqiyatsizlik xabari. */
export function ResultStep({ job, onNewImport }: { job: MigrationJob; onNewImport: () => void }) {
  const { t } = useTranslation('migration');
  const kindText = useEnumText('migration', 'kind', MIGRATION_KINDS);
  const reportM = useMigrationReport();

  const downloadReport = () => reportM.mutate(job.id, {
    onSuccess: (blob) => triggerDownload(blob, `migration-${job.id}.csv`),
  });

  if (job.status === 'failed') {
    return (
      <section data-testid="migration-result-step" className="flex max-w-md flex-col gap-4">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-danger">
          <CircleX aria-hidden className="size-5" />
          {t('result.titleFailed')}
        </h2>
        <p className="text-sm text-muted">{job.error ? `${t('result.errorLabel')}: ${job.error.message}` : null}</p>
        <div><Button variant="primary" onClick={onNewImport}>{t('result.newImportButton')}</Button></div>
      </section>
    );
  }

  const result = job.result;
  const createdEntries = result ? Object.entries(result.created).filter(([, n]) => (n ?? 0) > 0) : [];

  return (
    <section data-testid="migration-result-step" className="flex max-w-md flex-col gap-5">
      <h2 className="flex items-center gap-2 text-lg font-semibold text-success">
        <CircleCheck aria-hidden className="size-5" />
        {t('result.titleOk')}
      </h2>

      {result && (
        <div className="flex flex-wrap gap-2">
          {createdEntries.map(([kind, n]) => (
            <div key={kind} className="flex min-w-28 flex-col gap-1 rounded-md border border-line bg-surface px-3 py-2">
              <span className="text-xs text-muted">{kindText[kind as keyof typeof kindText]}</span>
              <span className="num text-lg font-semibold text-fg">{n}</span>
            </div>
          ))}
          <div className="flex min-w-28 flex-col gap-1 rounded-md border border-line bg-surface px-3 py-2">
            <span className="text-xs text-muted">{t('result.skipped')}</span>
            <span className="num text-lg font-semibold text-fg">{result.skipped}</span>
          </div>
          <div className="flex min-w-28 flex-col gap-1 rounded-md border border-line bg-surface px-3 py-2">
            <span className="text-xs text-muted">{t('result.warnings')}</span>
            <span className="num text-lg font-semibold text-fg">{result.warnings}</span>
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" icon={<Download aria-hidden className="size-3.5" />} loading={reportM.isPending} onClick={downloadReport}>
          {t('result.reportButton')}
        </Button>
        {job.pre_import_backup_id && (
          <Link to="/settings/backup" className="inline-flex items-center text-sm text-brand underline">
            {t('result.rollbackLink')}
          </Link>
        )}
      </div>

      <div><Button variant="primary" onClick={onNewImport}>{t('result.newImportButton')}</Button></div>
    </section>
  );
}
