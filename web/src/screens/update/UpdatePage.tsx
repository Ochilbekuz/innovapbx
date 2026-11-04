// S45 — Paneldan yangilash: joriy/yangi versiya, tasdiqlab yangilash, jonli jarayon kuzatish.
// Shartnoma: ../../replica/m11-update-contract.md §4 (API), §5 (frontend). Faqat `*` ruxsatiga ko'rinadi (`screens.ts`).
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CircleCheck, CircleX, LoaderCircle, RefreshCw, TriangleAlert } from 'lucide-react';
import { apiErrorMessage, isApiError } from '@/api/errors';
import { useCheckSystemUpdate, useStartSystemUpdate, useSystemUpdate, useSystemUpdateLog } from '@/api/queries';
import type { StartSystemUpdatePayload, SystemUpdateOut } from '@/api/types';
import {
  appendUpdateLog, EMPTY_LOG, isRestartingDuringUpdate, isScrolledAwayFromEnd, phaseStatus, scrollToEnd,
  shouldShowUpdateLog, updateLogPollMs, UPDATE_PHASES, type DisplayPhase, type QueryFailure, type UpdateLogAccum,
} from '@/domain/update';
import { cn } from '@/lib/cn';
import { formatDateTime } from '@/lib/time';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { useToast } from '@/ui/Toast';
import { ConfirmUpdateModal } from './ConfirmUpdateModal';
import { MarkdownLite } from './MarkdownLite';

type TFunc = (k: string, v?: Record<string, unknown>) => string;

function failureOf(e: unknown): QueryFailure {
  if (!e) return null;
  return { status: isApiError(e) ? e.status : null };
}

function isInitialLoadOrError(isLoading: boolean, isError: boolean, hasData: boolean): boolean {
  return !hasData && (isLoading || isError);
}

export function mismatchOrGenericMessage(e: unknown, t: TFunc): string {
  return isApiError(e) && e.code === 'update_version_mismatch' ? t('confirm.stale') : apiErrorMessage(e);
}

/** Jurnalni `offset`dan oʻsib boradigan holatga sinxronlaydi — faqat kerakli holatlarda (`shouldShowUpdateLog`) pollaydi. */
function useUpdateLogSync(state: SystemUpdateOut['state'] | undefined): UpdateLogAccum {
  const [log, setLog] = useState<UpdateLogAccum>(EMPTY_LOG);
  const logEnabled = shouldShowUpdateLog(state);
  const logQ = useSystemUpdateLog(log.offset, logEnabled, updateLogPollMs(state));

  useEffect(() => {
    if (logQ.data) setLog((prev) => appendUpdateLog(prev, logQ.data));
  }, [logQ.data]);

  return log;
}

/** "Tekshirish" va "Yangilashni boshlash" amallari — xato/409 (versiya eskirgan) xabarlarini ham shu yerda hal qiladi. */
function useUpdateActions(latest: string | null | undefined, refetch: () => unknown, t: TFunc) {
  const toast = useToast();
  const checkMut = useCheckSystemUpdate();
  const startMut = useStartSystemUpdate();

  const handleCheck = () => checkMut.mutate(undefined, {
    onError: (e) => toast({ kind: 'error', title: apiErrorMessage(e) }),
  });

  const startUpdate = (vars: StartSystemUpdatePayload, onSettled: () => void) => startMut.mutate(vars, {
    onSuccess: onSettled,
    onError: (e) => {
      onSettled();
      void refetch();
      toast({ kind: 'error', title: mismatchOrGenericMessage(e, t) });
    },
  });

  const handleConfirmUpdate = (onSettled: () => void) => {
    if (latest) startUpdate({ version: latest }, onSettled);
  };

  return { checkMut, startMut, handleCheck, handleConfirmUpdate };
}

function LoadOrErrorState({ t, isError, onRetry }: { t: TFunc; isError: boolean; onRetry: () => void }) {
  if (!isError) return <div className="flex flex-col gap-4"><div className="skeleton h-48 rounded-lg" /></div>;
  return (
    <div className="flex flex-col items-center gap-2 rounded-md border border-dashed border-line px-3 py-6 text-center text-sm text-muted">
      <p>{t('loadFailed')}</p>
      <Button size="sm" variant="secondary" onClick={onRetry}>{t('retry')}</Button>
    </div>
  );
}

function UpdateContent({
  info, log, restarting, checking, onCheck, onUpdateClick, t,
}: {
  info: SystemUpdateOut;
  log: UpdateLogAccum;
  restarting: boolean;
  checking: boolean;
  onCheck: () => void;
  onUpdateClick: () => void;
  t: TFunc;
}) {
  if (!info.agent) return <NoAgentCard t={t} />;
  return (
    <>
      <VersionCard data={info} checking={checking} onCheck={onCheck} onUpdateClick={onUpdateClick} t={t} />
      {info.state === 'updating' && <ProgressSection data={info} log={log} restarting={restarting} t={t} />}
      {info.state === 'done' && <DoneCard data={info} t={t} />}
      {info.state === 'failed' && <FailedCard data={info} log={log} t={t} />}
    </>
  );
}

/** `/settings/update` — faqat `*` ruxsatiga ko'rinadi (`screens.ts`, group `system`, fail-closed). */
export function UpdatePage() {
  const { t } = useTranslation('update');
  const { data, isLoading, isError, error, refetch } = useSystemUpdate();
  const log = useUpdateLogSync(data?.state);
  const restarting = isRestartingDuringUpdate(data?.state, failureOf(error));
  const [confirmOpen, setConfirmOpen] = useState(false);
  const { checkMut, startMut, handleCheck, handleConfirmUpdate } = useUpdateActions(data?.latest, refetch, t);

  if (isInitialLoadOrError(isLoading, isError, !!data)) {
    return (
      <AppShellPage title={t('title')}>
        <LoadOrErrorState t={t} isError={isError} onRetry={() => void refetch()} />
      </AppShellPage>
    );
  }

  const info = data!;

  return (
    <AppShellPage title={t('title')}>
      <div className="flex flex-col gap-4">
        <UpdateContent
          info={info}
          log={log}
          restarting={restarting}
          checking={checkMut.isPending || info.state === 'checking'}
          onCheck={handleCheck}
          onUpdateClick={() => setConfirmOpen(true)}
          t={t}
        />
      </div>
      <ConfirmUpdateModal
        open={confirmOpen}
        version={info.latest ?? ''}
        loading={startMut.isPending}
        onConfirm={() => handleConfirmUpdate(() => setConfirmOpen(false))}
        onClose={() => setConfirmOpen(false)}
      />
    </AppShellPage>
  );
}

function NoAgentCard({ t }: { t: TFunc }) {
  return (
    <section aria-label={t('noAgent.title')} className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-line bg-surface px-4 py-8 text-center">
      <h3 className="font-display text-base font-semibold text-fg">{t('noAgent.title')}</h3>
      <p className="max-w-md text-sm text-muted">{t('noAgent.body')}</p>
      <code className="num rounded-sm bg-surface-2 px-2.5 py-1 text-sm text-fg">{t('noAgent.cliHint')}</code>
    </section>
  );
}

function VersionCard({
  data, checking, onCheck, onUpdateClick, t,
}: {
  data: SystemUpdateOut;
  checking: boolean;
  onCheck: () => void;
  onUpdateClick: () => void;
  t: TFunc;
}) {
  return (
    <section aria-label={t('title')} className="overflow-hidden rounded-lg border border-line bg-surface shadow-card">
      <header className="flex items-center justify-between gap-2 border-b border-line px-4 py-2.5">
        <div className="flex items-center gap-2">
          <RefreshCw aria-hidden className="size-4 text-brand" />
          <h3 className="font-display text-base font-semibold">{t('title')}</h3>
        </div>
        <Button
          size="sm"
          variant="secondary"
          icon={<RefreshCw />}
          loading={checking}
          disabled={data.state === 'updating'}
          onClick={onCheck}
        >
          {checking ? t('version.checking') : t('version.checkButton')}
        </Button>
      </header>
      <div className="flex flex-col gap-3 px-4 py-3 text-sm">
        <div className="flex items-center justify-between gap-3">
          <span className="text-muted">{t('version.currentLabel')}</span>
          <span className="num font-medium text-fg">{data.current ?? '—'}</span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-muted">{t('version.checkedAtLabel')}</span>
          <span className="num text-fg">{data.checked_at ? formatDateTime(data.checked_at) : t('version.neverChecked')}</span>
        </div>
        {data.available && data.latest ? (
          <div className="flex flex-col gap-3 rounded-md border border-accent/30 bg-accent-soft/40 px-3 py-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h4 className="font-display text-sm font-semibold text-fg">{t('version.newVersionTitle', { version: data.latest })}</h4>
              {data.state !== 'updating' && (
                <Button size="sm" variant="primary" onClick={onUpdateClick}>{t('confirm.updateButton')}</Button>
              )}
            </div>
            {data.changelog.length > 0 && (
              <div>
                <h5 className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">{t('changelog.title')}</h5>
                <MarkdownLite text={data.changelog.map((c) => c.body).join('\n\n')} />
              </div>
            )}
          </div>
        ) : (
          <p className="text-muted">{t('version.upToDate')}</p>
        )}
      </div>
    </section>
  );
}

function PhaseStepper({ current, t }: { current: DisplayPhase | null; t: TFunc }) {
  return (
    <ol className="flex flex-wrap items-center gap-2">
      {UPDATE_PHASES.map((phase, i) => {
        const st = phaseStatus(phase, current);
        return (
          <li key={phase} className="flex items-center gap-2">
            <span
              className={cn(
                'flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium',
                st === 'done' && 'border-success/30 bg-success-soft text-on-success-soft',
                st === 'current' && 'border-accent/40 bg-accent-soft text-on-accent-soft',
                st === 'pending' && 'border-line bg-surface-2 text-muted',
              )}
            >
              {st === 'done' ? (
                <CircleCheck aria-hidden className="size-3.5" />
              ) : st === 'current' ? (
                <LoaderCircle aria-hidden className="size-3.5 animate-spin" />
              ) : (
                <span aria-hidden className="size-1.5 rounded-full bg-current" />
              )}
              {t(`progress.phase.${phase}`)}
            </span>
            {i < UPDATE_PHASES.length - 1 && <span aria-hidden className="h-px w-4 bg-line" />}
          </li>
        );
      })}
    </ol>
  );
}

/** Jurnal — 2s pollda `offset`dan oʻsib boradi; qoʻlda yuqoriga aylantirilsa avto-skroll toʻxtaydi. */
function LogViewer({ text, t }: { text: string; t: TFunc }) {
  const ref = useRef<HTMLPreElement>(null);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (!paused) scrollToEnd(ref.current);
  }, [text, paused]);

  const onScroll = () => setPaused(isScrolledAwayFromEnd(ref.current));
  const jumpToEnd = () => {
    setPaused(false);
    scrollToEnd(ref.current);
  };

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-xs font-medium uppercase tracking-wide text-muted">{t('progress.logTitle')}</h4>
        <LogResumeButton paused={paused} onClick={jumpToEnd} t={t} />
      </div>
      <pre
        ref={ref}
        onScroll={onScroll}
        className="num max-h-64 overflow-y-auto whitespace-pre-wrap rounded-md border border-line bg-surface-2 px-3 py-2.5 text-xs text-fg"
      >
        {text || ' '}
      </pre>
      {paused && <p className="text-xs text-muted">{t('progress.logPaused')}</p>}
    </div>
  );
}

function LogResumeButton({ paused, onClick, t }: { paused: boolean; onClick: () => void; t: TFunc }) {
  if (!paused) return null;
  return <Button size="sm" variant="ghost" onClick={onClick}>{t('progress.logResume')}</Button>;
}

function ProgressSection({
  data, log, restarting, t,
}: {
  data: SystemUpdateOut;
  log: UpdateLogAccum;
  restarting: boolean;
  t: TFunc;
}) {
  const current = (restarting ? 'restart' : data.phase) as DisplayPhase | null;
  return (
    <section aria-label={t('progress.title')} className="overflow-hidden rounded-lg border border-line bg-surface shadow-card">
      <header className="flex items-center gap-2 border-b border-line px-4 py-2.5">
        <RefreshCw aria-hidden className="size-4 animate-spin text-brand" />
        <h3 className="font-display text-base font-semibold">{t('progress.title')}</h3>
      </header>
      <div className="flex flex-col gap-4 px-4 py-3">
        <PhaseStepper current={current} t={t} />
        {restarting && (
          <div className="flex items-center gap-2 rounded-md border border-warning/30 bg-warning-soft px-3 py-2.5 text-sm text-on-warning-soft">
            <TriangleAlert aria-hidden className="size-4 shrink-0" />
            {t('progress.restarting')}
          </div>
        )}
        <LogViewer text={log.text} t={t} />
      </div>
    </section>
  );
}

function DoneCard({ data, t }: { data: SystemUpdateOut; t: TFunc }) {
  return (
    <section aria-label={t('done.title')} className="flex flex-col gap-3 rounded-lg border border-success/30 bg-success-soft px-4 py-4 text-on-success-soft">
      <div className="flex items-center gap-2">
        <CircleCheck aria-hidden className="size-5" />
        <h3 className="font-display text-base font-semibold">{t('done.title')}</h3>
      </div>
      <p className="text-sm">{t('done.body', { version: data.current ?? '' })}</p>
      <div>
        <Button variant="primary" onClick={() => window.location.reload()}>{t('done.reloadButton')}</Button>
      </div>
    </section>
  );
}

function FailedCard({ data, log, t }: { data: SystemUpdateOut; log: UpdateLogAccum; t: TFunc }) {
  const [showLog, setShowLog] = useState(false);
  const code = data.error;
  return (
    <section aria-label={t('failed.title')} className="flex flex-col gap-3 rounded-lg border border-danger/30 bg-danger-soft px-4 py-4 text-on-danger-soft">
      <div className="flex items-center gap-2">
        <CircleX aria-hidden className="size-5" />
        <h3 className="font-display text-base font-semibold">{code ? t(`error.${code}.title`) : t('failed.title')}</h3>
      </div>
      {code && <p className="text-sm">{t(`error.${code}.body`)}</p>}
      {data.backup && <p className="num text-sm">{t('failed.backupLabel')}: {data.backup}</p>}
      <div>
        <Button variant="secondary" onClick={() => setShowLog((v) => !v)}>{t('failed.viewLogButton')}</Button>
      </div>
      {showLog && <LogViewer text={log.text} t={t} />}
    </section>
  );
}
