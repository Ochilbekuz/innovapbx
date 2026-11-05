// Firewall sozlamalari: xizmatlar (ssh/web/sip/rtp) ruxsat ro'yxati + bloklangan manzillar, qo'llash-tasdiqlash
// oqimi. Shartnoma: ../../replica/m12-contract.md §B3. Faqat `*` ruxsatiga ko'rinadi (`screens.ts`, group `system`).
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { apiErrorMessage, isApiError } from '@/api/errors';
import { useAccessState, useApplyFirewall, useConfirmFirewall, useFirewallState, useRollbackFirewall, useValidateFirewall } from '@/api/queries';
import type { FirewallFieldError, FirewallStateOut } from '@/api/types';
import { buildFirewallDiff, parseFirewallFieldPath } from '@/domain/firewall';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Field, Segmented, Textarea } from '@/ui/Field';
import { useToast } from '@/ui/Toast';
import { ConfirmApplyModal } from './ConfirmApplyModal';
import { PendingBanner } from './PendingBanner';
import { DEFAULT_TIMEOUT_S, draftToConfig, stateToDraft, updateServiceDraft } from './firewallDraft';
import type { FirewallDraft } from './firewallDraft';

type ValidateMutation = ReturnType<typeof useValidateFirewall>;
type ApplyMutation = ReturnType<typeof useApplyFirewall>;
type PendingMutation = ReturnType<typeof useConfirmFirewall>;
type TFunc = (k: string, v?: Record<string, unknown>) => string;

function Banner({ tone, children }: { tone: 'warning' | 'danger'; children: ReactNode }) {
  const cls = tone === 'warning' ? 'border-warning/30 bg-warning-soft text-on-warning-soft' : 'border-danger/25 bg-danger-soft text-on-danger-soft';
  return <div className={`rounded-md border px-3 py-2.5 text-sm ${cls}`}>{children}</div>;
}

function StickyDraftBar({ count, onDiscard, onApply, loading }: { count: number; onDiscard: () => void; onApply: () => void; loading: boolean }) {
  const { t } = useTranslation('firewall');
  return (
    <div className="sticky bottom-4 z-10 mt-4 flex items-center justify-between gap-3 rounded-md border border-line bg-raised px-4 py-3 shadow-modal">
      <span className="num text-sm font-medium text-fg">{t('draftBar.changes', { count })}</span>
      <div className="flex gap-2">
        <Button variant="ghost" onClick={onDiscard}>{t('draftBar.discard')}</Button>
        <Button variant="primary" loading={loading} onClick={onApply}>{t('draftBar.apply')}</Button>
      </div>
    </div>
  );
}

function PendingSummary({ summary }: { summary: string[] }) {
  return (
    <ul className="num flex flex-col gap-1 rounded-md border border-line bg-surface-2 px-3 py-2.5 text-sm text-fg">
      {summary.map((line, i) => <li key={i}>{line}</li>)}
    </ul>
  );
}

function LastResultBanner({ state, onDismiss, t }: { state: FirewallStateOut; onDismiss: () => void; t: (k: string) => string }) {
  if (!state.last_result) return null;
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-line bg-surface-2 px-3 py-2.5 text-sm text-fg">
      <span>{state.last_result.message || t(`lastResult.${state.last_result.kind}`)}</span>
      <Button size="sm" variant="ghost" onClick={onDismiss}>{t('lastResult.dismiss')}</Button>
    </div>
  );
}

/** `services[idx].allow`/`services.<nom>.allow`/`blocked_cidrs[idx]` xatolarini UI maydoniga bog'laydi
 *  (`parseFirewallFieldPath` — bitta qoida manbai, dryer); qolganlari umumiy ro'yxatga tushadi. */
function groupFirewallErrors(errors: FirewallFieldError[], draft: FirewallDraft) {
  const config = draftToConfig(draft, DEFAULT_TIMEOUT_S);
  const serviceErrors: Record<string, string> = {};
  const otherMessages: string[] = [];
  let blockedError: string | undefined;
  for (const e of errors) {
    const path = parseFirewallFieldPath(e.field, config.services);
    if (path.kind === 'service') serviceErrors[path.name] = e.message;
    else if (path.kind === 'blocked') blockedError = e.message;
    else otherMessages.push(e.message);
  }
  return { serviceErrors, blockedError, otherMessages };
}

function ServiceRow({
  draft, errors, locked, onChange, t, portLabel,
}: {
  draft: FirewallDraft['services'][number];
  errors: Record<string, string>;
  locked: boolean;
  onChange: (name: string, patch: Partial<FirewallDraft['services'][number]>) => void;
  t: TFunc;
  portLabel?: ReactNode;
}) {
  const error = errors[draft.name];
  return (
    <div className="flex flex-col gap-2 rounded-md border border-line bg-surface-2 px-3 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-medium text-fg">
          {t(`services.name.${draft.name}`)}
          {portLabel && <span className="num ml-2 text-xs text-muted">{portLabel}</span>}
        </span>
        <Segmented
          value={draft.mode}
          onChange={(v) => !locked && onChange(draft.name, { mode: v as 'all' | 'allowlist' })}
          label={t('services.column.mode')}
          options={[
            { value: 'all', label: t('services.mode.all') },
            { value: 'allowlist', label: t('services.mode.allowlist') },
          ]}
        />
      </div>
      {draft.mode === 'allowlist' && (
        <Field label={t('services.column.allow')} hint={t('services.allowHint')} error={error}>
          {(a) => (
            <Textarea
              {...a}
              disabled={locked}
              value={draft.allowText}
              onChange={(e) => onChange(draft.name, { allowText: e.target.value })}
            />
          )}
        </Field>
      )}
    </div>
  );
}

function ServicesSection({
  draft, errors, locked, onChangeService, t, portLabels,
}: {
  draft: FirewallDraft;
  errors: Record<string, string>;
  locked: boolean;
  onChangeService: (name: string, patch: Partial<FirewallDraft['services'][number]>) => void;
  t: TFunc;
  portLabels: Record<string, ReactNode>;
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-medium text-fg">{t('services.title')}</p>
        <Link to="/settings/access" className="text-sm text-accent underline-offset-2 hover:underline">{t('accessLink')}</Link>
      </div>
      {draft.services.map((s) => (
        <ServiceRow key={s.name} draft={s} errors={errors} locked={locked} onChange={onChangeService} t={t} portLabel={portLabels[s.name]} />
      ))}
    </div>
  );
}

function BlockedSection({
  draft, error, locked, onChange, t,
}: {
  draft: FirewallDraft;
  error: string | undefined;
  locked: boolean;
  onChange: (text: string) => void;
  t: TFunc;
}) {
  return (
    <Field label={t('blocked.title')} hint={t('blocked.hint')} error={error}>
      {(a) => <Textarea {...a} disabled={locked} value={draft.blockedText} onChange={(e) => onChange(e.target.value)} />}
    </Field>
  );
}

function isFirewallLocked(state: FirewallStateOut): boolean {
  return state.readonly_reason !== null;
}

function syncDraftFromState(
  state: FirewallStateOut | undefined,
  draft: FirewallDraft | null,
  prevPendingId: { current: string | null },
  setDraft: (d: FirewallDraft) => void,
  resetValidationUi: () => void,
): void {
  if (!state) return;
  const hadPending = prevPendingId.current !== null;
  prevPendingId.current = state.pending?.id ?? null;
  if (draft === null || (hadPending && !state.pending)) {
    setDraft(stateToDraft(state));
    resetValidationUi();
  }
}

function requestValidate(
  draft: FirewallDraft | null, validateM: ValidateMutation,
  onInvalid: (errors: FirewallFieldError[]) => void,
  onValid: (diff: string[]) => void,
  onError: (e: unknown) => void,
): void {
  if (!draft) return;
  const config = draftToConfig(draft, DEFAULT_TIMEOUT_S);
  validateM.mutate(config, {
    onSuccess: (result) => (result.ok ? onValid(result.diff) : onInvalid(result.errors)),
    onError,
  });
}

function requestApply(
  draft: FirewallDraft | null, timeoutS: number, applyM: ApplyMutation,
  onApplied: () => void,
  onFieldErrors: (fields: FirewallFieldError[]) => void,
  onError: (e: unknown) => void,
): void {
  if (!draft) return;
  const config = draftToConfig(draft, timeoutS);
  applyM.mutate(config, {
    onSuccess: onApplied,
    onError: (e) => {
      const fields = isApiError(e) ? (e.details?.fields as FirewallFieldError[] | undefined) : undefined;
      return fields ? onFieldErrors(fields) : onError(e);
    },
  });
}

function resolvePending(pendingId: string | undefined, mutation: PendingMutation, onSuccess: () => void, onError: (e: unknown) => void): void {
  if (!pendingId) return;
  mutation.mutate(pendingId, { onSuccess, onError });
}

// DIQQAT: AppShellPage komponenti doim BIR marta, FirewallPage darajasida render qilinadi (pastda) —
// yuklanish/tayyor holatlar faqat uning ICHIDAGI bolani almashtiradi (qarang AccessPage.tsx'dagi xuddi
// shu izoh). Ikki holat ikki xil joyda alohida AppShellPage qaytarsa, React ularni turli element turi
// sifatida koʻrib butun main tugunini qayta yaratadi — bu sidebar/footer soʻrovlarini qayta ishga
// tushiradi va testda within(main) uzilib qoladi.
function FirewallLoadingBody({ isError, onRetry, t }: { isError: boolean; onRetry: () => void; t: (k: string) => string }) {
  return isError ? (
    <div className="flex flex-col items-center gap-2 rounded-md border border-dashed border-line px-3 py-6 text-center text-sm text-muted">
      <p>{t('loadFailed')}</p>
      <Button size="sm" variant="secondary" onClick={onRetry}>{t('retry')}</Button>
    </div>
  ) : (
    <div className="flex flex-col gap-4"><div className="skeleton h-64 rounded-lg" /></div>
  );
}

function FirewallReadyBody({
  t, state, draft, grouped, hasOtherErrors, portLabels, timeoutS, onTimeoutChange, confirm, pendingActions, draftActions,
}: {
  t: TFunc;
  state: FirewallStateOut;
  draft: FirewallDraft;
  grouped: ReturnType<typeof groupFirewallErrors>;
  hasOtherErrors: boolean;
  portLabels: Record<string, ReactNode>;
  timeoutS: number;
  onTimeoutChange: (s: number) => void;
  confirm: { open: boolean; diff: string[]; loading: boolean; onConfirm: () => void; onClose: () => void };
  pendingActions: { onConfirm: () => void; onRollback: () => void; onExpire: () => void; confirmLoading: boolean; rollbackLoading: boolean };
  draftActions: {
    lastResultDismissed: boolean; onDismissLastResult: () => void;
    diffCount: number; onDiscard: () => void; onApply: () => void; applyLoading: boolean;
    onChangeService: (name: string, patch: Partial<FirewallDraft['services'][number]>) => void;
    onChangeBlocked: (text: string) => void;
  };
}) {
  const locked = isFirewallLocked(state);
  return (
    <>
      <div className="flex flex-col gap-4">
        {locked && <Banner tone="warning">{t('readonlyBanner', { reason: state.readonly_reason })}</Banner>}
        {hasOtherErrors && <Banner tone="danger">{t('errorsBanner')}</Banner>}
        {grouped.otherMessages.length > 0 && <PendingSummary summary={grouped.otherMessages} />}
        {!draftActions.lastResultDismissed && !state.pending && (
          <LastResultBanner state={state} onDismiss={draftActions.onDismissLastResult} t={t} />
        )}

        {state.pending ? (
          <>
            <PendingBanner pending={state.pending} {...pendingActions} />
            <PendingSummary summary={state.pending.summary} />
          </>
        ) : (
          <div className="flex flex-col gap-6">
            <ServicesSection draft={draft} errors={grouped.serviceErrors} locked={locked} onChangeService={draftActions.onChangeService} t={t} portLabels={portLabels} />
            <BlockedSection draft={draft} error={grouped.blockedError} locked={locked} onChange={draftActions.onChangeBlocked} t={t} />
          </div>
        )}
      </div>

      {!state.pending && draftActions.diffCount > 0 && !locked && (
        <StickyDraftBar count={draftActions.diffCount} onDiscard={draftActions.onDiscard} onApply={draftActions.onApply} loading={draftActions.applyLoading} />
      )}

      <ConfirmApplyModal open={confirm.open} diff={confirm.diff} timeoutS={timeoutS} onTimeoutChange={onTimeoutChange} onConfirm={confirm.onConfirm} onClose={confirm.onClose} loading={confirm.loading} />
    </>
  );
}

/** Group `system` (faqat `*`) — shartnoma: GET/POST `/firewall/*` (../../replica/m12-contract.md §B3). */
export function FirewallPage() {
  const { t } = useTranslation('firewall');
  const toast = useToast();
  const { data: state, isLoading, isError, refetch } = useFirewallState();
  const { data: access } = useAccessState();
  const validateM = useValidateFirewall();
  const applyM = useApplyFirewall();
  const confirmM = useConfirmFirewall();
  const rollbackM = useRollbackFirewall();

  const [draft, setDraftRaw] = useState<FirewallDraft | null>(null);
  const [validateErrors, setValidateErrors] = useState<FirewallFieldError[]>([]);
  const [timeoutS, setTimeoutS] = useState(DEFAULT_TIMEOUT_S);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmDiff, setConfirmDiff] = useState<string[]>([]);
  const [lastResultDismissed, setLastResultDismissed] = useState(false);
  const prevPendingId = useRef<string | null>(null);

  useEffect(() => {
    syncDraftFromState(state, draft, prevPendingId, setDraftRaw, () => {
      setValidateErrors([]);
      setLastResultDismissed(false);
    });
  }, [state, draft]);

  const handleDiscard = () => { if (state) setDraftRaw(stateToDraft(state)); setValidateErrors([]); };
  const handleChangeService = (name: string, patch: Partial<FirewallDraft['services'][number]>) => {
    setValidateErrors([]);
    setDraftRaw((d) => (d ? updateServiceDraft(d, name, patch) : d));
  };
  const handleChangeBlocked = (text: string) => {
    setValidateErrors([]);
    setDraftRaw((d) => (d ? { ...d, blockedText: text } : d));
  };
  const handleApplyClick = () => requestValidate(
    draft, validateM,
    setValidateErrors,
    (diffLines) => { setConfirmDiff(diffLines); setConfirmOpen(true); },
    (e) => toast({ kind: 'error', title: apiErrorMessage(e) }),
  );
  const handleConfirmApply = () => requestApply(
    draft, timeoutS, applyM,
    () => { setConfirmOpen(false); toast({ kind: 'success', title: t('toast.applied') }); },
    (fields) => { setValidateErrors(fields); setConfirmOpen(false); },
    (e) => toast({ kind: 'error', title: apiErrorMessage(e) }),
  );
  const handleConfirmPending = () => resolvePending(state?.pending?.id, confirmM, () => toast({ kind: 'success', title: t('toast.confirmed') }), (e) => toast({ kind: 'error', title: apiErrorMessage(e) }));
  const handleRollbackPending = () => resolvePending(state?.pending?.id, rollbackM, () => toast({ kind: 'success', title: t('toast.rolledBack') }), (e) => toast({ kind: 'error', title: apiErrorMessage(e) }));

  const diff = useMemo(() => {
    if (!draft || !state) return [];
    return buildFirewallDiff(draftToConfig(draft, timeoutS), { services: state.services, blocked_cidrs: state.blocked_cidrs });
  }, [draft, state, timeoutS]);

  const grouped = useMemo(() => (draft ? groupFirewallErrors(validateErrors, draft) : { serviceErrors: {}, blockedError: undefined, otherMessages: [] }), [validateErrors, draft]);

  const portLabels: Record<string, ReactNode> = useMemo(() => (access ? {
    ssh: t('services.portLabel', { port: access.ssh.port }),
    web: t('services.webPortsLabel', { http: access.web.http_port, https: access.web.https_port }),
  } : {}), [access, t]);

  return (
    <AppShellPage title={t('title')}>
      {isLoading || !state || !draft ? (
        <FirewallLoadingBody isError={isError} onRetry={() => void refetch()} t={t} />
      ) : (
        <FirewallReadyBody
          t={t}
          state={state}
          draft={draft}
          grouped={grouped}
          hasOtherErrors={validateErrors.length > 0}
          portLabels={portLabels}
          timeoutS={timeoutS}
          onTimeoutChange={setTimeoutS}
          confirm={{ open: confirmOpen, diff: confirmDiff, loading: applyM.isPending, onConfirm: handleConfirmApply, onClose: () => setConfirmOpen(false) }}
          pendingActions={{ onConfirm: handleConfirmPending, onRollback: handleRollbackPending, onExpire: () => void refetch(), confirmLoading: confirmM.isPending, rollbackLoading: rollbackM.isPending }}
          draftActions={{
            lastResultDismissed, onDismissLastResult: () => setLastResultDismissed(true),
            diffCount: diff.length, onDiscard: handleDiscard, onApply: handleApplyClick, applyLoading: validateM.isPending,
            onChangeService: handleChangeService,
            onChangeBlocked: handleChangeBlocked,
          }}
        />
      )}
    </AppShellPage>
  );
}
