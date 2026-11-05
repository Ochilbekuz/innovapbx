// Kirish (SSH va veb-panel) sozlamalari: SSH holati + port oʻzgartirish, veb-panel portlari. Shartnoma:
// ../../replica/m12-contract.md §B4. Faqat `*` ruxsatiga koʻrinadi (`screens.ts`, group `system`).
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Copy } from 'lucide-react';
import { apiErrorMessage, isApiError } from '@/api/errors';
import { useAccessState, useApplySsh, useApplyWeb, useConfirmAccess, useRollbackAccess } from '@/api/queries';
import type { AccessFieldError, AccessStateOut } from '@/api/types';
import {
  ACCESS_DEFAULT_TIMEOUT_S, buildSshLoginCommand, buildWebAddress, buildWebConfirmUrl, ROOT_LOGIN_FIX_COMMAND, sshLoginAdvice, sshLoginUser,
  sshNeedsAttention,
} from '@/domain/access';
import { copyText, currentLocation, navigateTo } from '@/lib/browser';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Field, Input } from '@/ui/Field';
import { useToast } from '@/ui/Toast';
import { ConfirmWebApplyModal } from './ConfirmWebApplyModal';
import { PendingBanner } from './PendingBanner';

type TFunc = (k: string, v?: Record<string, unknown>) => string;
type ApplySshMutation = ReturnType<typeof useApplySsh>;
type ApplyWebMutation = ReturnType<typeof useApplyWeb>;
type PendingMutation = ReturnType<typeof useConfirmAccess>;

function Banner({ tone, children }: { tone: 'warning' | 'danger'; children: ReactNode }) {
  const cls = tone === 'warning' ? 'border-warning/30 bg-warning-soft text-on-warning-soft' : 'border-danger/25 bg-danger-soft text-on-danger-soft';
  return <div className={`rounded-md border px-3 py-2.5 text-sm ${cls}`}>{children}</div>;
}

function LastResultBanner({ state, onDismiss, t }: { state: AccessStateOut; onDismiss: () => void; t: TFunc }) {
  if (!state.last_result) return null;
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-line bg-surface-2 px-3 py-2.5 text-sm text-fg">
      <span>{state.last_result.message || t(`lastResult.${state.last_result.status}`)}</span>
      <Button size="sm" variant="ghost" onClick={onDismiss}>{t('lastResult.dismiss')}</Button>
    </div>
  );
}

function Card({ title, children }: { title: ReactNode; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-4 rounded-lg border border-line bg-raised p-4">
      <h2 className="font-display text-base text-fg">{title}</h2>
      {children}
    </div>
  );
}

function LoginCommandRow({ command, t }: { command: string; t: TFunc }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    void copyText(command).then((ok) => {
      if (ok) {
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }
    });
  };
  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-sm font-medium text-fg">{t('ssh.loginInstructions')}</p>
      <div className="flex items-center gap-2 rounded-md border border-line bg-surface-2 px-3 py-2">
        <code className="num flex-1 truncate text-sm text-fg">{command}</code>
        <Button size="sm" variant="ghost" iconOnly icon={<Copy />} aria-label={t('ssh.copy')} onClick={handleCopy} />
      </div>
      {copied && <p className="text-xs text-success">{t('ssh.copied')}</p>}
    </div>
  );
}

function SshStatusSection({ ssh, hostname, t }: { ssh: AccessStateOut['ssh']; hostname: string; t: TFunc }) {
  const command = buildSshLoginCommand(ssh.port, sshLoginUser(ssh), hostname);
  const advice = sshLoginAdvice(ssh);
  return (
    <div className="flex flex-col gap-3">
      {sshNeedsAttention(ssh) && <Banner tone="danger">{t('ssh.attentionWarning')}</Banner>}
      <div className="flex flex-wrap gap-4 text-sm text-fg">
        <span>{ssh.active ? t('ssh.active') : t('ssh.inactive')}</span>
        <span className="num">{t('ssh.currentPort')}: {ssh.port}</span>
        <span className="num">{t('ssh.listening', { ports: ssh.listening_ports.join(', ') })}</span>
        <span>{ssh.password_auth ? t('ssh.passwordAuthOn') : t('ssh.passwordAuthOff')}</span>
      </div>
      {advice === 'sudo' && <p className="text-sm text-muted">{t('ssh.rootLoginNote')}</p>}
      {advice === 'no-login' && (
        <Banner tone="warning">
          <p>{t('ssh.noLoginUser')}</p>
          <code className="num mt-1.5 block break-all text-xs">{ROOT_LOGIN_FIX_COMMAND}</code>
        </Banner>
      )}
      {ssh.host_firewall === 'external' && <p className="text-sm text-muted">{t('ssh.hostFirewallNote')}</p>}
      <LoginCommandRow command={command} t={t} />
    </div>
  );
}

function SshPortForm({
  port, timeoutS, error, locked, onPortChange, onTimeoutChange, onSubmit, loading, t,
}: {
  port: string;
  timeoutS: number;
  error: string | undefined;
  locked: boolean;
  onPortChange: (v: string) => void;
  onTimeoutChange: (s: number) => void;
  onSubmit: () => void;
  loading: boolean;
  t: TFunc;
}) {
  return (
    <form
      className="flex flex-wrap items-end gap-3"
      onSubmit={(e) => { e.preventDefault(); onSubmit(); }}
    >
      <Field label={t('ssh.portLabel')} error={error} className="w-40">
        {(a) => <Input {...a} type="number" min={1} max={65535} disabled={locked} value={port} onChange={(e) => onPortChange(e.target.value)} />}
      </Field>
      <Field label={t('ssh.timeoutLabel')} className="w-40">
        {(a) => <Input {...a} type="number" disabled={locked} value={timeoutS} onChange={(e) => onTimeoutChange(Number(e.target.value))} />}
      </Field>
      <Button type="submit" variant="primary" loading={loading} disabled={locked}>{t('ssh.apply')}</Button>
    </form>
  );
}

function WebPortForm({
  http, https, httpError, httpsError, locked, onHttpChange, onHttpsChange, onSubmit, t,
}: {
  http: string;
  https: string;
  httpError: string | undefined;
  httpsError: string | undefined;
  locked: boolean;
  onHttpChange: (v: string) => void;
  onHttpsChange: (v: string) => void;
  onSubmit: () => void;
  t: TFunc;
}) {
  return (
    <form
      className="flex flex-wrap items-end gap-3"
      onSubmit={(e) => { e.preventDefault(); onSubmit(); }}
    >
      <Field label={t('web.httpPort')} error={httpError} className="w-40">
        {(a) => <Input {...a} type="number" min={1} max={65535} disabled={locked} value={http} onChange={(e) => onHttpChange(e.target.value)} />}
      </Field>
      <Field label={t('web.httpsPort')} error={httpsError} className="w-40">
        {(a) => <Input {...a} type="number" min={1} max={65535} disabled={locked} value={https} onChange={(e) => onHttpsChange(e.target.value)} />}
      </Field>
      <Button type="submit" variant="primary" disabled={locked}>{t('web.apply')}</Button>
    </form>
  );
}

function isAccessLocked(state: AccessStateOut): boolean {
  return state.readonly_reason !== null;
}

function findFieldError(errors: AccessFieldError[], field: string): string | undefined {
  return errors.find((e) => e.field === field)?.message;
}

function requestApplySsh(
  port: number, timeoutS: number, mutation: ApplySshMutation,
  onApplied: () => void, onFieldErrors: (f: AccessFieldError[]) => void, onError: (e: unknown) => void,
): void {
  mutation.mutate({ port, timeout_s: timeoutS }, {
    onSuccess: onApplied,
    onError: (e) => {
      const fields = isApiError(e) ? (e.details?.fields as AccessFieldError[] | undefined) : undefined;
      return fields ? onFieldErrors(fields) : onError(e);
    },
  });
}

function requestApplyWeb(
  httpPort: number, httpsPort: number, timeoutS: number, mutation: ApplyWebMutation,
  onApplied: (state: AccessStateOut) => void, onFieldErrors: (f: AccessFieldError[]) => void, onError: (e: unknown) => void,
): void {
  mutation.mutate({ http_port: httpPort, https_port: httpsPort, timeout_s: timeoutS }, {
    onSuccess: onApplied,
    onError: (e) => {
      const fields = isApiError(e) ? (e.details?.fields as AccessFieldError[] | undefined) : undefined;
      return fields ? onFieldErrors(fields) : onError(e);
    },
  });
}

function resolvePending(pendingId: string | undefined, mutation: PendingMutation, onSuccess: () => void, onError: (e: unknown) => void): void {
  if (!pendingId) return;
  mutation.mutate(pendingId, { onSuccess, onError });
}

// DIQQAT: AppShellPage komponenti doim BIR marta, AccessPage darajasida render qilinadi (pastda) —
// yuklanish/tayyor holatlar faqat uning ICHIDAGI bolani almashtiradi. Agar bu ikki holat ikki xil
// joyda alohida AppShellPage qaytarsa, React ularni turli element turi sifatida koʻrib butun main
// tugunini (va undagi sidebar holatini) qayta yaratadi — sinovda within(main) eski, uzilgan DOM
// tugunini kutib qolishiga olib keladi.
function AccessLoadingBody({ isError, onRetry, t }: { isError: boolean; onRetry: () => void; t: TFunc }) {
  return isError ? (
    <div className="flex flex-col items-center gap-2 rounded-md border border-dashed border-line px-3 py-6 text-center text-sm text-muted">
      <p>{t('loadFailed')}</p>
      <Button size="sm" variant="secondary" onClick={onRetry}>{t('retry')}</Button>
    </div>
  ) : (
    <div className="flex flex-col gap-4"><div className="skeleton h-64 rounded-lg" /></div>
  );
}

/** Group `system` (faqat `*`) — shartnoma: GET/POST `/access/*` (../../replica/m12-contract.md §B4). */
export function AccessPage() {
  const { t } = useTranslation('access');
  const toast = useToast();
  const { data: state, isLoading, isError, refetch } = useAccessState();
  const applySshM = useApplySsh();
  const applyWebM = useApplyWeb();
  const confirmM = useConfirmAccess();
  const rollbackM = useRollbackAccess();

  const [sshPort, setSshPort] = useState('');
  const [sshTimeout, setSshTimeout] = useState(ACCESS_DEFAULT_TIMEOUT_S);
  const [sshErrors, setSshErrors] = useState<AccessFieldError[]>([]);

  const [webHttp, setWebHttp] = useState('');
  const [webHttps, setWebHttps] = useState('');
  const [webErrors, setWebErrors] = useState<AccessFieldError[]>([]);
  const [webTimeout, setWebTimeout] = useState(ACCESS_DEFAULT_TIMEOUT_S);
  const [webConfirmOpen, setWebConfirmOpen] = useState(false);
  const [lastResultDismissed, setLastResultDismissed] = useState(false);
  const prevPendingId = useRef<string | null>(null);
  // Diqqat: dastlabki toʻldirish uchun `sshPort === ''` tekshiruvi ISHLATILMAYDI — foydalanuvchi
  // maydonni tozalaganda (`user.clear`) ham vaqtincha '' boʻladi, shu payt effekt uni joriy holatga
  // qaytarib qoʻyib, keyingi kiritilgan qiymatga ulanib ketardi (masalan "22" + "5060" = "225060").
  const initialized = useRef(false);

  useEffect(() => {
    if (!state) return;
    const hadPending = prevPendingId.current !== null;
    prevPendingId.current = state.pending?.id ?? null;
    if (!initialized.current || (hadPending && !state.pending)) {
      initialized.current = true;
      setSshPort(String(state.ssh.port));
      setWebHttp(String(state.web.http_port));
      setWebHttps(String(state.web.https_port));
      setSshErrors([]);
      setWebErrors([]);
      setLastResultDismissed(false);
    }
  }, [state]);

  if (isLoading || !state) {
    return (
      <AppShellPage title={t('title')}>
        <AccessLoadingBody isError={isError} onRetry={() => void refetch()} t={t} />
      </AppShellPage>
    );
  }

  const locked = isAccessLocked(state);
  const hostname = currentLocation().hostname;
  const previewAddress = buildWebAddress({ ...currentLocation(), httpPort: Number(webHttp) || state.web.http_port, httpsPort: Number(webHttps) || state.web.https_port });

  const handleApplySsh = () => requestApplySsh(
    Number(sshPort), sshTimeout, applySshM,
    () => toast({ kind: 'success', title: t('toast.applied') }),
    setSshErrors,
    (e) => toast({ kind: 'error', title: apiErrorMessage(e) }),
  );
  const handleOpenWebConfirm = () => setWebConfirmOpen(true);
  const handleApplyWeb = () => requestApplyWeb(
    Number(webHttp), Number(webHttps), webTimeout, applyWebM,
    (result) => {
      setWebConfirmOpen(false);
      if (result.pending) {
        navigateTo(buildWebConfirmUrl({ ...currentLocation(), httpPort: Number(webHttp), httpsPort: Number(webHttps), pendingId: result.pending.id }));
      }
    },
    (fields) => { setWebErrors(fields); setWebConfirmOpen(false); },
    (e) => toast({ kind: 'error', title: apiErrorMessage(e) }),
  );
  const handleConfirmPending = () => resolvePending(state.pending?.id, confirmM, () => toast({ kind: 'success', title: t('toast.confirmed') }), (e) => toast({ kind: 'error', title: apiErrorMessage(e) }));
  const handleRollbackPending = () => resolvePending(state.pending?.id, rollbackM, () => toast({ kind: 'success', title: t('toast.rolledBack') }), (e) => toast({ kind: 'error', title: apiErrorMessage(e) }));

  const sshPending = state.pending?.kind === 'ssh' ? state.pending : null;
  const webPending = state.pending?.kind === 'web' ? state.pending : null;

  return (
    <AppShellPage title={t('title')}>
      <div className="flex flex-col gap-4">
        {locked && <Banner tone="warning">{t('readonlyBanner', { reason: state.readonly_reason })}</Banner>}
        {!lastResultDismissed && !state.pending && <LastResultBanner state={state} onDismiss={() => setLastResultDismissed(true)} t={t} />}

        <Card title={t('ssh.title')}>
          <SshStatusSection ssh={state.ssh} hostname={hostname} t={t} />
          {sshPending ? (
            <PendingBanner
              pending={sshPending}
              hint={t('ssh.pendingHint', { command: buildSshLoginCommand(sshPending.new_ports[0] ?? state.ssh.port, sshLoginUser(state.ssh), hostname) })}
              onConfirm={handleConfirmPending}
              onRollback={handleRollbackPending}
              onExpire={() => void refetch()}
              confirmLoading={confirmM.isPending}
              rollbackLoading={rollbackM.isPending}
            />
          ) : (
            <SshPortForm
              port={sshPort}
              timeoutS={sshTimeout}
              error={findFieldError(sshErrors, 'port')}
              locked={locked}
              onPortChange={(v) => { setSshErrors([]); setSshPort(v); }}
              onTimeoutChange={setSshTimeout}
              onSubmit={handleApplySsh}
              loading={applySshM.isPending}
              t={t}
            />
          )}
        </Card>

        <Card title={t('web.title')}>
          {webPending ? (
            <PendingBanner
              pending={webPending}
              onConfirm={handleConfirmPending}
              onRollback={handleRollbackPending}
              onExpire={() => void refetch()}
              confirmLoading={confirmM.isPending}
              rollbackLoading={rollbackM.isPending}
            />
          ) : (
            <WebPortForm
              http={webHttp}
              https={webHttps}
              httpError={findFieldError(webErrors, 'http_port')}
              httpsError={findFieldError(webErrors, 'https_port')}
              locked={locked}
              onHttpChange={(v) => { setWebErrors([]); setWebHttp(v); }}
              onHttpsChange={(v) => { setWebErrors([]); setWebHttps(v); }}
              onSubmit={handleOpenWebConfirm}
              t={t}
            />
          )}
        </Card>

        <p className="text-sm text-muted">
          <Link to="/settings/firewall" className="text-accent underline-offset-2 hover:underline">{t('firewallLink')}</Link>
        </p>
      </div>

      <ConfirmWebApplyModal
        open={webConfirmOpen}
        url={previewAddress}
        timeoutS={webTimeout}
        onTimeoutChange={setWebTimeout}
        onConfirm={handleApplyWeb}
        onClose={() => setWebConfirmOpen(false)}
        loading={applyWebM.isPending}
      />
    </AppShellPage>
  );
}
