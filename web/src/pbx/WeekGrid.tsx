import { useRef, useState, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';
import { paint, summarizeWeek, type Week } from '@/domain/week';
import { dayLabels } from './domainText';

const HOURS = Array.from({ length: 24 }, (_, h) => h);
const hh = (h: number) => `${String(h).padStart(2, '0')}:00`;

/**
 * Ish vaqti setkasi. Sichqoncha: bosib sudrash bilan bo'yash (birinchi katak holati teskarisiga).
 * Klaviatura: role=grid, strelkalar — katak, Space — almashtirish, Shift+strelka — bo'yab yurish.
 */
export function WeekGrid({ value, onChange, label }: { value: Week; onChange: (w: Week) => void; label?: string }) {
  const { t } = useTranslation('common');
  const resolvedLabel = label ?? t('weekGrid.defaultLabel');
  const [cursor, setCursor] = useState<[number, number]>([0, 9]);
  const painting = useRef<boolean | null>(null);
  const cells = useRef<Record<string, HTMLDivElement | null>>({});

  const set = (d: number, h: number, on: boolean) => onChange(paint(value, d, h, h + 1, on));
  const focus = (d: number, h: number) => {
    setCursor([d, h]);
    cells.current[`${d}-${h}`]?.focus();
  };

  const onKey = (e: KeyboardEvent, d: number, h: number) => {
    const moves: Record<string, [number, number]> = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] };
    const mv = moves[e.key];
    if (mv) {
      e.preventDefault();
      const nd = Math.min(6, Math.max(0, d + mv[0]));
      const nh = Math.min(23, Math.max(0, h + mv[1]));
      if (e.shiftKey) set(nd, nh, value[d]?.[h] ?? false);
      focus(nd, nh);
    } else if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      set(d, h, !value[d]?.[h]);
    }
  };

  const days = dayLabels(t, 'short');
  const dayNames = dayLabels(t, 'long');
  const summary = summarizeWeek(value, days);
  return (
    <div className="space-y-3" onPointerUp={() => (painting.current = null)} onPointerLeave={() => (painting.current = null)}>
      <div className="overflow-x-auto rounded-lg border border-line bg-surface p-3 shadow-card">
        <div role="grid" aria-label={resolvedLabel} aria-describedby="week-summary" className="inline-grid min-w-full grid-cols-[32px_repeat(24,minmax(18px,1fr))] gap-[2px]">
          <div role="row" className="contents">
            <span role="columnheader" aria-hidden />
            {HOURS.map((h) => (
              <span key={h} role="columnheader" aria-label={hh(h)} className="num pb-1 text-center text-[10px] leading-3 text-muted">
                {h % 3 === 0 ? String(h).padStart(2, '0') : ''}
              </span>
            ))}
          </div>
          {days.map((day, d) => (
            <div role="row" key={day} className="contents">
              <span role="rowheader" aria-label={dayNames[d]} className={cn('flex items-center text-xs font-medium', d >= 5 ? 'text-muted' : 'text-fg')}>{day}</span>
              {HOURS.map((h) => {
                const on = value[d]?.[h] ?? false;
                const isCursor = cursor[0] === d && cursor[1] === h;
                return (
                  <div
                    key={h}
                    ref={(el) => { cells.current[`${d}-${h}`] = el; }}
                    role="gridcell"
                    aria-selected={on}
                    aria-label={t('weekGrid.cellAriaLabel', { day: dayNames[d], from: hh(h), to: hh(h + 1), state: on ? t('weekGrid.open') : t('weekGrid.closed') })}
                    tabIndex={isCursor ? 0 : -1}
                    onKeyDown={(e) => onKey(e, d, h)}
                    onFocus={() => setCursor([d, h])}
                    onPointerDown={(e) => { e.preventDefault(); painting.current = !on; set(d, h, !on); setCursor([d, h]); }}
                    onPointerEnter={() => painting.current !== null && set(d, h, painting.current)}
                    className={cn(
                      'h-6 cursor-pointer rounded-[2px] transition-colors duration-fast',
                      on ? 'bg-brand hover:bg-brand-fire' : 'bg-surface-2 hover:bg-line-strong',
                      h % 6 === 0 && h > 0 && 'ml-[2px]',
                      'focus-visible:outline-offset-1',
                    )}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        <span className="inline-flex items-center gap-1.5 text-muted"><span aria-hidden className="size-3 rounded-[2px] bg-brand" />{t('weekGrid.legendOpen')}</span>
        <span className="inline-flex items-center gap-1.5 text-muted"><span aria-hidden className="size-3 rounded-[2px] border border-line-strong bg-surface-2" />{t('weekGrid.legendClosed')}</span>
        <span id="week-summary" className="num text-fg">{summary.length ? summary.join(' · ') : t('weekGrid.allClosed')}</span>
      </div>
    </div>
  );
}
