import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { ArrowDownToLine, Pause, Play, Search } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';
import { Input } from '@/ui/Field';
import { LiveDot } from '@/ui/Status';

export type LogLevel = 'ERROR' | 'WARNING' | 'NOTICE' | 'VERBOSE' | 'DEBUG';
export type LogLine = { id: number; ts: string; level: LogLevel; source: string; text: string };

const LEVELS: LogLevel[] = ['ERROR', 'WARNING', 'NOTICE', 'VERBOSE', 'DEBUG'];
const LEVEL_CLS: Record<LogLevel, string> = {
  ERROR: 'text-danger',
  WARNING: 'text-warning',
  NOTICE: 'text-info',
  VERBOSE: 'text-fg',
  DEBUG: 'text-muted',
};

function mark(text: string, q: string): ReactNode {
  if (!q) return text;
  const i = text.toLowerCase().indexOf(q.toLowerCase());
  if (i < 0) return text;
  return (
    <>
      {text.slice(0, i)}
      <mark className="rounded-[2px] bg-live px-px text-on-live">{text.slice(i, i + q.length)}</mark>
      {text.slice(i + q.length)}
    </>
  );
}

/** Asterisk CLI logi — faqat o'qish. Jonli rejimda pastga yopishadi; foydalanuvchi yuqoriga aylantirsa — to'xtaydi. */
export function LogViewer({ lines, live, onLiveChange }: { lines: LogLine[]; live: boolean; onLiveChange: (v: boolean) => void }) {
  const { t } = useTranslation('common');
  const [q, setQ] = useState('');
  const [levels, setLevels] = useState<ReadonlySet<LogLevel>>(new Set(['ERROR', 'WARNING', 'NOTICE', 'VERBOSE']));
  const box = useRef<HTMLDivElement>(null);
  const shown = useMemo(
    () => lines.filter((l) => levels.has(l.level) && (!q || `${l.source} ${l.text}`.toLowerCase().includes(q.toLowerCase()))),
    [lines, levels, q],
  );

  useEffect(() => {
    const el = box.current;
    if (live && el) el.scrollTop = el.scrollHeight;
  }, [shown, live]);

  const toggleLevel = (l: LogLevel) =>
    setLevels((s) => { const n = new Set(s); if (n.has(l)) n.delete(l); else n.add(l); return n; });

  return (
    <div className="overflow-hidden rounded-lg border border-line bg-surface shadow-card">
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2">
        <div className="w-56"><Input size="sm" type="search" aria-label={t('logViewer.searchAriaLabel')} placeholder={t('logViewer.searchPlaceholder')} leading={<Search />} value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <div role="group" aria-label={t('logViewer.levelFilterAriaLabel')} className="flex flex-wrap gap-1">
          {LEVELS.map((l) => {
            const on = levels.has(l);
            return (
              <button
                key={l}
                type="button"
                aria-pressed={on}
                onClick={() => toggleLevel(l)}
                className={cn('num h-6 rounded-sm border px-1.5 text-xs transition-colors duration-fast', on ? 'border-line-strong bg-surface-2 text-fg' : 'border-dashed border-line text-muted line-through decoration-1')}
              >
                {l}
              </button>
            );
          })}
        </div>
        <div className="ml-auto flex items-center gap-2">
          {live && <span className="inline-flex items-center gap-1.5 text-xs font-medium text-fg"><LiveDot />{t('logViewer.live')}</span>}
          <button
            type="button"
            onClick={() => onLiveChange(!live)}
            aria-pressed={live}
            className="inline-flex h-ctl-sm items-center gap-1.5 rounded-md border border-line-strong bg-surface px-2 text-sm text-fg hover:bg-surface-2 [&_svg]:size-3.5"
          >
            {live ? <Pause aria-hidden /> : <Play aria-hidden />}
            {live ? t('logViewer.stop') : t('logViewer.watch')}
          </button>
        </div>
      </div>
      <div
        ref={box}
        role="log"
        aria-live={live ? 'polite' : 'off'}
        aria-label={t('logViewer.logAriaLabel')}
        tabIndex={0}
        onScroll={(e) => {
          const el = e.currentTarget;
          if (live && el.scrollHeight - el.scrollTop - el.clientHeight > 40) onLiveChange(false);
        }}
        className="num h-64 overflow-y-auto bg-surface-2/50 py-1.5 text-xs leading-5"
      >
        {shown.length === 0 && <p className="px-3 py-6 font-sans text-sm text-muted">{t('logViewer.noMatch')}</p>}
        {shown.map((l) => (
          <div key={l.id} className={cn('grid grid-cols-[92px_68px_minmax(0,140px)_1fr] gap-x-3 px-3 hover:bg-surface-2', l.level === 'ERROR' && 'bg-danger-soft/50')}>
            <span className="text-muted">{l.ts}</span>
            <span className={cn('font-medium', LEVEL_CLS[l.level])}>{l.level}</span>
            <span className="truncate text-on-accent-soft">{mark(l.source, q)}</span>
            <span className="whitespace-pre-wrap break-all text-fg">{mark(l.text, q)}</span>
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between border-t border-line px-3 py-1.5 text-xs text-muted">
        <span className="num">{t('logViewer.lineCount', { shown: shown.length, total: lines.length })}</span>
        {!live && (
          <button type="button" onClick={() => onLiveChange(true)} className="inline-flex items-center gap-1 font-medium text-accent hover:underline">
            <ArrowDownToLine aria-hidden className="size-3.5" /> {t('logViewer.jumpToEnd')}
          </button>
        )}
      </div>
    </div>
  );
}
