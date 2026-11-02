// M3a §4 — /calls va /me tarixidagi raqam yonidagi «Qo'ng'iroq» tugmasi. Faqat softfon `registered`
// bo'lsa ko'rinadi; bosilganda raqamga to'g'ridan-to'g'ri (tergandek) qo'ng'iroq qilinadi.
import { Phone } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/ui/Button';
import { useSoftphoneStore } from './store';

export function ClickToCallButton({ number }: { number: string }) {
  const { t } = useTranslation('common');
  const registered = useSoftphoneStore((s) => s.connection === 'registered');
  const busy = useSoftphoneStore((s) => s.call !== null);
  if (!registered) return null;
  return (
    <Button
      size="sm"
      variant="ghost"
      iconOnly
      icon={<Phone />}
      aria-label={t('softphone.callNumberAriaLabel', { number })}
      disabled={busy}
      onClick={() => useSoftphoneStore.getState().startCall(number)}
    />
  );
}
