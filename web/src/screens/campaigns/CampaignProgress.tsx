import { useTranslation } from 'react-i18next';
import type { CampaignStats } from '@/api/types';
import { campaignProgress } from '@/domain/campaigns';
import { cn } from '@/lib/cn';

const SEGMENTS = [
  { key: 'done', className: 'bg-success' },
  { key: 'skipped', className: 'bg-warning/70' },
  { key: 'failed', className: 'bg-danger/80' },
] as const;

/** Hal bo'lganlar ulushi: bajarildi / o'tkazildi / yetib bo'lmadi — bitta ingichka chiziqda. Qolgani — navbat. */
export function CampaignProgress({ stats, className }: { stats: CampaignStats; className?: string }) {
  const { t } = useTranslation('campaigns');
  if (stats.total === 0) return <span className="text-sm text-muted">{t('noContacts')}</span>;
  const pct = campaignProgress(stats);
  return (
    <div className={cn('flex min-w-36 items-center gap-2.5', className)}>
      <div
        role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} aria-label={t('column.progress')}
        className="flex h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2 ring-1 ring-inset ring-line"
      >
        {SEGMENTS.map((s) => (
          <span key={s.key} className={cn('h-full transition-[width] duration-slow', s.className)} style={{ width: `${(stats[s.key] * 100) / stats.total}%` }} />
        ))}
      </div>
      <span className="num shrink-0 text-xs text-muted">
        {t('progressOf', { handled: stats.done + stats.failed + stats.skipped, total: stats.total })}
      </span>
    </div>
  );
}
