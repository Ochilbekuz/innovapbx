// Sana va vaqt sozlamalari: vaqt zonasi (server + PBX ish vaqti qoidalari), NTP, «Hozir sinxronlash» — to'g'ridan-to'g'ri qo'llanadi
// (pending/confirm yo'q, network/firewalldan farqli). Shartnoma: ../../replica/m12-contract.md §B1.
// Faqat `*` ruxsatiga ko'rinadi (`screens.ts`, group `system`).
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { apiErrorMessage, isApiError } from '@/api/errors';
import { useApplyTime, useSyncTime, useSystemTime } from '@/api/queries';
import type { TimeConfigIn, TimeFieldError, TimeStateOut } from '@/api/types';
import { defaultNtpServers, formatInZone, MAX_NTP_SERVERS } from '@/domain/systemTime';
import { applyToast } from '@/lib/applyToast';
import { splitList } from '@/lib/validators';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Field, Textarea } from '@/ui/Field';
import { Toggle } from '@/ui/Toggle';
import { type ToastInput, useToast } from '@/ui/Toast';
import { ClockPanel } from './ClockPanel';
import { TimezonePicker } from './TimezonePicker';

type TimeDraft = { timezone: string; ntpEnabled: boolean; ntpServersText: string };
type TFunc = (k: string, v?: Record<string, unknown>) => string;

function draftToConfig(draft: TimeDraft): TimeConfigIn {
  return { timezone: draft.timezone.trim(), ntp_enabled: draft.ntpEnabled, ntp_servers: splitList(draft.ntpServersText) };
}

function errorFor(errors: TimeFieldError[], field: string): string | undefined {
  return errors.find((e) => e.field === field)?.message;
}

function TimeLoadingState({ title, isError, onRetry, t }: { title: string; isError: boolean; onRetry: () => void; t: (k: string) => string }) {
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

function TimeForm({
  draft, errors, locked, onChange, t,
}: {
  draft: TimeDraft;
  errors: TimeFieldError[];
  locked: boolean;
  onChange: (patch: Partial<TimeDraft>) => void;
  t: TFunc;
}) {
  const zone = draft.timezone;
  const pool = defaultNtpServers(zone);
  return (
    <div className="flex max-w-xl flex-col gap-4">
      <Field label={t('timezoneLabel')} hint={t('timezoneHint', { time: formatInZone(new Date(), zone) })} error={errorFor(errors, 'timezone')}>
        {(a) => (
          <TimezonePicker
            {...a}
            value={zone}
            disabled={locked}
            onChange={(z) => onChange({ timezone: z })}
            searchPlaceholder={t('timezoneSearchPlaceholder')}
            noMatch={t('timezoneNoMatch')}
          />
        )}
      </Field>

      <Toggle
        checked={draft.ntpEnabled}
        onCheckedChange={(v) => onChange({ ntpEnabled: v })}
        label={t('ntpEnabledLabel')}
        description={t('ntpEnabledDescription')}
        disabled={locked}
      />

      <Field label={t('ntpServersLabel')} hint={t('ntpServersHint', { max: MAX_NTP_SERVERS, pool: pool[0] })} error={errorFor(errors, 'ntp_servers')}>
        {(a) => (
          <Textarea
            {...a}
            disabled={locked || !draft.ntpEnabled}
            placeholder={pool.join('\n')}
            value={draft.ntpServersText}
            onChange={(e) => onChange({ ntpServersText: e.target.value })}
          />
        )}
      </Field>
    </div>
  );
}

function syncToast(res: TimeStateOut, t: TFunc): ToastInput {
  const description = res.sync_server ? t('syncedToastServer', { server: res.sync_server }) : undefined;
  return { kind: 'success', title: t('syncedToast'), description };
}

function fieldErrors(e: unknown): TimeFieldError[] | undefined {
  return isApiError(e) ? (e.details?.fields as TimeFieldError[] | undefined) : undefined;
}

/** Saqlash (+ PBX zonasi o'zgarsa dialplan natijasi) va «Hozir sinxronlash» — xabarlari bilan. */
function useTimeActions(onFieldErrors: (errors: TimeFieldError[]) => void, t: TFunc) {
  const toast = useToast();
  const applyM = useApplyTime();
  const syncM = useSyncTime();

  const save = (draft: TimeDraft) =>
    applyM.mutate(draftToConfig(draft), {
      onSuccess: (res) => {
        toast({ kind: 'success', title: t('savedToast') });
        if (res.apply) toast(applyToast(res.apply, t('pbxTimezoneApplied')));
      },
      onError: (e) => {
        const fields = fieldErrors(e);
        if (fields) onFieldErrors(fields);
        else toast({ kind: 'error', title: apiErrorMessage(e) });
      },
    });

  const sync = () =>
    syncM.mutate(undefined, {
      onSuccess: (res) => toast(syncToast(res, t)),
      onError: (e) => toast({ kind: 'error', title: t('syncFailedToast'), description: apiErrorMessage(e) }),
    });

  return { save, sync, saving: applyM.isPending, syncing: syncM.isPending };
}

/** Qoralama serverdan birinchi kelgan holatdan bir marta olinadi; keyin foydalanuvchiniki. */
function useTimeDraft(state: TimeStateOut | undefined) {
  const [draft, setDraft] = useState<TimeDraft | null>(null);
  useEffect(() => {
    if (state && draft === null) {
      setDraft({ timezone: state.timezone, ntpEnabled: state.ntp_enabled, ntpServersText: state.ntp_servers.join('\n') });
    }
  }, [state, draft]);
  const patch = (p: Partial<TimeDraft>) => setDraft((d) => (d ? { ...d, ...p } : d));
  return [draft, patch] as const;
}

function Banners({ readonlyReason, hasErrors, t }: { readonlyReason: string | null; hasErrors: boolean; t: TFunc }) {
  return (
    <>
      {readonlyReason !== null && (
        <div className="rounded-md border border-warning/30 bg-warning-soft px-3 py-2.5 text-sm text-on-warning-soft">
          {t('readonlyBanner', { reason: readonlyReason })}
        </div>
      )}
      {hasErrors && (
        <div className="rounded-md border border-danger/25 bg-danger-soft px-3 py-2.5 text-sm text-on-danger-soft">{t('errorsBanner')}</div>
      )}
    </>
  );
}

/** S48 (shartnomada S-raqam yo'q) — GET/PUT `/system/time`, POST `/system/time/sync` (../../replica/m12-contract.md §B1). */
export function TimeSettingsPage() {
  const { t } = useTranslation('time');
  const { data: state, dataUpdatedAt, isLoading, isError, refetch } = useSystemTime();
  const [draft, patchDraft] = useTimeDraft(state);
  const [errors, setErrors] = useState<TimeFieldError[]>([]);
  const actions = useTimeActions(setErrors, t);

  if (isLoading || !state || !draft) {
    return <TimeLoadingState title={t('title')} isError={isError} onRetry={() => void refetch()} t={t} />;
  }

  const locked = state.readonly_reason !== null;
  const handleChange = (p: Partial<TimeDraft>) => {
    setErrors([]);
    patchDraft(p);
  };

  return (
    <AppShellPage title={t('title')}>
      <div className="flex flex-col gap-4">
        <Banners readonlyReason={state.readonly_reason} hasErrors={errors.length > 0} t={t} />
        <ClockPanel state={state} fetchedAt={dataUpdatedAt} canSync={!locked} syncing={actions.syncing} onSync={actions.sync} t={t} />
        <TimeForm draft={draft} errors={errors} locked={locked} onChange={handleChange} t={t} />
        {!locked && (
          <div>
            <Button variant="primary" loading={actions.saving} onClick={() => actions.save(draft)}>{t('save')}</Button>
          </div>
        )}
      </div>
    </AppShellPage>
  );
}
