// Qo'llangan, lekin hali tasdiqlanmagan o'zgarish banneri — jonli sanoq + Tasdiqlash/Hozir qaytarish. M12 B3.
// `network/countdown.ts`dagi sof hook/yordamchi qayta ishlatiladi (dryer) — faqat matn namespace'i farqli.
import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Clock } from 'lucide-react';
import type { FirewallPending } from '@/api/types';
import { Button } from '@/ui/Button';
import { formatCountdown, useSecondsLeft } from '../network/countdown';

export function PendingBanner({
  pending, onConfirm, onRollback, onExpire, confirmLoading, rollbackLoading,
}: {
  pending: FirewallPending;
  onConfirm: () => void;
  onRollback: () => void;
  onExpire: () => void;
  confirmLoading: boolean;
  rollbackLoading: boolean;
}) {
  const { t } = useTranslation('firewall');
  const secondsLeft = useSecondsLeft(pending.expires_at);
  const expiredFired = useRef(false);

  useEffect(() => {
    if (secondsLeft === 0 && !expiredFired.current) {
      expiredFired.current = true;
      onExpire();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [secondsLeft]);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-warning/30 bg-warning-soft px-4 py-3 text-sm text-on-warning-soft">
      <div className="flex items-center gap-2.5">
        <Clock aria-hidden className="size-4 shrink-0" />
        <div>
          <p className="font-medium">{t('pendingBanner.title')}</p>
          <p className="num text-xs opacity-90">
            {secondsLeft === 0 ? t('pendingBanner.expiredNotice') : t('pendingBanner.countdown', { time: formatCountdown(secondsLeft) })}
          </p>
        </div>
      </div>
      <div className="flex gap-2">
        <Button size="sm" variant="secondary" loading={rollbackLoading} disabled={secondsLeft === 0} onClick={onRollback}>
          {t('pendingBanner.rollbackButton')}
        </Button>
        <Button size="sm" variant="primary" loading={confirmLoading} disabled={secondsLeft === 0} onClick={onConfirm}>
          {t('pendingBanner.confirmButton')}
        </Button>
      </div>
    </div>
  );
}
