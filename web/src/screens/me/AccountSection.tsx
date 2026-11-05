import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { KeyRound, ShieldCheck } from 'lucide-react';
import { useChangePassword, useDisableTotp, useRegenerateTotpRecoveryCodes } from '@/api/queries';
import { isApiError } from '@/api/errors';
import { useSession } from '@/api/session';
import { TotpEnrollPanel } from '@/auth/TotpEnrollPanel';
import { TotpRecoveryCodes } from '@/auth/TotpRecoveryCodes';
import { Button } from '@/ui/Button';
import { Modal } from '@/ui/Dialog';
import { Field, Input } from '@/ui/Field';
import { Badge } from '@/ui/Status';
import { useToast } from '@/ui/Toast';

const CARD = 'flex flex-col gap-4 rounded-lg border border-line bg-surface p-4 shadow-card';

/**
 * Profil va xavfsizlik — har bir foydalanuvchida bor (ichki raqami bo'lmagan admin ham):
 * kim ekanligi, parolni o'zgartirish va 2FA. Ichki raqamga bog'liq kartalar MePage'da qoladi.
 */
export function AccountSection() {
  return (
    <div className="flex flex-col gap-4">
      <ProfileCard />
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <PasswordCard />
        <TwoFactorCard />
      </div>
    </div>
  );
}

function ProfileCard() {
  const { t } = useTranslation('me');
  const user = useSession((s) => s.user);
  if (!user) return null;
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border border-line bg-surface px-4 py-3 shadow-card">
      <p className="font-display text-base text-fg">{user.full_name}</p>
      <p className="text-sm text-muted">{t('account.login')}: <span className="num text-fg">{user.login}</span></p>
      <p className="text-sm text-muted">
        {t('account.extension')}: {user.extension
          ? <span className="num text-fg">{user.extension.number}</span>
          : <span className="text-fg">{t('account.extensionNone')}</span>}
      </p>
    </div>
  );
}

/** Ixtiyoriy parol almashtirish (majburiysi — /change-password). Server boshqa sessiyalarni yopadi, joriysiga yangi tokenlar beradi. */
function PasswordCard() {
  const { t } = useTranslation('me');
  const toast = useToast();
  const user = useSession((s) => s.user);
  const setUser = useSession((s) => s.setUser);
  const setTokens = useSession((s) => s.setTokens);
  const changeM = useChangePassword();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');

  const errorField = isApiError(changeM.error) ? changeM.error.field : undefined;
  const fieldError = (field: string) => (errorField === field ? changeM.error?.message : undefined);
  const valid = current.length > 0 && next.length >= 10;

  const submit = () => {
    changeM.mutate({ current, new: next }, {
      onSuccess: (tokens) => {
        setTokens(tokens.access, tokens.refresh);
        if (user) setUser({ ...user, must_change_password: false });
        setCurrent('');
        setNext('');
        toast({ kind: 'success', title: t('password.success') });
      },
      onError: (e) => { if (!(isApiError(e) && e.field)) toast({ kind: 'error', title: e.message }); },
    });
  };

  return (
    <form className={CARD} onSubmit={(e) => { e.preventDefault(); if (valid) submit(); }}>
      <h2 className="font-display text-base text-fg">{t('password.title')}</h2>
      <p className="text-sm text-muted">{t('password.description')}</p>
      <Field label={t('password.current')} required error={fieldError('current')}>
        {(a) => <Input {...a} type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />}
      </Field>
      <Field label={t('password.new')} required hint={t('password.newHint')} error={fieldError('new')}>
        {(a) => <Input {...a} type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />}
      </Field>
      <Button type="submit" size="sm" variant="primary" icon={<KeyRound />} className="self-start" loading={changeM.isPending} disabled={!valid}>
        {t('password.submit')}
      </Button>
    </form>
  );
}

/** M10 C B2 — ixtiyoriy 2FA: yoqish (QR/kod), oʻchirish, zaxira kodlarni qayta yaratish. */
function TwoFactorCard() {
  const { t } = useTranslation(['me', 'common']);
  const toast = useToast();
  const user = useSession((s) => s.user);
  const setUser = useSession((s) => s.setUser);
  const disableM = useDisableTotp();
  const regenerateM = useRegenerateTotpRecoveryCodes();

  const [enrolling, setEnrolling] = useState(false);
  const [newRecoveryCodes, setNewRecoveryCodes] = useState<string[] | null>(null);
  const [disabling, setDisabling] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  const enabled = !!user?.totp_enabled;
  const setEnabled = (v: boolean) => { if (user) setUser({ ...user, totp_enabled: v }); };
  const onError = (e: Error) => toast({ kind: 'error', title: e.message });

  const onEnabled = (codes: string[]) => {
    setEnabled(true);
    setEnrolling(false);
    setNewRecoveryCodes(codes);
  };
  const confirmDisable = (code: string) => {
    disableM.mutate({ code }, {
      onSuccess: () => {
        setEnabled(false);
        setDisabling(false);
        toast({ kind: 'success', title: t('me:twofa.toastDisabled') });
      },
      onError,
    });
  };
  const confirmRegenerate = (code: string) => {
    regenerateM.mutate({ code }, {
      onSuccess: (res) => { setRegenerating(false); setNewRecoveryCodes(res.recovery_codes); },
      onError,
    });
  };

  return (
    <div className={CARD}>
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-display text-base text-fg">{t('me:twofa.title')}</h2>
        <Badge tone={enabled ? 'success' : 'neutral'}>{t(enabled ? 'me:twofa.enabled' : 'me:twofa.disabled')}</Badge>
      </div>
      <p className="text-sm text-muted">{t('me:twofa.description')}</p>

      {newRecoveryCodes ? (
        <>
          <TotpRecoveryCodes codes={newRecoveryCodes} />
          <Button size="sm" variant="primary" className="self-start" onClick={() => setNewRecoveryCodes(null)}>{t('me:twofa.done')}</Button>
        </>
      ) : enrolling ? (
        <TotpEnrollPanel onEnabled={onEnabled} />
      ) : enabled ? (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" onClick={() => setRegenerating(true)}>{t('me:twofa.regenerate')}</Button>
          <Button size="sm" variant="danger-ghost" onClick={() => setDisabling(true)}>{t('me:twofa.disable')}</Button>
        </div>
      ) : (
        <Button size="sm" variant="primary" icon={<ShieldCheck />} className="self-start" onClick={() => setEnrolling(true)}>{t('me:twofa.enable')}</Button>
      )}

      <CodeConfirmModal
        open={disabling} onClose={() => setDisabling(false)} danger
        title={t('me:twofa.disable')} intro={t('me:twofa.disableIntro')}
        loading={disableM.isPending} error={disableM.error} onSubmit={confirmDisable}
      />
      <CodeConfirmModal
        open={regenerating} onClose={() => setRegenerating(false)}
        title={t('me:twofa.regenerate')} intro={t('me:twofa.regenerateIntro')}
        loading={regenerateM.isPending} error={regenerateM.error} onSubmit={confirmRegenerate}
      />
    </div>
  );
}

/** 2FA amalini ilovadagi (yoki zaxira) kod bilan tasdiqlash oynasi; yopilganda kod tozalanadi. */
function CodeConfirmModal({ open, onClose, title, intro, danger = false, loading, error, onSubmit }: {
  open: boolean;
  onClose: () => void;
  title: string;
  intro: string;
  danger?: boolean;
  loading: boolean;
  error: Error | null;
  onSubmit: (code: string) => void;
}) {
  const { t } = useTranslation(['me', 'common']);
  const [code, setCode] = useState('');
  // Muvaffaqiyatda ota `open`ni o'zi yopadi — eski kod keyingi ochilishda qolmasin (render paytidagi hosila holat).
  if (!open && code) setCode('');
  const close = () => onClose();
  const trimmed = code.trim();
  return (
    <Modal
      open={open}
      onOpenChange={(v) => { if (!v) close(); }}
      title={title}
      footer={
        <>
          <Button variant="ghost" onClick={close}>{t('common:cancel')}</Button>
          <Button variant={danger ? 'danger' : 'primary'} loading={loading} disabled={trimmed.length < 6} onClick={() => onSubmit(trimmed)}>
            {title}
          </Button>
        </>
      }
    >
      <p className="mb-3 text-sm text-muted">{intro}</p>
      <Field label={t('me:twofa.codeLabel')} error={isApiError(error) ? error.message : undefined}>
        {(a) => <Input {...a} autoFocus inputMode="numeric" autoComplete="one-time-code" placeholder="000000" value={code} onChange={(e) => setCode(e.target.value)} />}
      </Field>
    </Modal>
  );
}
