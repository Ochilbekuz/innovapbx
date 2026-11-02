import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { ShieldAlert, TriangleAlert } from 'lucide-react';
import type { MigrationJob } from '@/api/types';
import { useApplyMigrationJob } from '@/api/queries';
import { apiErrorMessage, isApiError } from '@/api/errors';
import { Button } from '@/ui/Button';
import { Field, Input } from '@/ui/Field';
import { JobProgressBody } from '@/screens/backup/Progress';
import { applyMigrationPayload, migrationConfirmValid } from './migrationForms';

/**
 * Sehrgarning 4-bosqichi: `pre_import` zaxira haqida eslatma, zaxira paroli yo'q bo'lsa bloklash,
 * "KOCHIRISH" deb yozib tasdiqlash, `applying` bo'lsa progress. `plan_stale` 409'ida qayta tahlil taklifi.
 */
export function ApplyStep({
  job, canManage, rotateWeakSecrets, confirmText, onConfirmTextChange, onReanalyze,
}: {
  job: MigrationJob; canManage: boolean; rotateWeakSecrets: boolean;
  confirmText: string; onConfirmTextChange: (v: string) => void; onReanalyze: () => void;
}) {
  const { t } = useTranslation('migration');
  const applyM = useApplyMigrationJob();

  if (job.status === 'applying') {
    return (
      <section data-testid="migration-apply-step" className="flex max-w-md flex-col gap-3">
        <h2 className="text-lg font-semibold text-fg">{t('apply.title')}</h2>
        <JobProgressBody label={t('apply.progressLabel')} jobData={job} />
      </section>
    );
  }

  const planStale = isApiError(applyM.error) && applyM.error.code === 'plan_stale';
  const jobRunning = isApiError(applyM.error) && applyM.error.code === 'job_running';
  const otherError = applyM.isError && !planStale && !jobRunning ? apiErrorMessage(applyM.error) : null;

  const submit = () => applyM.mutate({ id: job.id, payload: applyMigrationPayload(rotateWeakSecrets) });

  return (
    <section data-testid="migration-apply-step" className="flex max-w-md flex-col gap-4">
      <h2 className="text-lg font-semibold text-fg">{t('apply.title')}</h2>
      <p className="text-sm text-muted">{t('apply.preImportNotice')}</p>

      {!job.backup_ready && (
        <div className="flex items-start gap-1.5 rounded-md border border-warning/30 bg-warning-soft px-3 py-2 text-sm text-on-warning-soft">
          <ShieldAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />
          <span>
            {t('apply.backupNotReady.body')}{' '}
            <Link to="/settings/backup" className="underline">{t('apply.backupNotReady.link')}</Link>
          </span>
        </div>
      )}

      {planStale && (
        <div className="flex items-center justify-between gap-3 rounded-md border border-warning/30 bg-warning-soft px-3 py-2 text-sm text-on-warning-soft">
          <span className="flex items-start gap-1.5"><TriangleAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />{t('apply.planStale.body')}</span>
          <Button size="sm" variant="secondary" onClick={onReanalyze}>{t('apply.planStale.reanalyze')}</Button>
        </div>
      )}
      {jobRunning && <p className="text-sm text-danger">{t('apply.jobRunning')}</p>}
      {otherError && <p className="text-sm text-danger">{otherError}</p>}

      <Field label={t('apply.confirmLabel')}>
        {(a) => (
          <Input
            {...a} mono placeholder={t('apply.confirmPlaceholder')} disabled={!canManage || !job.backup_ready}
            value={confirmText} onChange={(e) => onConfirmTextChange(e.target.value)}
          />
        )}
      </Field>

      <div>
        <Button
          variant="danger" disabled={!canManage || !job.backup_ready || !migrationConfirmValid(confirmText)}
          loading={applyM.isPending} onClick={submit}
        >
          {applyM.isPending ? t('apply.submitting') : t('apply.submit')}
        </Button>
      </div>
    </section>
  );
}
