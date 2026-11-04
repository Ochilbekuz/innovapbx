// Server soati: server zonasidagi vaqt (har soniya yuradi), UTC, NTP manbai va «Hozir sinxronlash».
// Server vaqti brauzer soatiga emas, oxirgi javobdagi `now_utc` ga tayanadi — farq bo'lsa shu ko'rinadi.
import { RefreshCw } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { TimeStateOut } from '@/api/types';
import { formatInZone, utcOffsetLabel } from '@/domain/systemTime';
import { cn } from '@/lib/cn';
import { Button } from '@/ui/Button';

type TFunc = (k: string, v?: Record<string, unknown>) => string;

function useNow(stepMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), stepMs);
    return () => clearInterval(id);
  }, [stepMs]);
  return now;
}

/** `fetchedAt` — javob kelgan brauzer vaqti (`dataUpdatedAt`); undan beri o'tgan vaqt server soatiga qo'shiladi. */
export function useServerNow(nowUtc: string, fetchedAt: number): Date {
  const now = useNow();
  return new Date(Date.parse(nowUtc) + Math.max(0, now - fetchedAt));
}

type Props = {
  state: TimeStateOut;
  fetchedAt: number;
  canSync: boolean;
  syncing: boolean;
  onSync: () => void;
  t: TFunc;
};

export function ClockPanel({ state, fetchedAt, canSync, syncing, onSync, t }: Props) {
  const serverNow = useServerNow(state.now_utc, fetchedAt);
  const [date, time] = formatInZone(serverNow, state.timezone).split(' ');
  const ok = state.ntp_enabled && state.synced;

  return (
    <section className="flex flex-col gap-4 rounded-lg border border-line bg-surface-2 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-col gap-1">
        <span className="text-xs font-medium uppercase tracking-wide text-muted">{t('serverTimeLabel')}</span>
        <span className="num text-3xl font-semibold leading-none tracking-tight text-fg" aria-live="off">{time}</span>
        <span className="num text-sm text-muted">
          {date} · {state.timezone} ({utcOffsetLabel(state.timezone, serverNow)}) · UTC {formatInZone(serverNow, 'UTC').split(' ')[1]}
        </span>
      </div>

      <div className="flex flex-col gap-2 sm:items-end">
        <span className={cn('inline-flex items-center gap-1.5 text-sm', ok ? 'text-success' : 'text-warning')}>
          <span aria-hidden className={cn('size-2 rounded-full', ok ? 'bg-success' : 'bg-warning')} />
          {!state.ntp_enabled ? t('ntpOff') : state.synced ? t('syncedYes') : t('syncedNo')}
        </span>
        <span className="text-sm text-muted">
          {t('syncServerLabel')}: <span className="num text-fg">{state.sync_server ?? t('syncServerNone')}</span> · {state.backend}
        </span>
        {canSync && (
          <Button size="sm" variant="secondary" loading={syncing} disabled={!state.ntp_enabled} onClick={onSync}>
            <RefreshCw aria-hidden />
            {t('syncNow')}
          </Button>
        )}
      </div>
    </section>
  );
}
