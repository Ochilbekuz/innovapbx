// Qo'llangan, lekin hali tasdiqlanmagan SSH/veb-panel o'zgarishi banneri — jonli sanoq + Tasdiqlash/Hozir
// qaytarish. `firewall/PendingBanner.tsx` bilan bir xil naqsh — qasddan mustaqil komponent (bitta ekranning
// o'zgarishi boshqasiga ta'sir qilmasligi kerak, ko'ring: `firewall/ConfirmApplyModal.tsx` izohi).
import { useEffect, useRef, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Clock } from 'lucide-react';
import type { AccessPending } from '@/api/types';
import { Button } from '@/ui/Button';
import { formatCountdown, useSecondsLeft } from '../network/countdown';

export function PendingBanner({
  pending, hint, onConfirm, onRollback, onExpire, confirmLoading, rollbackLoading,
}: {
  pending: AccessPending;
  hint?: ReactNode;
  onConfirm: () => void;
  onRollback: () => void;
  onExpire: () => void;
  confirmLoading: boolean;
  rollbackLoading: boolean;
}) {
  const { t } = useTranslation('access');
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
          {hint && <p className="mt-1 text-xs opacity-90">{hint}</p>}
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
