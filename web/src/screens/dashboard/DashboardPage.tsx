import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  AlertTriangle, ArrowLeftRight, OctagonX, ParkingSquare, PhoneCall, PhoneIncoming,
  PhoneMissed, PhoneOutgoing, Users,
} from 'lucide-react';
import { useDashboard, useParking } from '@/api/queries';
import { useCanView } from '@/auth/permissions';
import type {
  CallDirection, DashboardAlert, DashboardHourBucket, DashboardLiveCall, DashboardMissedCall, DashboardQueueLive, ParkedCall,
} from '@/api/types';
import { formatDurationSec, formatTime } from '@/lib/time';
import { cn } from '@/lib/cn';
import { diskLevel, trunkHealthLevel } from '@/lib/health';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { BarChart, ChartCard, ChartLegend } from '@/ui/Chart';
import type { HealthItem } from '@/ui/Health';
import { HealthList } from '@/ui/Health';
import { Kpi } from '@/ui/Kpi';
import { Badge, type Tone } from '@/ui/Status';

const DIRECTION_ICON: Record<CallDirection, typeof PhoneIncoming> = { in: PhoneIncoming, out: PhoneOutgoing, internal: ArrowLeftRight };
const ALERT_TONE: Record<DashboardAlert['level'], Tone> = { warn: 'warning', danger: 'danger' };

/** S03 — bosh panel: tizim sogʻligʻi, jonli qoʻngʻiroqlar/navbatlar, bugungi hajm + soatlik grafik, oʻtkazib yuborilganlar va ogohlantirishlar. 10s da yangilanadi. */
export function DashboardPage() {
  const { t } = useTranslation('dashboard');
  const { data, isLoading, isError, refetch } = useDashboard();
  const directionLabel: Record<CallDirection, string> = { in: t('direction.in'), out: t('direction.out'), internal: t('direction.internal') };
  const registrationShort: Record<'registered' | 'rejected' | 'unregistered', string> = {
    registered: t('registration.registered'), rejected: t('registration.rejected'), unregistered: t('registration.unregistered'),
  };

  if (isLoading || !data) {
    return (
      <AppShellPage title={t('title')}>
        {isError ? (
          <div className="flex flex-col items-center gap-2 rounded-md border border-dashed border-line px-3 py-6 text-center text-sm text-muted">
            <p>{t('loadFailed')}</p>
            <Button size="sm" variant="secondary" onClick={() => void refetch()}>{t('retry')}</Button>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }, (_, i) => <Kpi key={i} label="…" value={null} loading />)}
          </div>
        )}
      </AppShellPage>
    );
  }

  const healthItems: HealthItem[] = [
    { id: 'asterisk', label: t('health.asterisk'), level: data.health.asterisk.up ? 'ok' : 'crit', value: data.health.asterisk.version ?? undefined, reason: data.health.asterisk.up ? undefined : t('health.asteriskDown') },
    { id: 'db', label: t('health.database'), level: data.health.db.up ? 'ok' : 'crit', reason: data.health.db.up ? undefined : t('health.dbDown') },
    { id: 'disk', label: t('health.disk'), level: diskLevel(data.health.disk.used_pct), value: `${data.health.disk.used_pct}%`, reason: diskLevel(data.health.disk.used_pct) !== 'ok' ? t('health.freeSpace', { gb: data.health.disk.free_gb }) : undefined },
    ...data.health.trunks.map((tr) => ({
      id: tr.id,
      label: t('health.trunk', { name: tr.name }),
      level: trunkHealthLevel(tr.state),
      value: tr.registration ? registrationShort[tr.registration] : undefined,
      reason: tr.reason ?? undefined,
    })),
  ];

  return (
    <AppShellPage title={t('title')}>
      {data.alerts.length > 0 && (
        <ul className="mb-4 flex flex-col gap-2">
          {data.alerts.map((a, i) => (
            <li key={i}>
              <Link
                to={a.link}
                className={cn(
                  'flex items-center gap-2.5 rounded-md border px-3 py-2.5 text-sm transition-colors duration-fast hover:brightness-[0.98]',
                  a.level === 'danger' ? 'border-danger/25 bg-danger-soft text-on-danger-soft' : 'border-warning/30 bg-warning-soft text-on-warning-soft',
                )}
              >
                {a.level === 'danger' ? <OctagonX aria-hidden className="size-4 shrink-0" /> : <AlertTriangle aria-hidden className="size-4 shrink-0" />}
                <span className="flex-1">{a.text}</span>
                <Badge tone={ALERT_TONE[a.level]}>{t('alertView')}</Badge>
              </Link>
            </li>
          ))}
        </ul>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Kpi label={t('kpi.activeCalls')} value={String(data.live.active_calls)} />
        <Kpi label={t('kpi.todayTotal')} value={String(data.today.total)} unit={t('kpi.unit')} />
        <Kpi label={t('kpi.answered')} value={String(data.today.answered)} unit={t('kpi.unit')} />
        <Kpi label={t('kpi.missed')} value={String(data.today.missed)} unit={t('kpi.unit')} />
        <Kpi label={t('kpi.avgWait')} value={data.today.avg_wait_s !== null ? formatDurationSec(data.today.avg_wait_s) : null} emptyText={t('kpi.noCallsYet')} />
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[1.3fr_1fr]">
        <HourlyChart buckets={data.today.by_hour} />
        <HealthList
          items={healthItems}
          action={<Link to="/settings/status" className="text-xs font-medium text-accent hover:underline">{t('health.viewDetails')}</Link>}
        />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <LiveCallsCard calls={data.live.calls} directionLabel={directionLabel} />
        <QueuesLiveCard queues={data.queues} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <MissedCallsCard missed={data.missed} />
        <ParkedCallsCard />
      </div>
    </AppShellPage>
  );
}

function HourlyChart({ buckets }: { buckets: DashboardHourBucket[] }) {
  const { t } = useTranslation('dashboard');
  return (
    <ChartCard
      ariaLabel={t('hourly.ariaLabel')}
      title={t('hourly.title')}
      legend={
        <ChartLegend
          items={[
            { swatchClass: 'bg-chart-1', label: t('hourly.legendIn') },
            { swatchClass: 'bg-chart-2', label: t('hourly.legendOut') },
            { swatchClass: 'bg-danger', label: t('hourly.legendMissed') },
          ]}
        />
      }
    >
      <BarChart
        data={buckets}
        emptyText={t('hourly.empty')}
        tickLabel={(b) => (b.hour % 6 === 0 ? String(b.hour).padStart(2, '0') : null)}
        series={[
          { key: 'in', swatchClass: 'fill-chart-1', value: (b) => b.in },
          { key: 'out', swatchClass: 'fill-chart-2', value: (b) => b.out },
          { key: 'missed', swatchClass: 'fill-danger', value: (b) => b.missed },
        ]}
      />
    </ChartCard>
  );
}

function LiveCallsCard({ calls, directionLabel }: { calls: DashboardLiveCall[]; directionLabel: Record<CallDirection, string> }) {
  const { t } = useTranslation('dashboard');
  return (
    <section aria-label={t('live.ariaLabel')} className="overflow-hidden rounded-lg border border-line bg-surface shadow-card">
      <header className="flex items-center gap-2 border-b border-line px-4 py-2.5">
        <PhoneCall aria-hidden className="size-4 text-brand" />
        <h3 className="font-display text-base font-semibold">{t('live.title')}</h3>
        {calls.length > 0 && <Badge tone="accent">{calls.length}</Badge>}
      </header>
      {calls.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-muted">{t('live.empty')}</p>
      ) : (
        <ul className="divide-y divide-line">
          {calls.map((c) => {
            const Icon = DIRECTION_ICON[c.direction];
            return (
              <li key={c.channel} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                <Icon aria-hidden className="size-4 shrink-0 text-muted" />
                <span className="num flex-1 truncate">{c.from} <span className="text-muted">→</span> {c.to}</span>
                <span className="text-xs text-muted">{directionLabel[c.direction]}</span>
                <span className="num text-xs text-muted">{formatDurationSec(c.duration_s)}</span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function QueuesLiveCard({ queues }: { queues: DashboardQueueLive[] }) {
  const { t } = useTranslation('dashboard');
  return (
    <section aria-label={t('queues.ariaLabel')} className="overflow-hidden rounded-lg border border-line bg-surface shadow-card">
      <header className="flex items-center gap-2 border-b border-line px-4 py-2.5">
        <Users aria-hidden className="size-4 text-brand" />
        <h3 className="font-display text-base font-semibold">{t('queues.title')}</h3>
      </header>
      {queues.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-muted">{t('queues.empty')}</p>
      ) : (
        <ul className="divide-y divide-line">
          {queues.map((q) => (
            <li key={q.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
              <span className="flex-1 truncate font-medium text-fg">{q.name}</span>
              <span className="num text-xs text-muted">{q.members_online} {t('queues.online')}</span>
              <Badge tone={q.waiting > 0 ? 'warning' : 'neutral'}>{q.waiting} {t('queues.waiting')}</Badge>
              {q.waiting > 0 && <span className="num text-xs text-muted">{formatDurationSec(q.longest_wait_s)}</span>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/**
 * M2a §3 — park (700-720): hozir kutayotgan qoʻngʻiroqlar roʻyxati, faqat koʻrish. 10s da yangilanadi.
 * `/parking` `apps:view` talab qiladi (M7) — operatorda 403 boʻladi, shuning uchun karta operatorda umuman koʻrinmaydi.
 */
function ParkedCallsCard() {
  const { t } = useTranslation('dashboard');
  const canView = useCanView('apps');
  const { data, isLoading, isError } = useParking(canView);
  const parked: ParkedCall[] = data?.parked ?? [];

  if (!canView) return null;

  return (
    <section aria-label={t('parking.ariaLabel')} className="overflow-hidden rounded-lg border border-line bg-surface shadow-card">
      <header className="flex items-center gap-2 border-b border-line px-4 py-2.5">
        <ParkingSquare aria-hidden className="size-4 text-brand" />
        <h3 className="font-display text-base font-semibold">{t('parking.title')}</h3>
        {parked.length > 0 && <Badge tone="accent">{parked.length}</Badge>}
      </header>
      {isLoading ? (
        <p className="px-4 py-6 text-center text-sm text-muted">{t('parking.loading')}</p>
      ) : isError ? (
        <p className="px-4 py-6 text-center text-sm text-danger">{t('parking.loadFailed')}</p>
      ) : parked.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-muted">{t('parking.empty')}</p>
      ) : (
        <ul className="divide-y divide-line">
          {parked.map((p) => (
            <li key={p.slot} className="flex items-center gap-3 px-4 py-2.5 text-sm">
              <span className="num shrink-0 font-medium text-fg">{p.slot}</span>
              <span className="num flex-1 truncate text-muted">{p.callerid}</span>
              <span className="text-xs text-muted">{t('parking.parkedBy', { who: p.parked_by })}</span>
              <span className="num text-xs text-muted">{formatTime(p.since)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function MissedCallsCard({ missed }: { missed: DashboardMissedCall[] }) {
  const { t } = useTranslation('dashboard');
  return (
    <section aria-label={t('missedCalls.ariaLabel')} className="overflow-hidden rounded-lg border border-line bg-surface shadow-card">
      <header className="flex items-center gap-2 border-b border-line px-4 py-2.5">
        <PhoneMissed aria-hidden className="size-4 text-warning" />
        <h3 className="font-display text-base font-semibold">{t('missedCalls.title')}</h3>
      </header>
      {missed.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-muted">{t('missedCalls.empty')}</p>
      ) : (
        <ul className="divide-y divide-line">
          {missed.map((m) => (
            <li key={m.uniqueid} className="flex flex-wrap items-center gap-3 px-4 py-2.5 text-sm">
              <span className="num w-16 shrink-0 text-xs text-muted">{formatTime(m.started_at)}</span>
              <span className="num flex-1 truncate font-medium text-fg">{m.src}</span>
              {m.did && <span className="num text-xs text-muted">→ {m.did}</span>}
              {m.called_back ? (
                <Badge tone="success">{t('missedCalls.calledBack')}</Badge>
              ) : (
                <>
                  <Badge tone="warning">{t('missedCalls.notCalledBack')}</Badge>
                  <a href={`tel:${m.src}`} className="text-xs font-medium text-accent hover:underline">{t('missedCalls.callBack')}</a>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
