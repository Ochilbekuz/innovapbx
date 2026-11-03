import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Copy, ShieldCheck } from 'lucide-react';
import { useEnableTotp, useSetupTotp } from '@/api/queries';
import { isApiError } from '@/api/errors';
import { copyText } from '@/lib/browser';
import { Button } from '@/ui/Button';
import { Field, Input } from '@/ui/Field';
import { QrImage } from '@/ui/QrImage';
import { useToast } from '@/ui/Toast';

/**
 * M10 C B2 — TOTP ro'yxatdan o'tish: QR/sekret ko'rsatish + 6 xonali kod bilan yoqish.
 * Majburiy (`Enroll2faPage`) va ixtiyoriy (`MePage` kartasi) holatlari uchun umumiy.
 */
export function TotpEnrollPanel({ onEnabled }: { onEnabled: (recoveryCodes: string[]) => void }) {
  const { t } = useTranslation('auth');
  const toast = useToast();
  const setupM = useSetupTotp();
  const enableM = useEnableTotp();
  const [code, setCode] = useState('');

  useEffect(() => { setupM.mutate(); }, [setupM.mutate]);

  const copy = (text: string) => void copyText(text).then((ok) => ok && toast({ kind: 'success', title: t('enroll2fa.copied') }));
  const submit = () => enableM.mutate({ code: code.trim() }, { onSuccess: (res) => onEnabled(res.recovery_codes) });

  if (setupM.isError) {
    return <p role="alert" className="text-sm text-danger">{setupM.error.message}</p>;
  }
  if (!setupM.data) {
    return <div className="skeleton h-[216px] w-[216px] rounded-lg" />;
  }
  const { secret, otpauth_uri } = setupM.data;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col items-center gap-3 sm:flex-row sm:items-start">
        <QrImage url={otpauth_uri} alt={t('enroll2fa.qrAlt')} />
        <div className="flex flex-1 flex-col gap-1.5">
          <p className="text-sm text-muted">{t('enroll2fa.scanIntro')}</p>
          <div className="flex items-center gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2">
            <span className="num flex-1 truncate text-sm" data-testid="totp-secret">{secret}</span>
            <Button size="sm" variant="ghost" iconOnly icon={<Copy />} aria-label={t('enroll2fa.copySecret')} onClick={() => copy(secret)} />
          </div>
          <p className="text-xs text-muted">{t('enroll2fa.manualHint')}</p>
        </div>
      </div>
      <Field label={t('enroll2fa.codeLabel')} required error={isApiError(enableM.error) ? enableM.error.message : undefined}>
        {(a) => <Input {...a} autoFocus inputMode="numeric" autoComplete="one-time-code" placeholder="000000" value={code} onChange={(e) => setCode(e.target.value)} />}
      </Field>
      <div className="flex justify-end">
        <Button variant="primary" icon={<ShieldCheck />} loading={enableM.isPending} disabled={code.trim().length < 6} onClick={submit}>
          {t('enroll2fa.enable')}
        </Button>
      </div>
    </div>
  );
}
