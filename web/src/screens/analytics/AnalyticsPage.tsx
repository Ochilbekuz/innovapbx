import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { presetRange, validateRange, type DateRange, type RangePreset } from '@/domain/dateRange';
import {
  useQueues, useReportsAgents, useReportsDaily, useReportsHourly, useReportsQueues, useReportsSummary,
} from '@/api/queries';
import type { ReportsAgentRow, ReportsQueueRow } from '@/api/types';
import { formatDurationSec } from '@/lib/time';
import { AppShellPage } from '@/shell/AppShellPage';
import { BarChart, ChartCard, ChartLegend } from '@/ui/Chart';
import { Field, Input, Select } from '@/ui/Field';
import { Kpi } from '@/ui/Kpi';
import { DataTable, type Column } from '@/ui/Table';

const PRESETS: RangePreset[] = ['today', 'yesterday', '7d', '30d', 'custom'];

function pct(v: number | null): string {
  return v === null ? '—' : `${Math.round(v)}%`;
}
function secOrDash(v: number | null): string {
  return v === null ? '—' : formatDurationSec(v);
}

/** S13 — analitika: sana oralig'i, navbat filtri, KPI, kunlik/soatlik grafik, navbat/agent jadvallari (M2b §5). */
export function AnalyticsPage() {
  const { t } = useTranslation('analytics');
  const [preset, setPreset] = useState<RangePreset>('7d');
  const [custom, setCustom] = useState<DateRange>(() => presetRange('today', new Date()));
  const [queueId, setQueueId] = useState('');

  const range = presetRange(preset, new Date(), custom);
  const validation = validateRange(range);
  const { data: queues } = useQueues();
  const params = { ...range, queue_id: queueId || undefined };

  const enabled = validation.ok;
  const { data: summary, isLoading: summaryLoading } = useReportsSummary(enabled ? params : { from: '', to: '' }) ;
  const { data: daily } = useReportsDaily(enabled ? params : { from: '', to: '' });
  const { data: hourly } = useReportsHourly(enabled ? params : { from: '', to: '' });
  const { data: byQueue } = useReportsQueues(enabled ? params : { from: '', to: '' });
  const { data: byAgent } = useReportsAgents(enabled ? params : { from: '', to: '' });

  const dailyTick = useMemo(() => {
    const n = daily?.items.length ?? 0;
    const step = Math.max(1, Math.ceil(n / 8));
    return (row: { date: string }, i: number) => (i % step === 0 ? row.date.slice(5) : null);
  }, [daily?.items.length]);

  const queueColumns: Column<ReportsQueueRow>[] = [
    { key: 'name', header: t('queuesTable.column.name'), cell: (r) => r.name },
    { key: 'calls', header: t('queuesTable.column.calls'), align: 'right', cell: (r) => <span className="num">{r.entered}</span> },
    { key: 'answered', header: t('queuesTable.column.answered'), align: 'right', cell: (r) => <span className="num">{r.answered}</span> },
    { key: 'missed', header: t('queuesTable.column.missed'), align: 'right', cell: (r) => <span className="num">{r.abandoned + r.timeout}</span> },
    { key: 'avgWait', header: t('queuesTable.column.avgWait'), align: 'right', cell: (r) => <span className="num">{secOrDash(r.avg_wait_seconds)}</span> },
    { key: 'sla', header: t('queuesTable.column.sla'), align: 'right', cell: (r) => <span className="num">{pct(r.sla_percent)}</span> },
  ];
  const agentColumns: Column<ReportsAgentRow>[] = [
    { key: 'name', header: t('agentsTable.column.name'), cell: (r) => r.name },
    { key: 'calls', header: t('agentsTable.column.calls'), align: 'right', cell: (r) => <span className="num">{r.answered}</span> },
    { key: 'talkTime', header: t('agentsTable.column.talkTime'), align: 'right', cell: (r) => <span className="num">{formatDurationSec(r.talk_seconds)}</span> },
    { key: 'avgTalk', header: t('agentsTable.column.avgTalk'), align: 'right', cell: (r) => <span className="num">{secOrDash(r.avg_talk_seconds)}</span> },
  ];

  return (
    <AppShellPage title={t('title')}>
      <div className="flex flex-col gap-5">
        <div className="flex flex-wrap items-end gap-3 rounded-lg border border-line bg-surface p-3 shadow-card">
          <Field label={t('range.label')}>
            {(a) => (
              <Select
                {...a} value={preset} onValueChange={(v) => setPreset(v as RangePreset)}
                options={PRESETS.map((p) => ({ value: p, label: t(`range.${p}`) }))}
              />
            )}
          </Field>
          {preset === 'custom' && (
            <>
              <Field label={t('range.fromLabel')}>
                {(a) => <Input {...a} type="date" value={custom.from} max={custom.to} onChange={(e) => setCustom((c) => ({ ...c, from: e.target.value }))} />}
              </Field>
              <Field label={t('range.toLabel')}>
                {(a) => <Input {...a} type="date" value={custom.to} min={custom.from} onChange={(e) => setCustom((c) => ({ ...c, to: e.target.value }))} />}
              </Field>
            </>
          )}
          <Field label={t('queueFilter.label')}>
            {(a) => (
              <Select
                {...a} value={queueId} onValueChange={setQueueId}
                options={[{ value: '', label: t('queueFilter.all') }, ...(queues?.items ?? []).map((q) => ({ value: q.id, label: q.name }))]}
              />
            )}
          </Field>
        </div>

        {!validation.ok ? (
          <p role="alert" className="rounded-md border border-danger/30 bg-danger-soft px-3 py-2.5 text-sm text-on-danger-soft">{t('range.badRange')}</p>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
              <Kpi label={t('kpi.totalCalls')} value={summary ? String(summary.total) : null} loading={summaryLoading} />
              <Kpi label={t('kpi.answered')} value={summary ? String(summary.answered) : null} loading={summaryLoading} />
              <Kpi label={t('kpi.missed')} value={summary ? String(summary.missed) : null} loading={summaryLoading} />
              <Kpi label={t('kpi.avgWait')} value={summary ? secOrDash(summary.avg_wait_seconds) : null} loading={summaryLoading} />
              <Kpi label={t('kpi.avgTalk')} value={summary ? secOrDash(summary.avg_talk_seconds) : null} loading={summaryLoading} />
              <Kpi label={t('kpi.slaLevel')} value={summary ? pct(summary.sla_percent) : null} loading={summaryLoading} />
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <ChartCard
                ariaLabel={t('charts.dailyAriaLabel')}
                title={t('charts.dailyTitle')}
                legend={<ChartLegend items={[{ swatchClass: 'bg-chart-1', label: t('charts.legendIn') }, { swatchClass: 'bg-danger', label: t('charts.legendMissed') }]} />}
              >
                <BarChart
                  data={daily?.items ?? []}
                  emptyText={t('charts.empty')}
                  tickLabel={dailyTick}
                  series={[
                    { key: 'answered', swatchClass: 'fill-chart-1', value: (d) => d.answered },
                    { key: 'missed', swatchClass: 'fill-danger', value: (d) => d.missed },
                  ]}
                />
              </ChartCard>
              <ChartCard
                ariaLabel={t('charts.hourlyAriaLabel')}
                title={t('charts.hourlyTitle')}
                legend={
                  <ChartLegend
                    items={[
                      { swatchClass: 'bg-chart-1', label: t('charts.legendIn') },
                      { swatchClass: 'bg-chart-2', label: t('charts.legendOut') },
                      { swatchClass: 'bg-danger', label: t('charts.legendMissed') },
                    ]}
                  />
                }
              >
                <BarChart
                  data={hourly?.items ?? []}
                  emptyText={t('charts.empty')}
                  tickLabel={(h) => (h.hour % 6 === 0 ? String(h.hour).padStart(2, '0') : null)}
                  series={[
                    { key: 'inbound', swatchClass: 'fill-chart-1', value: (h) => h.inbound },
                    { key: 'answered', swatchClass: 'fill-chart-2', value: (h) => h.answered },
                    { key: 'missed', swatchClass: 'fill-danger', value: (h) => h.missed },
                  ]}
                />
              </ChartCard>
            </div>

            <div className="rounded-lg border border-line bg-surface p-4 shadow-card">
              <p className="mb-3 font-display text-base text-fg">{t('queuesTable.title')}</p>
              <DataTable
                caption={t('queuesTable.title')} rows={byQueue?.items ?? []} columns={queueColumns}
                rowId={(r) => r.queue_id} searchText={(r) => r.name} state="ready"
                empty={{ title: t('queuesTable.empty'), body: '' }}
              />
            </div>
            <div className="rounded-lg border border-line bg-surface p-4 shadow-card">
              <p className="mb-3 font-display text-base text-fg">{t('agentsTable.title')}</p>
              <DataTable
                caption={t('agentsTable.title')} rows={byAgent?.items ?? []} columns={agentColumns}
                rowId={(r) => r.extension} searchText={(r) => r.name} state="ready"
                empty={{ title: t('agentsTable.empty'), body: '' }}
              />
            </div>
          </>
        )}
      </div>
    </AppShellPage>
  );
}
