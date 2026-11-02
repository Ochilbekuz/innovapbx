import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

export type ChartSeries<T> = {
  key: string;
  /** Tailwind to'ldirish rangi, masalan "fill-chart-1" yoki "fill-danger". */
  swatchClass: string;
  value: (d: T) => number;
};

type BarChartProps<T> = {
  data: T[];
  series: ChartSeries<T>[];
  /** Har bir ustun guruhi tagidagi yorliq; `null` qaytarilsa o'sha guruhga yorliq chizilmaydi. */
  tickLabel: (d: T, index: number) => string | null;
  height?: number;
  emptyText?: string;
};

/**
 * Guruhlangan ustunli SVG diagramma — DashboardPage'dagi `HourlyChart`dan ajratilgan umumiy
 * komponent (M2b §5: Analitika sahifasi ham shuni ishlatadi, soatlik va kunlik grafiklar uchun).
 */
export function BarChart<T>({ data, series, tickLabel, height = 140, emptyText }: BarChartProps<T>) {
  const w = 480;
  const h = height;
  const padBottom = 18;
  const chartH = h - padBottom;
  const max = Math.max(1, ...data.flatMap((d) => series.map((s) => s.value(d))));
  const groupW = w / Math.max(1, data.length);
  const barW = Math.max(1.2, groupW / series.length - 1);
  const isEmpty = data.every((d) => series.every((s) => s.value(d) === 0));

  const bar = (x: number, v: number) => {
    const bh = (v / max) * (chartH - 4);
    return { x, y: chartH - bh, barHeight: Math.max(bh, v > 0 ? 1 : 0) };
  };

  if (isEmpty && emptyText) return <p className="py-10 text-center text-sm text-muted">{emptyText}</p>;

  return (
    <svg aria-hidden viewBox={`0 0 ${w} ${h}`} style={{ height: `${h}px` }} className="w-full overflow-visible" preserveAspectRatio="none">
      <line x1={0} y1={chartH} x2={w} y2={chartH} className="stroke-line" strokeWidth={1} />
      {data.map((d, i) => {
        const gx = i * groupW;
        const label = tickLabel(d, i);
        return (
          <g key={i}>
            {series.map((s, si) => {
              const b = bar(gx + (barW + 1) * si, s.value(d));
              return <rect key={s.key} x={b.x} y={b.y} width={barW} height={b.barHeight} className={s.swatchClass} rx={0.5} />;
            })}
            {label !== null && (
              <text x={gx + groupW / 2} y={h - 4} textAnchor="middle" className="fill-muted text-[8px]">{label}</text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

/** Diagramma ustidagi rang-yorliq qatori (masalan "kiruvchi / chiquvchi / o'tkazib yuborilgan"). */
export function ChartLegend({ items }: { items: { swatchClass: string; label: string }[] }) {
  return (
    <div className="flex items-center gap-3 text-xs text-muted">
      {items.map((it) => (
        <span key={it.label} className="flex items-center gap-1.5">
          <span aria-hidden className={cn('size-2 rounded-sm', it.swatchClass)} />
          {it.label}
        </span>
      ))}
    </div>
  );
}

/** Diagrammani o'rab turuvchi karta — sarlavha + legend header, bolalar esa grafik tanasi. */
export function ChartCard({
  ariaLabel, title, legend, children,
}: { ariaLabel: string; title: ReactNode; legend?: ReactNode; children: ReactNode }) {
  return (
    <section aria-label={ariaLabel} className="overflow-hidden rounded-lg border border-line bg-surface p-4 shadow-card">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-display text-base font-semibold">{title}</h3>
        {legend}
      </div>
      {children}
    </section>
  );
}
