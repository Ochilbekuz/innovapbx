import { useId, useState } from 'react';
import { ArrowRight, Plus, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';
import { applyRoute, describePattern, parsePattern, type RouteRule } from '@/domain/pattern';
import { patternText } from './domainText';
import { Button } from '@/ui/Button';
import { controlBase } from '@/ui/Field';
import { newId } from '@/lib/browser';

export type PatternRow = RouteRule & { id: string; callerId: string };

/** Naqshni xato belgisi ostiga chiziq bilan ko'rsatadi (input ustidagi qatlam). */
function Highlight({ text, at }: { text: string; at: number | null }) {
  if (at === null) return null;
  return (
    <span aria-hidden className="num pointer-events-none absolute inset-0 flex items-center whitespace-pre px-2 text-transparent">
      {text.slice(0, at)}
      <span className="rounded-[1px] bg-danger/20 underline decoration-danger decoration-wavy decoration-1 underline-offset-4">{text[at] ?? ' '}</span>
    </span>
  );
}

function Cell({ label, value, onChange, placeholder, invalid, errorAt, describedBy, wide }: {
  label: string; value: string; onChange: (v: string) => void; placeholder: string;
  invalid?: boolean; errorAt?: number | null; describedBy?: string; wide?: boolean;
}) {
  return (
    <label className={cn('flex flex-col gap-1', wide ? 'min-w-[180px] flex-[2]' : 'min-w-[88px] flex-1')}>
      <span className="eyebrow">{label}</span>
      <span className="relative">
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          spellCheck={false}
          autoCapitalize="characters"
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy}
          className={cn(controlBase, 'num h-ctl-md px-2 text-base tracking-wide')}
        />
        <Highlight text={value} at={errorAt ?? null} />
      </span>
    </label>
  );
}

export function PatternEditor({ rows, onChange }: { rows: PatternRow[]; onChange: (r: PatternRow[]) => void }) {
  const { t } = useTranslation('common');
  const [probe, setProbe] = useState('998901234567');
  const base = useId();
  const update = (id: string, patch: Partial<PatternRow>) => onChange(rows.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  const firstMatch = rows.findIndex((r) => applyRoute(r, probe).matched);

  return (
    <div className="overflow-hidden rounded-lg border border-line bg-surface shadow-card">
      <ol className="divide-y divide-line">
        {rows.map((r, i) => {
          const parsed = parsePattern(r.pattern);
          const msgId = `${base}-${r.id}`;
          const hit = i === firstMatch;
          return (
            <li key={r.id} className={cn('relative flex flex-wrap items-end gap-2 px-3 py-3 transition-colors duration-fast', hit && 'bg-accent-soft/50')}>
              {hit && <span aria-hidden className="absolute inset-y-0 left-0 w-[3px] bg-brand" />}
              <span className="num mb-1.5 w-5 text-sm text-muted">{i + 1}</span>
              <Cell label={t('patternEditor.prependLabel')} value={r.prepend} onChange={(v) => update(r.id, { prepend: v })} placeholder="—" />
              <Cell label={t('patternEditor.prefixLabel')} value={r.prefix} onChange={(v) => update(r.id, { prefix: v })} placeholder="—" />
              <Cell
                wide
                label={t('patternEditor.patternLabel')}
                value={r.pattern}
                onChange={(v) => update(r.id, { pattern: v })}
                placeholder={t('patternEditor.patternPlaceholder')}
                invalid={!parsed.ok}
                errorAt={parsed.ok ? null : parsed.error.at}
                describedBy={msgId}
              />
              <Cell label={t('patternEditor.callerIdLabel')} value={r.callerId} onChange={(v) => update(r.id, { callerId: v })} placeholder={t('patternEditor.callerIdPlaceholder')} />
              <Button variant="ghost" size="md" iconOnly icon={<Trash2 />} aria-label={t('patternEditor.deleteRule', { n: i + 1 })} onClick={() => onChange(rows.filter((x) => x.id !== r.id))} />
              <p id={msgId} className={cn('basis-full pl-7 text-sm', parsed.ok ? 'text-muted' : 'text-danger')} aria-live="polite">
                {patternText(describePattern(parsed), t)}
              </p>
            </li>
          );
        })}
      </ol>
      <div className="flex flex-wrap items-center gap-3 border-t border-line bg-surface-2/60 px-3 py-2.5">
        <Button size="sm" variant="ghost" icon={<Plus />} onClick={() => onChange([...rows, { id: newId(), prepend: '', prefix: '', pattern: '', callerId: '' }])}>
          {t('patternEditor.addRule')}
        </Button>
        <div className="ml-auto flex items-center gap-2 text-sm">
          <label htmlFor={`${base}-probe`} className="whitespace-nowrap text-muted">{t('patternEditor.probeLabel')}</label>
          <input
            id={`${base}-probe`}
            value={probe}
            onChange={(e) => setProbe(e.target.value.replace(/\s/g, ''))}
            inputMode="tel"
            className={cn(controlBase, 'num h-ctl-sm w-40 px-2 text-sm')}
          />
          <ArrowRight aria-hidden className="size-4 text-muted" />
          <ProbeResult rows={rows} probe={probe} index={firstMatch} />
        </div>
      </div>
    </div>
  );
}

function ProbeResult({ rows, probe, index }: { rows: PatternRow[]; probe: string; index: number }) {
  const { t } = useTranslation('common');
  const row = rows[index];
  const res = row ? applyRoute(row, probe) : null;
  return (
    <output aria-live="polite" className="text-sm">
      {res?.matched ? (
        <span>
          <span className="text-muted">{t('patternEditor.probeMatch', { n: index + 1 })}</span>
          <span className="num font-medium text-fg">{res.dialed}</span>
        </span>
      ) : (
        <span className="font-medium text-danger">{t('patternEditor.probeNoMatch')}</span>
      )}
    </output>
  );
}
