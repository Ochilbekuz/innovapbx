import { useTranslation } from 'react-i18next';
import type { MigrationJob } from '@/api/types';
import { useAnalyzeMigrationJob } from '@/api/queries';
import { apiErrorMessage } from '@/api/errors';
import { Button } from '@/ui/Button';
import { useToast } from '@/ui/Toast';
import { JobProgressBody } from '@/screens/backup/Progress';

/**
 * Sehrgarning 2-bosqichi: `uploaded` holatida "Tahlilni boshlash" tugmasi, `analyzing`'da progress.
 * Tahlil hech narsani o'zgartirmaydi — faqat reja tuziladi (3-bosqichda ko'rsatiladi).
 */
export function AnalyzeStep({ job, canManage }: { job: MigrationJob; canManage: boolean }) {
  const { t } = useTranslation('migration');
  const toast = useToast();
  const analyzeM = useAnalyzeMigrationJob();

  if (job.status === 'analyzing') {
    return (
      <section data-testid="migration-analyze-step" className="flex max-w-md flex-col gap-3">
        <h2 className="text-lg font-semibold text-fg">{t('analyze.title')}</h2>
        <JobProgressBody label={t('analyze.progressLabel')} jobData={job} />
      </section>
    );
  }

  const start = () => analyzeM.mutate(job.id, {
    onError: (e) => toast({ kind: 'error', title: apiErrorMessage(e) }),
  });

  return (
    <section data-testid="migration-analyze-step" className="flex max-w-md flex-col gap-4">
      <h2 className="text-lg font-semibold text-fg">{t('analyze.title')}</h2>
      <p className="text-sm text-muted">{t('analyze.autoStartHint')}</p>
      <div>
        <Button variant="primary" disabled={!canManage} loading={analyzeM.isPending} onClick={start}>
          {analyzeM.isPending ? t('analyze.starting') : t('analyze.startButton')}
        </Button>
      </div>
    </section>
  );
}
