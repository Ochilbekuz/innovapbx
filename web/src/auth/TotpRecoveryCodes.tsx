import { useTranslation } from 'react-i18next';
import { Copy } from 'lucide-react';
import { copyText } from '@/lib/browser';
import { Button } from '@/ui/Button';
import { useToast } from '@/ui/Toast';

/** M10 C B2 — bir martalik zaxira kodlar: faqat shu paytda ko'rsatiladi, keyin qayta ko'rish mumkin emas. */
export function TotpRecoveryCodes({ codes }: { codes: string[] }) {
  const { t } = useTranslation('auth');
  const toast = useToast();
  const copyAll = () => void copyText(codes.join('\n')).then((ok) => ok && toast({ kind: 'success', title: t('enroll2fa.copied') }));

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted">{t('enroll2fa.recoveryIntro')}</p>
      <div className="grid grid-cols-2 gap-2 rounded-md border border-line bg-surface-2/60 p-3">
        {codes.map((code) => (
          <span key={code} className="num text-sm text-fg">{code}</span>
        ))}
      </div>
      <Button size="sm" variant="secondary" icon={<Copy />} onClick={copyAll} className="self-start">{t('enroll2fa.copyAll')}</Button>
    </div>
  );
}
