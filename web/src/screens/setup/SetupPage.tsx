import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, ArrowRight, CircleAlert, Globe, Network as NetworkIcon, ShieldCheck } from 'lucide-react';
import { apiClient, useSession } from '@/api';
import { apiErrorMessage } from '@/api/errors';
import { qk } from '@/api/queries';
import type { Lang, SetupPayload } from '@/api/types';
import { BrandMark } from '@/shell/AppShell';
import { Button } from '@/ui/Button';
import { Field, Input, Select, Textarea } from '@/ui/Field';
import { isValidCidr, isValidIPv4, splitList } from '@/lib/validators';
import { persistLanguage } from '@/lib/i18n';
import { useNavigate } from 'react-router-dom';

type Step = 'admin' | 'network';

type FormState = {
  code: string;
  login: string;
  password: string;
  fullName: string;
  language: Lang;
  timezone: string;
  externalIp: string;
  localNets: string;
};

const INITIAL: FormState = { code: '', login: '', password: '', fullName: '', language: 'uz', timezone: 'Asia/Tashkent', externalIp: '', localNets: '10.0.0.0/8' };

function parseLocalNets(raw: string, t: (key: string, opts?: Record<string, unknown>) => string): { ok: true; nets: string[] } | { ok: false; error: string } {
  const lines = splitList(raw);
  if (lines.length === 0) return { ok: false, error: t('error.netsRequired') };
  const bad = lines.find((l) => !isValidCidr(l));
  if (bad) return { ok: false, error: t('error.netsInvalid', { bad }) };
  return { ok: true, nets: lines };
}

/** S01 — o'rnatish sehrgari: admin yaratish, keyin tarmoq. Ikki qisqa qadam, FreePBX'ning 6 sahifasi o'rniga. */
export function SetupPage() {
  const { t } = useTranslation('setup');
  const [step, setStep] = useState<Step>('admin');
  const [form, setForm] = useState<FormState>(INITIAL);
  const [touched, setTouched] = useState(false);
  const navigate = useNavigate();
  const setSession = useSession((s) => s.setSession);
  const queryClient = useQueryClient();

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => setForm((f) => ({ ...f, [k]: v }));

  const codeError = touched && form.code.trim().length === 0 ? t('error.codeRequired') : undefined;
  const loginError = touched && form.login.trim().length < 3 ? t('error.loginTooShort') : undefined;
  const passwordError = touched && form.password.length < 8 ? t('error.passwordTooShort') : undefined;
  const nameError = touched && form.fullName.trim().length < 2 ? t('error.nameRequired') : undefined;
  const adminValid = !codeError && !loginError && !passwordError && !nameError;

  const ipError = form.externalIp.trim() !== '' && !isValidIPv4(form.externalIp.trim()) ? t('error.ipInvalid') : undefined;
  const netsResult = parseLocalNets(form.localNets, t);

  const mutation = useMutation({
    mutationFn: () => {
      const payload: SetupPayload = {
        admin: { login: form.login.trim(), password: form.password, full_name: form.fullName.trim() },
        language: form.language,
        timezone: form.timezone,
        external_ip: form.externalIp.trim() || null,
        local_nets: netsResult.ok ? netsResult.nets : [],
        code: form.code.trim(),
      };
      return apiClient.setup(payload);
    },
    onSuccess: (res) => {
      // Sehrgar yopilgach — keshdagi eski `{needed:true}`ni darhol yangilaymiz,
      // aks holda /dashboard'dagi `RequireAuth` eski holatni o'qib /setup'ga qaytarib yuboradi.
      queryClient.setQueryData(qk.setupState, { needed: false });
      setSession(res.access, res.refresh, res.user);
      navigate('/dashboard', { replace: true });
    },
  });

  const goNext = () => { setTouched(true); if (adminValid) setStep('network'); };

  return (
    <div className="grid min-h-dvh place-items-center bg-sidebar-bg px-4 py-10">
      <div className="w-full max-w-[460px] overflow-hidden rounded-xl border border-sidebar-border bg-surface shadow-modal">
        <div className="flex items-center gap-3 border-b border-line bg-sidebar-bg px-6 py-5">
          <BrandMark />
        </div>
        <div className="px-6 pt-5">
          <ol className="flex items-center gap-2 text-xs text-muted" aria-label={t('stepsAriaLabel')}>
            <li className={step === 'admin' ? 'font-semibold text-fg' : ''}>{t('step.admin')}</li>
            <li aria-hidden>→</li>
            <li className={step === 'network' ? 'font-semibold text-fg' : ''}>{t('step.network')}</li>
          </ol>
        </div>

        {step === 'admin' ? (
          <form
            className="flex flex-col gap-4 px-6 py-5"
            onSubmit={(e) => { e.preventDefault(); goNext(); }}
          >
            <p className="text-sm text-muted">{t('adminIntro')}</p>
            <Field label={t('field.setupCode')} required error={codeError} hint={!codeError ? t('field.setupCodeHint') : undefined}>
              {(a) => <Input {...a} mono autoComplete="off" value={form.code} onChange={(e) => set('code', e.target.value)} />}
            </Field>
            <Field label={t('field.login')} required error={loginError}>
              {(a) => <Input {...a} autoFocus autoComplete="username" value={form.login} onChange={(e) => set('login', e.target.value)} />}
            </Field>
            <Field label={t('field.fullName')} required error={nameError}>
              {(a) => <Input {...a} autoComplete="name" value={form.fullName} onChange={(e) => set('fullName', e.target.value)} />}
            </Field>
            <Field label={t('field.password')} required error={passwordError} hint={!passwordError ? t('field.passwordHint') : undefined}>
              {(a) => <Input {...a} type="password" autoComplete="new-password" value={form.password} onChange={(e) => set('password', e.target.value)} />}
            </Field>
            <Field label={t('field.panelLanguage')}>
              {(a) => (
                <Select
                  {...a}
                  value={form.language}
                  onValueChange={(v) => { set('language', v as Lang); persistLanguage(v as Lang); }}
                  options={[{ value: 'uz', label: t('field.languageOptions.uz') }, { value: 'ru', label: t('field.languageOptions.ru') }, { value: 'en', label: t('field.languageOptions.en') }]}
                />
              )}
            </Field>
            <Button type="submit" variant="primary" size="lg" icon={<ArrowRight />}>{t('continue')}</Button>
          </form>
        ) : (
          <form
            className="flex flex-col gap-4 px-6 py-5"
            onSubmit={(e) => { e.preventDefault(); if (!ipError && netsResult.ok) mutation.mutate(); }}
          >
            <p className="flex items-start gap-2 text-sm text-muted">
              <Globe aria-hidden className="mt-0.5 size-4 shrink-0" />
              {t('networkIntro')}
            </p>
            <Field label={t('field.timezone')}>
              {(a) => (
                <Select
                  {...a}
                  value={form.timezone}
                  onValueChange={(v) => set('timezone', v)}
                  options={[{ value: 'Asia/Tashkent', label: t('field.timezoneOptions.tashkent') }, { value: 'Asia/Samarkand', label: t('field.timezoneOptions.samarkand') }]}
                />
              )}
            </Field>
            <Field label={t('field.externalIp')} aside={t('field.optional')} error={ipError} hint={!ipError ? t('field.externalIpHint') : undefined}>
              {(a) => <Input {...a} mono placeholder="203.0.113.10" value={form.externalIp} onChange={(e) => set('externalIp', e.target.value)} />}
            </Field>
            <Field
              label={t('field.localNets')}
              error={!netsResult.ok && form.localNets.trim() !== '' ? netsResult.error : undefined}
              hint={t('field.localNetsHint')}
            >
              {(a) => (
                <Textarea
                  {...a}
                  className="num min-h-16"
                  value={form.localNets}
                  onChange={(e) => set('localNets', e.target.value)}
                />
              )}
            </Field>
            {mutation.isError && (
              <p role="alert" className="flex items-start gap-1.5 text-sm text-danger">
                <CircleAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />
                {apiErrorMessage(mutation.error)}
              </p>
            )}
            <div className="flex items-center justify-between gap-3">
              <Button type="button" variant="ghost" icon={<ArrowLeft />} onClick={() => setStep('admin')}>{t('back')}</Button>
              <Button type="submit" variant="primary" size="lg" icon={<ShieldCheck />} loading={mutation.isPending}>{t('launch')}</Button>
            </div>
          </form>
        )}
        <div className="flex items-center gap-2 border-t border-line bg-surface-2/60 px-6 py-3 text-xs text-muted">
          <NetworkIcon aria-hidden className="size-3.5" />
          {t('footerNote')}
        </div>
      </div>
    </div>
  );
}
