import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowRight } from 'lucide-react';
import { useSession } from '@/api/session';
import { homeFor } from '@/auth/guards';
import { TotpEnrollPanel } from '@/auth/TotpEnrollPanel';
import { TotpRecoveryCodes } from '@/auth/TotpRecoveryCodes';
import { BrandMark } from '@/shell/AppShell';
import { Button } from '@/ui/Button';

/** Majburiy 2FA ro'yxatdan o'tish ekrani — `must_enroll_2fa: true` bo'lsa `RequireAuth` shu yerga qaytaradi (M10 C B2). */
export function Enroll2faPage() {
  const { t } = useTranslation('auth');
  const navigate = useNavigate();
  const user = useSession((s) => s.user);
  const setUser = useSession((s) => s.setUser);
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);

  const finish = () => {
    if (user) setUser({ ...user, must_enroll_2fa: false, totp_enabled: true });
    navigate(homeFor(user?.permissions), { replace: true });
  };

  return (
    <div className="grid min-h-dvh place-items-center bg-sidebar-bg px-4 py-8">
      <div className="w-full max-w-[460px] overflow-hidden rounded-xl border border-sidebar-border bg-surface shadow-modal">
        <div className="flex items-center gap-3 border-b border-line bg-sidebar-bg px-6 py-5">
          <BrandMark />
        </div>
        <div className="flex flex-col gap-4 px-6 py-6">
          <div>
            <h1 className="font-display text-lg text-fg">{t('enroll2fa.title')}</h1>
            <p className="mt-1 text-sm text-muted">{t('enroll2fa.required')}</p>
          </div>
          {recoveryCodes ? (
            <>
              <TotpRecoveryCodes codes={recoveryCodes} />
              <Button variant="primary" size="lg" icon={<ArrowRight />} onClick={finish}>{t('enroll2fa.continue')}</Button>
            </>
          ) : (
            <TotpEnrollPanel onEnabled={setRecoveryCodes} />
          )}
        </div>
      </div>
    </div>
  );
}
