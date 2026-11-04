// Sana va vaqt sozlamalari: vaqt zonasi, NTP yoqish/o'chirish, NTP serverlar — to'g'ridan-to'g'ri qo'llanadi
// (pending/confirm yo'q, network/firewalldan farqli). Shartnoma: ../../replica/m12-contract.md §B1.
// Faqat `*` ruxsatiga ko'rinadi (`screens.ts`, group `system`).
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { apiErrorMessage, isApiError } from '@/api/errors';
import { useApplyTime, useSystemTime } from '@/api/queries';
import type { TimeConfigIn, TimeFieldError } from '@/api/types';
import { listTimezones, MAX_NTP_SERVERS } from '@/domain/systemTime';
import { splitList } from '@/lib/validators';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Field, Input, Textarea } from '@/ui/Field';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

type TimeDraft = { timezone: string; ntpEnabled: boolean; ntpServersText: string };
type TFunc = (k: string, v?: Record<string, unknown>) => string;

function draftToConfig(draft: TimeDraft): TimeConfigIn {
  return { timezone: draft.timezone.trim(), ntp_enabled: draft.ntpEnabled, ntp_servers: splitList(draft.ntpServersText) };
}

function errorFor(errors: TimeFieldError[], field: string): string | undefined {
  return errors.find((e) => e.field === field)?.message;
}

/** `nowLabel` aniq "(UTC)" deydi — brauzer/tenant zonasiga aylantirmaymiz (`lib/time.ts`dagi `formatDateTime`dan farqli). */
function formatUtc(iso: string): string {
  return iso.replace('T', ' ').replace(/\.\d+Z?$/, '').replace(/Z$/, '');
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

function StatusSummary({ nowUtc, backend, synced, t }: { nowUtc: string; backend: string; synced: boolean; t: TFunc }) {
  return (
    <div className="flex flex-wrap gap-6 rounded-md border border-line bg-surface-2 px-3 py-2.5 text-sm text-fg">
      <span className="num">{t('nowLabel')}: {formatUtc(nowUtc)}</span>
      <span>{t('backendLabel')}: {backend}</span>
      <span>{synced ? t('syncedYes') : t('syncedNo')}</span>
    </div>
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
  return (
    <div className="flex max-w-xl flex-col gap-4">
      <Field label={t('timezoneLabel')} error={errorFor(errors, 'timezone')}>
        {(a) => (
          <>
            <Input
              {...a}
              list="innova-timezones"
              placeholder={t('timezoneSearchPlaceholder')}
              disabled={locked}
              value={draft.timezone}
              onChange={(e) => onChange({ timezone: e.target.value })}
            />
            <datalist id="innova-timezones">
              {listTimezones().map((z) => <option key={z} value={z} />)}
            </datalist>
          </>
        )}
      </Field>

      <Toggle
        checked={draft.ntpEnabled}
        onCheckedChange={(v) => onChange({ ntpEnabled: v })}
        label={t('ntpEnabledLabel')}
        disabled={locked}
      />

      <Field label={t('ntpServersLabel')} hint={t('ntpServersHint', { max: MAX_NTP_SERVERS })} error={errorFor(errors, 'ntp_servers')}>
        {(a) => (
          <Textarea
            {...a}
            disabled={locked || !draft.ntpEnabled}
            value={draft.ntpServersText}
            onChange={(e) => onChange({ ntpServersText: e.target.value })}
          />
        )}
      </Field>
    </div>
  );
}

/** S48 (shartnomada S-raqam yo'q) — GET/PUT `/system/time` (../../replica/m12-contract.md §B1). */
export function TimeSettingsPage() {
  const { t } = useTranslation('time');
  const toast = useToast();
  const { data: state, isLoading, isError, refetch } = useSystemTime();
  const applyM = useApplyTime();

  const [draft, setDraft] = useState<TimeDraft | null>(null);
  const [errors, setErrors] = useState<TimeFieldError[]>([]);

  useEffect(() => {
    if (state && draft === null) {
      setDraft({ timezone: state.timezone, ntpEnabled: state.ntp_enabled, ntpServersText: state.ntp_servers.join('\n') });
    }
  }, [state, draft]);

  const handleChange = (patch: Partial<TimeDraft>) => {
    setErrors([]);
    setDraft((d) => (d ? { ...d, ...patch } : d));
  };

  const handleSave = () => {
    if (!draft) return;
    applyM.mutate(draftToConfig(draft), {
      onSuccess: () => toast({ kind: 'success', title: t('savedToast') }),
      onError: (e) => {
        const fields = isApiError(e) ? (e.details?.fields as TimeFieldError[] | undefined) : undefined;
        if (fields) setErrors(fields);
        else toast({ kind: 'error', title: apiErrorMessage(e) });
      },
    });
  };

  if (isLoading || !state || !draft) {
    return <TimeLoadingState title={t('title')} isError={isError} onRetry={() => void refetch()} t={t} />;
  }

  const locked = state.readonly_reason !== null;

  return (
    <AppShellPage title={t('title')}>
      <div className="flex flex-col gap-4">
        {locked && (
          <div className="rounded-md border border-warning/30 bg-warning-soft px-3 py-2.5 text-sm text-on-warning-soft">
            {t('readonlyBanner', { reason: state.readonly_reason })}
          </div>
        )}
        {errors.length > 0 && (
          <div className="rounded-md border border-danger/25 bg-danger-soft px-3 py-2.5 text-sm text-on-danger-soft">{t('errorsBanner')}</div>
        )}

        <StatusSummary nowUtc={state.now_utc} backend={state.backend} synced={state.synced} t={t} />
        <TimeForm draft={draft} errors={errors} locked={locked} onChange={handleChange} t={t} />

        {!locked && (
          <div>
            <Button variant="primary" loading={applyM.isPending} onClick={handleSave}>{t('save')}</Button>
          </div>
        )}
      </div>
    </AppShellPage>
  );
}
