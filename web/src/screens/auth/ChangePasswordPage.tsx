import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { CircleAlert, KeyRound } from 'lucide-react';
import { apiClient } from '@/api';
import { useSession } from '@/api/session';
import { isApiError } from '@/api/errors';
import { homeFor } from '@/auth/guards';
import { BrandMark } from '@/shell/AppShell';
import { Button } from '@/ui/Button';
import { Field, Input } from '@/ui/Field';

/** Majburiy parol almashtirish ekrani — `must_change_password: true` bo'lsa `RequireAuth` shu yerga qaytaradi (M2b §3). */
export function ChangePasswordPage() {
  const { t } = useTranslation('auth');
  const navigate = useNavigate();
  const user = useSession((s) => s.user);
  const setUser = useSession((s) => s.setUser);
  const setTokens = useSession((s) => s.setTokens);
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');

  const mutation = useMutation({
    mutationFn: () => apiClient.changePassword({ current, new: next }),
    onSuccess: (tokens) => {
      // Server eski refresh tokenlarni bekor qildi — yangisini saqlamasak, keyingi yangilashda chiqib ketardi.
      setTokens(tokens.access, tokens.refresh);
      if (user) setUser({ ...user, must_change_password: false });
      navigate(homeFor(user?.role), { replace: true });
    },
  });

  const errorField = isApiError(mutation.error) ? mutation.error.field : undefined;
  const errorMessage = isApiError(mutation.error) ? mutation.error.message : undefined;
  const valid = current.length > 0 && next.length >= 10;

  return (
    <div className="grid min-h-dvh place-items-center bg-sidebar-bg px-4">
      <div className="w-full max-w-[400px] overflow-hidden rounded-xl border border-sidebar-border bg-surface shadow-modal">
        <div className="flex items-center gap-3 border-b border-line bg-sidebar-bg px-6 py-5">
          <BrandMark />
        </div>
        <form
          className="flex flex-col gap-4 px-6 py-6"
          onSubmit={(e) => { e.preventDefault(); if (valid) mutation.mutate(); }}
        >
          <h1 className="font-display text-lg text-fg">{t('changePassword.title')}</h1>
          <p className="text-sm text-muted">{t('changePassword.intro')}</p>
          <Field label={t('changePassword.current')} required error={errorField === 'current' ? errorMessage : undefined}>
            {(a) => <Input {...a} autoFocus type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />}
          </Field>
          <Field label={t('changePassword.new')} required hint={t('changePassword.newHint')} error={errorField === 'new' ? errorMessage : undefined}>
            {(a) => <Input {...a} type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />}
          </Field>
          {mutation.isError && !errorField && (
            <p role="alert" className="flex items-start gap-1.5 text-sm text-danger">
              <CircleAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />
              {mutation.error.message}
            </p>
          )}
          <Button type="submit" variant="primary" size="lg" icon={<KeyRound />} loading={mutation.isPending} disabled={!valid}>
            {t('changePassword.submit')}
          </Button>
        </form>
      </div>
    </div>
  );
}
