import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { CircleAlert, CircleCheck, KeyRound, LogIn } from 'lucide-react';
import { apiClient, isApiError, useSession } from '@/api';
import type { AuthResult } from '@/api/types';
import { BrandMark } from '@/shell/AppShell';
import { Button } from '@/ui/Button';
import { Field, Input } from '@/ui/Field';

/** S02 — kirish. Fake klient 5-urinishdan keyin 15 daqiqa bloklaydi (423), demo uchun shu holatni ham ko'rsatamiz. */
export function LoginPage() {
  const { t } = useTranslation('auth');
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();
  const location = useLocation();
  const setSession = useSession((s) => s.setSession);
  const locationState = location.state as { from?: string } | null;
  const from = locationState?.from;
  const notice = useSession((s) => s.notice);

  // M10 B2 — 2FA yoqilgan bo'lsa `login()` tokenlar o'rniga `{status:'totp_required', challenge}` qaytaradi;
  // shu holatda sahifa 2-qadamga (kod kiritish) o'tadi.
  const [challenge, setChallenge] = useState<string | null>(null);
  const [code, setCode] = useState('');
  const [useRecovery, setUseRecovery] = useState(false);

  const afterLogin = (res: AuthResult) => {
    if (res.status === 'totp_required') { setChallenge(res.challenge); return; }
    setSession(res.access, res.refresh, res.user);
    if (res.user.must_change_password) {
      navigate('/change-password', { replace: true });
      return;
    }
    navigate(from ?? (res.user.role === 'operator' ? '/me' : '/dashboard'), { replace: true });
  };

  const mutation = useMutation({
    mutationFn: () => apiClient.login(login.trim(), password),
    onSuccess: afterLogin,
  });

  const totpMutation = useMutation({
    mutationFn: () => apiClient.loginTotp({ challenge: challenge!, code: code.trim() }),
    onSuccess: afterLogin,
  });

  const locked = isApiError(mutation.error) && mutation.error.code === 'locked';
  const backToLogin = () => { setChallenge(null); setCode(''); setUseRecovery(false); totpMutation.reset(); };

  if (challenge) {
    return (
      <div className="grid min-h-dvh place-items-center bg-sidebar-bg px-4">
        <div className="w-full max-w-[400px] overflow-hidden rounded-xl border border-sidebar-border bg-surface shadow-modal">
          <div className="flex items-center gap-3 border-b border-line bg-sidebar-bg px-6 py-5">
            <BrandMark />
          </div>
          <form
            className="flex flex-col gap-4 px-6 py-6"
            onSubmit={(e) => { e.preventDefault(); totpMutation.mutate(); }}
          >
            <div>
              <p className="text-sm font-medium text-text">{t('totp.title')}</p>
              <p className="mt-1 text-sm text-muted">{useRecovery ? t('totp.recoveryIntro') : t('totp.intro')}</p>
            </div>
            <Field label={useRecovery ? t('totp.recoveryCode') : t('totp.code')} required>
              {(a) => (
                <Input
                  {...a} autoFocus data-testid="totp-code" autoComplete="one-time-code"
                  placeholder={useRecovery ? 'xxxx-xxxx' : '000000'}
                  value={code} onChange={(e) => setCode(e.target.value)}
                />
              )}
            </Field>
            {totpMutation.isError && (
              <p role="alert" className="flex items-start gap-1.5 text-sm text-danger">
                <CircleAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />
                {totpMutation.error.message}
              </p>
            )}
            <Button type="submit" variant="primary" size="lg" icon={<KeyRound />} loading={totpMutation.isPending}>
              {t('totp.submit')}
            </Button>
            <div className="flex items-center justify-between text-sm">
              <button type="button" className="text-muted underline-offset-2 hover:underline" onClick={backToLogin}>
                {t('totp.back')}
              </button>
              <button
                type="button" className="text-muted underline-offset-2 hover:underline"
                onClick={() => { setUseRecovery((v) => !v); setCode(''); totpMutation.reset(); }}
              >
                {useRecovery ? t('totp.useCode') : t('totp.useRecovery')}
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="grid min-h-dvh place-items-center bg-sidebar-bg px-4">
      <div className="w-full max-w-[400px] overflow-hidden rounded-xl border border-sidebar-border bg-surface shadow-modal">
        <div className="flex items-center gap-3 border-b border-line bg-sidebar-bg px-6 py-5">
          <BrandMark />
        </div>
        <form
          className="flex flex-col gap-4 px-6 py-6"
          onSubmit={(e) => { e.preventDefault(); if (!locked) mutation.mutate(); }}
        >
          <p className="text-sm text-muted">{t('intro')}</p>
          {notice && (
            <p role="status" className="flex items-start gap-1.5 text-sm text-success">
              <CircleCheck aria-hidden className="mt-0.5 size-3.5 shrink-0" />
              {notice}
            </p>
          )}
          <Field label={t('login')} required>
            {(a) => <Input {...a} autoFocus autoComplete="username" value={login} onChange={(e) => setLogin(e.target.value)} />}
          </Field>
          <Field label={t('password')} required>
            {(a) => <Input {...a} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />}
          </Field>
          {mutation.isError && (
            <p role="alert" className="flex items-start gap-1.5 text-sm text-danger">
              <CircleAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />
              {mutation.error.message}
            </p>
          )}
          <Button type="submit" variant="primary" size="lg" icon={<LogIn />} loading={mutation.isPending} disabled={locked}>
            {t('submit')}
          </Button>
        </form>
      </div>
    </div>
  );
}
