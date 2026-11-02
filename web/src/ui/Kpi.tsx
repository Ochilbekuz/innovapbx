import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';

type KpiProps = {
  label: string;
  value: string | null;
  unit?: string;
  /** Oldingi davrga nisbatan, foizda. Yaxshi/yomon deb bo'yalmaydi — yo'nalish strelka va ishora bilan. */
  delta?: number;
  deltaLabel?: string;
  series?: number[];
  loading?: boolean;
  emptyText?: string;
  className?: string;
};

function Sparkline({ series }: { series: number[] }) {
  const w = 120;
  const h = 32;
  const max = Math.max(...series);
  const min = Math.min(...series);
  const span = max - min || 1;
  const pts = series.map((v, i) => [(i / (series.length - 1)) * w, h - 2 - ((v - min) / span) * (h - 4)] as const);
  const line = pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  const last = pts[pts.length - 1];
  return (
    <svg aria-hidden viewBox={`0 0 ${w} ${h}`} className="-mt-1 h-7 w-[88px] shrink-0 overflow-visible" preserveAspectRatio="none">
      <path d={`${line} L${w},${h} L0,${h} Z`} className="fill-brand/10" />
      <path d={line} className="fill-none stroke-chart-1" strokeWidth={1.5} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
      {last && <circle cx={last[0]} cy={last[1]} r={2.5} className="fill-chart-1" />}
    </svg>
  );
}

export function Kpi({ label, value, unit, delta, deltaLabel, series, loading, emptyText, className }: KpiProps) {
  const { t } = useTranslation('common');
  const Arrow = delta === undefined || delta === 0 ? Minus : delta > 0 ? ArrowUpRight : ArrowDownRight;
  const resolvedDeltaLabel = deltaLabel ?? t('kpi.deltaLabel');
  const resolvedEmptyText = emptyText ?? t('kpi.emptyText');
  return (
    <div className={cn('flex min-h-[112px] flex-col gap-3 rounded-lg border border-line bg-surface p-4 shadow-card', className)} aria-busy={loading || undefined}>
      <div className="flex items-start justify-between gap-3">
        <p className="eyebrow">{label}</p>
        {!loading && value !== null && series && series.length > 1 && <Sparkline series={series} />}
      </div>
      {loading ? (
        <div className="space-y-2" aria-label={t('kpi.loadingAriaLabel')}>
          <div className="skeleton h-8 w-24" />
          <div className="skeleton h-3 w-32" />
        </div>
      ) : value === null ? (
        <div>
          <p className="num text-2xl text-disabled">—</p>
          <p className="text-sm text-muted">{resolvedEmptyText}</p>
        </div>
      ) : (
        <div>
          <div>
            <p className="num text-2xl text-fg">
              {value}
              {unit && <span className="ml-1 text-md text-muted">{unit}</span>}
            </p>
            {delta !== undefined && (
              <p className="mt-1 flex items-center gap-1 whitespace-nowrap text-sm text-muted">
                <Arrow aria-hidden className="size-3.5 text-fg" />
                <span className="num text-fg">{delta > 0 ? '+' : ''}{delta}%</span>
                {resolvedDeltaLabel}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
