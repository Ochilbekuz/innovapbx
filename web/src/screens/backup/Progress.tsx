import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';

/** Zaxiralash/tiklash ishi uchun aniq (determinate) progress — hech qayerda shared `ui/` komponenti
 * yo'q edi (grep bilan tasdiqlangan), shuning uchun shu modulga xos kichik komponent qilingan. */
export function Progress({ value, label, className }: { value: number; label?: string; className?: string }) {
  const pct = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div className={cn('w-full', className)}>
      <div
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
        className="h-2 w-full overflow-hidden rounded-full bg-surface-2"
      >
        <div
          className="h-full rounded-full bg-brand transition-[width] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

/** `BackupJobBanner` (zaxiralash) va `RestoreRunner`ning «running» bosqichi (tiklash) ikkisi ham
 * progress + joriy qadam matnini bir xil ko'rinishda chiqaradi — shu umumiy ichki tanaga ajratilgan. */
export function JobProgressBody({ label, jobData }: { label: string; jobData?: { progress: number | null; step: string | null } }) {
  const stepText = useJobStepText(jobData?.step);
  return (
    <>
      <Progress value={jobData?.progress ?? 0} label={label} />
      <p className="text-sm text-muted" role="status">{stepText}</p>
    </>
  );
}

/** Backend bosqichni identifikator (`pg_restore`, …) bilan beradi — tarjima bo'lsa o'shani,
 * bo'lmasa (yangi/noma'lum bosqich yoki fake API'ning tayyor matni) qiymatning o'zini ko'rsatadi. */
export function useJobStepText(step: string | null | undefined): string {
  const { t } = useTranslation('backup');
  return step ? t(`job.steps.${step}`, { defaultValue: step }) : '';
}
