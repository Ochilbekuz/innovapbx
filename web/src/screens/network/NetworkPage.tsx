// S38 — Tarmoq sozlamalari: Umumiy/Interfeyslar/Statik marshrutlar + qo'llash-tasdiqlash oqimi.
// Shartnoma: ../../replica/m8-network-contract.md §4 (API), §5 (frontend).
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { apiErrorMessage, isApiError } from '@/api/errors';
import { useApplyNetwork, useConfirmNetwork, useNetworkState, useRollbackNetwork, useValidateNetwork } from '@/api/queries';
import type { NetworkFieldError, NetworkStateOut } from '@/api/types';
import { buildNetworkDiff } from '@/domain/network';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Tabs, type TabItem } from '@/ui/Tabs';
import { useToast } from '@/ui/Toast';
import { ConfirmApplyModal } from './ConfirmApplyModal';
import { GeneralTab } from './GeneralTab';
import { InterfacesTab } from './InterfacesTab';
import { PendingBanner } from './PendingBanner';
import { PingTab } from './PingTab';
import { RoutesTab } from './RoutesTab';
import { DEFAULT_TIMEOUT_S, draftToConfig, normalizeServerErrors, stateToDraft } from './networkDraft';
import type { NetworkDraft } from './networkDraft';

type ValidateMutation = ReturnType<typeof useValidateNetwork>;
type ApplyMutation = ReturnType<typeof useApplyNetwork>;
type PendingMutation = ReturnType<typeof useConfirmNetwork>;
type TFunc = (k: string, v?: Record<string, unknown>) => string;

function Banner({ tone, children }: { tone: 'warning' | 'danger'; children: ReactNode }) {
  const cls = tone === 'warning' ? 'border-warning/30 bg-warning-soft text-on-warning-soft' : 'border-danger/25 bg-danger-soft text-on-danger-soft';
  return <div className={`rounded-md border px-3 py-2.5 text-sm ${cls}`}>{children}</div>;
}

function StickyDraftBar({ count, onDiscard, onApply, loading }: { count: number; onDiscard: () => void; onApply: () => void; loading: boolean }) {
  const { t } = useTranslation('network');
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

/** `state.pending` mavjud ekan tahrirlash qulflanadi — foydalanuvchi avval tasdiqlashi/qaytarishi kerak. */
function PendingSummary({ summary }: { summary: string[] }) {
  return (
    <ul className="num flex flex-col gap-1 rounded-md border border-line bg-surface-2 px-3 py-2.5 text-sm text-fg">
      {summary.map((line, i) => <li key={i}>{line}</li>)}
    </ul>
  );
}

function LastResultBanner({ state, onDismiss, t }: { state: NetworkStateOut; onDismiss: () => void; t: (k: string) => string }) {
  if (!state.last_result) return null;
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-line bg-surface-2 px-3 py-2.5 text-sm text-fg">
      <span>{state.last_result.message || t(`lastResult.${state.last_result.kind}`)}</span>
      <Button size="sm" variant="ghost" onClick={onDismiss}>{t('lastResult.dismiss')}</Button>
    </div>
  );
}

function ReadonlyBanner({ state, t }: { state: NetworkStateOut; t: TFunc }) {
  if (state.editable) return null;
  // netplan/NM — UI tilida; boshqa sabablar (NETD_READONLY, aniqlanmagan) — server matni
  const reason = t(`readonlyReason.${state.backend}`, { defaultValue: state.readonly_reason ?? '—' });
  return <Banner tone="warning">{t('readonlyBanner', { reason })}</Banner>;
}

function HelperUnavailableBanner({ state, t }: { state: NetworkStateOut; t: (k: string) => string }) {
  if (state.helper.available) return null;
  return <Banner tone="danger">{t('helperUnavailableBanner')}</Banner>;
}

function ValidationErrorsBanner({ show, t }: { show: boolean; t: (k: string) => string }) {
  if (!show) return null;
  return <Banner tone="danger">{t('errorsBanner')}</Banner>;
}

function NetworkBanners({
  state, hasValidateErrors, showLastResult, onDismissLastResult, t,
}: {
  state: NetworkStateOut;
  hasValidateErrors: boolean;
  showLastResult: boolean;
  onDismissLastResult: () => void;
  t: TFunc;
}) {
  return (
    <>
      <ReadonlyBanner state={state} t={t} />
      <HelperUnavailableBanner state={state} t={t} />
      <ValidationErrorsBanner show={hasValidateErrors} t={t} />
      {showLastResult && <LastResultBanner state={state} onDismiss={onDismissLastResult} t={t} />}
    </>
  );
}

function NetworkLoadingState({ title, isError, onRetry, t }: { title: string; isError: boolean; onRetry: () => void; t: (k: string) => string }) {
  return (
    <AppShellPage title={title}>
      {isError ? (
        <div className="flex flex-col items-center gap-2 rounded-md border border-dashed border-line px-3 py-6 text-center text-sm text-muted">
          <p>{t('loadFailed')}</p>
          <Button size="sm" variant="secondary" onClick={onRetry}>{t('retry')}</Button>
        </div>
      ) : (
        <div className="flex flex-col gap-4"><div className="skeleton h-64 rounded-lg" /></div>
      )}
    </AppShellPage>
  );
}

function buildNetworkTabs({
  draft, state, errors, locked, onChangeGeneral, onChangeInterface, onChangeRoutes, t,
}: {
  draft: NetworkDraft; state: NetworkStateOut; errors: NetworkFieldError[]; locked: boolean;
  onChangeGeneral: (patch: Partial<NetworkDraft>) => void;
  onChangeInterface: (name: string, next: NetworkDraft['interfaces'][number]) => void;
  onChangeRoutes: (next: NetworkDraft['routes']) => void;
  t: (k: string) => string;
}): TabItem[] {
  return [
    {
      value: 'general', label: t('tabs.general'), invalid: errors.some((e) => e.field === 'hostname'),
      content: <GeneralTab draft={draft} onChange={onChangeGeneral} errors={errors} defaultGateway={state.default_gateway} dnsEditable={state.dns.editable} locked={locked} />,
    },
    {
      value: 'interfaces', label: t('tabs.interfaces'), invalid: errors.some((e) => e.field.startsWith('interfaces')),
      content: <InterfacesTab interfaces={state.interfaces} draft={draft} errors={errors} locked={locked} onChangeInterface={onChangeInterface} />,
    },
    {
      value: 'routes', label: t('tabs.routes'), invalid: errors.some((e) => e.field.startsWith('routes')),
      content: <RoutesTab routes={draft.routes} liveRoutes={state.routes.live} interfaces={state.interfaces} errors={errors} locked={locked} onChange={onChangeRoutes} />,
    },
    // Diagnostika — `locked`ga bog'liq emas (konfiguratsiyani o'zgartirmaydi).
    { value: 'ping', label: t('tabs.ping'), content: <PingTab gateway={state.default_gateway.address} helperAvailable={state.helper.available} /> },
  ];
}

function isNetworkLocked(state: NetworkStateOut): boolean {
  return !state.editable || !state.helper.available;
}

function computeConfig(draft: NetworkDraft | null, timeoutS: number) {
  return draft ? draftToConfig(draft, timeoutS) : null;
}

function computeDiff(config: ReturnType<typeof computeConfig>, state: NetworkStateOut | undefined): string[] {
  if (!config || !state) return [];
  return buildNetworkDiff(config, { hostname: state.hostname, dns: state.dns, interfaces: state.interfaces, routes: state.routes.static });
}

/** Birinchi yuklanganda va pending holati yechilganda (tasdiqlandi/qaytarildi/muddati tugadi) draft'ni holatdan qayta quradi. */
function syncDraftFromState(
  state: NetworkStateOut | undefined,
  draft: NetworkDraft | null,
  prevPendingId: { current: string | null },
  setDraft: (d: NetworkDraft) => void,
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

function applyDraftUpdate(draft: NetworkDraft | null, updater: (d: NetworkDraft) => NetworkDraft): NetworkDraft | null {
  return draft ? updater(draft) : draft;
}

function discardDraft(state: NetworkStateOut | undefined, setDraft: (d: NetworkDraft) => void): void {
  if (state) setDraft(stateToDraft(state));
}

function requestValidate(
  draft: NetworkDraft | null, timeoutS: number, validateM: ValidateMutation,
  onInvalid: (errors: NetworkFieldError[]) => void,
  onValid: (diff: string[], warnings: string[]) => void,
  onError: (e: unknown) => void,
): void {
  if (!draft) return;
  const config = draftToConfig(draft, timeoutS);
  validateM.mutate(config, {
    onSuccess: (result) => (result.ok ? onValid(result.diff, result.warnings) : onInvalid(normalizeServerErrors(result.errors, config))),
    onError,
  });
}

function requestApply(
  draft: NetworkDraft | null, timeoutS: number, applyM: ApplyMutation,
  onApplied: () => void,
  onFieldErrors: (fields: NetworkFieldError[]) => void,
  onError: (e: unknown) => void,
): void {
  if (!draft) return;
  const config = draftToConfig(draft, timeoutS);
  applyM.mutate(config, {
    onSuccess: onApplied,
    onError: (e) => {
      const fields = isApiError(e) ? (e.details?.fields as NetworkFieldError[] | undefined) : undefined;
      return fields ? onFieldErrors(normalizeServerErrors(fields, config)) : onError(e);
    },
  });
}

function resolvePending(pendingId: string | undefined, mutation: PendingMutation, onSuccess: () => void, onError: (e: unknown) => void): void {
  if (!pendingId) return;
  mutation.mutate(pendingId, { onSuccess, onError });
}

function NetworkReadyView({
  t, state, draft, errors, timeoutS, onTimeoutChange, confirm, pendingActions, draftActions,
}: {
  t: TFunc;
  state: NetworkStateOut;
  draft: NetworkDraft;
  errors: NetworkFieldError[];
  timeoutS: number;
  onTimeoutChange: (s: number) => void;
  confirm: { open: boolean; diff: string[]; warnings: string[]; loading: boolean; onConfirm: () => void; onClose: () => void };
  pendingActions: { onConfirm: () => void; onRollback: () => void; onExpire: () => void; confirmLoading: boolean; rollbackLoading: boolean };
  draftActions: {
    lastResultDismissed: boolean; onDismissLastResult: () => void;
    diffCount: number; onDiscard: () => void; onApply: () => void; applyLoading: boolean;
    onChangeGeneral: (patch: Partial<NetworkDraft>) => void;
    onChangeInterface: (name: string, next: NetworkDraft['interfaces'][number]) => void;
    onChangeRoutes: (next: NetworkDraft['routes']) => void;
  };
}) {
  const locked = isNetworkLocked(state);
  const tabs = buildNetworkTabs({
    draft, state, errors, locked,
    onChangeGeneral: draftActions.onChangeGeneral,
    onChangeInterface: draftActions.onChangeInterface,
    onChangeRoutes: draftActions.onChangeRoutes,
    t,
  });

  return (
    <AppShellPage title={t('title')}>
      <div className="flex flex-col gap-4">
        <NetworkBanners
          state={state}
          hasValidateErrors={errors.length > 0}
          showLastResult={!draftActions.lastResultDismissed && !state.pending}
          onDismissLastResult={draftActions.onDismissLastResult}
          t={t}
        />

        {state.pending ? (
          <>
            <PendingBanner pending={state.pending} {...pendingActions} />
            <PendingSummary summary={state.pending.summary} />
          </>
        ) : (
          <Tabs items={tabs} label={t('title')} />
        )}
      </div>

      {!state.pending && draftActions.diffCount > 0 && !locked && (
        <StickyDraftBar count={draftActions.diffCount} onDiscard={draftActions.onDiscard} onApply={draftActions.onApply} loading={draftActions.applyLoading} />
      )}

      <ConfirmApplyModal open={confirm.open} diff={confirm.diff} warnings={confirm.warnings} timeoutS={timeoutS} onTimeoutChange={onTimeoutChange} onConfirm={confirm.onConfirm} onClose={confirm.onClose} loading={confirm.loading} />
    </AppShellPage>
  );
}

/** S38 — faqat `*` ruxsatiga ko'rinadi (`screens.ts`, group `system`); shartnoma: GET/POST `/network/*`. */
export function NetworkPage() {
  const { t } = useTranslation('network');
  const toast = useToast();
  const { data: state, isLoading, isError, refetch } = useNetworkState();
  const validateM = useValidateNetwork();
  const applyM = useApplyNetwork();
  const confirmM = useConfirmNetwork();
  const rollbackM = useRollbackNetwork();

  const [draft, setDraftRaw] = useState<NetworkDraft | null>(null);
  const [validateErrors, setValidateErrors] = useState<NetworkFieldError[]>([]);
  const [timeoutS, setTimeoutS] = useState(DEFAULT_TIMEOUT_S);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmDiff, setConfirmDiff] = useState<string[]>([]);
  const [confirmWarnings, setConfirmWarnings] = useState<string[]>([]);
  const [lastResultDismissed, setLastResultDismissed] = useState(false);
  const prevPendingId = useRef<string | null>(null);

  useEffect(() => {
    syncDraftFromState(state, draft, prevPendingId, setDraftRaw, () => {
      setValidateErrors([]);
      setLastResultDismissed(false);
    });
  }, [state, draft]);

  const updateDraft = (updater: (d: NetworkDraft) => NetworkDraft) => {
    setValidateErrors([]);
    setDraftRaw((d) => applyDraftUpdate(d, updater));
  };
  const handleDiscard = () => { discardDraft(state, setDraftRaw); setValidateErrors([]); };
  const handleApplyClick = () => requestValidate(
    draft, timeoutS, validateM,
    setValidateErrors,
    (diffLines, warnings) => { setConfirmDiff(diffLines); setConfirmWarnings(warnings); setConfirmOpen(true); },
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

  const config = useMemo(() => computeConfig(draft, timeoutS), [draft, timeoutS]);
  const diff = useMemo(() => computeDiff(config, state), [config, state]);

  if (isLoading || !state || !draft) {
    return <NetworkLoadingState title={t('title')} isError={isError} onRetry={() => void refetch()} t={t} />;
  }

  return (
    <NetworkReadyView
      t={t}
      state={state}
      draft={draft}
      errors={validateErrors}
      timeoutS={timeoutS}
      onTimeoutChange={setTimeoutS}
      confirm={{ open: confirmOpen, diff: confirmDiff, warnings: confirmWarnings, loading: applyM.isPending, onConfirm: handleConfirmApply, onClose: () => setConfirmOpen(false) }}
      pendingActions={{ onConfirm: handleConfirmPending, onRollback: handleRollbackPending, onExpire: () => void refetch(), confirmLoading: confirmM.isPending, rollbackLoading: rollbackM.isPending }}
      draftActions={{
        lastResultDismissed, onDismissLastResult: () => setLastResultDismissed(true),
        diffCount: diff.length, onDiscard: handleDiscard, onApply: handleApplyClick, applyLoading: validateM.isPending,
        onChangeGeneral: (patch) => updateDraft((d) => ({ ...d, ...patch })),
        onChangeInterface: (name, next) => updateDraft((d) => ({ ...d, interfaces: d.interfaces.map((i) => (i.name === name ? next : i)) })),
        onChangeRoutes: (next) => updateDraft((d) => ({ ...d, routes: next })),
      }}
    />
  );
}
