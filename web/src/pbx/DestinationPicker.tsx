import { useId, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import * as Popover from '@radix-ui/react-popover';
import { Check, ChevronDown, CircleAlert, Link2Off, Search } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';
import {
  formatNumber, normalizeNumber, resolveDestination,
  type Catalog, type DestKind, type Destination, type Resolved, type Target,
} from '@/domain/destination';
import { Button } from '@/ui/Button';
import { controlBase } from '@/ui/Field';
import { KIND_ICON, KIND_ORDER, useKindLabel } from './kinds';

type Props = {
  value: Destination | null;
  onChange: (d: Destination) => void;
  catalog: Catalog;
  label: string;
  /** Qaysi turlar ruxsat etilgan (masalan IVR ichida «IVR» ham bo'lishi mumkin). */
  kinds?: DestKind[];
  required?: boolean;
  disabled?: boolean;
  hint?: ReactNode;
};

type Tab = DestKind | 'all';

function Face({ r }: { r: Resolved }) {
  const { t } = useTranslation('common');
  const kindLabel = useKindLabel();
  if (r.state === 'empty') return <span className="text-muted">{t('destinationPicker.selectPlaceholder')}</span>;
  if (r.state === 'broken')
    return (
      <span className="flex min-w-0 items-center gap-2 text-danger">
        <Link2Off aria-hidden className="size-4 shrink-0" />
        <span className="truncate font-medium">{t('destinationPicker.deletedPrefix', { kind: kindLabel[r.kind].toLowerCase() })}</span>
        <span className="num truncate text-xs text-on-danger-soft">#{r.targetId}</span>
      </span>
    );
  if (r.state === 'invalid')
    return (
      <span className="flex min-w-0 items-center gap-2 text-danger">
        <CircleAlert aria-hidden className="size-4 shrink-0" />
        <span className="num truncate">{r.number}</span>
      </span>
    );
  return (
    <span className="flex min-w-0 items-center gap-2">
      <span aria-hidden className="grid size-5 shrink-0 place-items-center rounded-sm bg-accent-soft text-on-accent-soft [&_svg]:size-3.5">{KIND_ICON[r.kind]}</span>
      <span className="shrink-0 text-xs text-muted">{kindLabel[r.kind]}</span>
      <span className="truncate font-medium text-fg">{r.kind === 'external' ? <span className="num">{formatNumber(r.number ?? '')}</span> : r.label}</span>
      {r.kind !== 'external' && r.number && <span className="num shrink-0 text-sm text-muted">{r.number}</span>}
    </span>
  );
}

type TFunc = (key: string, opts?: Record<string, unknown>) => string;

function faceText(r: Resolved, t: TFunc, kindLabel: Record<DestKind, string>): string {
  if (r.state === 'empty') return t('destinationPicker.faceUnselected');
  if (r.state === 'broken') return t('destinationPicker.faceDeleted', { kind: kindLabel[r.kind], id: r.targetId });
  if (r.state === 'invalid') return t('destinationPicker.faceInvalid', { number: r.number });
  return t('destinationPicker.facePicked', { kind: kindLabel[r.kind], label: r.label }) + (r.number && r.kind !== 'external' ? ` ${r.number}` : '');
}

export function DestinationPicker({ value, onChange, catalog, label, kinds = KIND_ORDER, required, disabled, hint }: Props) {
  const { t } = useTranslation('common');
  const kindLabel = useKindLabel();
  const resolved = resolveDestination(value, catalog);
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>(value ? value.kind : 'all');
  const id = useId();
  const problem = resolved.state === 'broken' || resolved.state === 'invalid' || (required && resolved.state === 'empty');
  const msgId = `${id}-msg`;

  const pick = (d: Destination) => {
    onChange(d);
    setOpen(false);
  };

  return (
    <div className="flex flex-col gap-1.5">
      <span id={`${id}-l`} className="text-sm font-medium text-fg">
        {label}
        {required && <span aria-hidden className="ml-0.5 text-danger">*</span>}
      </span>
      <Popover.Root open={open} onOpenChange={setOpen}>
        <Popover.Trigger asChild disabled={disabled}>
          <button
            type="button"
            aria-labelledby={`${id}-l ${id}-v`}
            aria-describedby={problem || hint ? msgId : undefined}
            aria-invalid={problem || undefined}
            aria-haspopup="dialog"
            className={cn(
              controlBase,
              'flex h-ctl-lg items-center justify-between gap-2 px-2.5 text-left text-base',
              resolved.state === 'empty' && 'border-dashed',
              (resolved.state === 'broken' || resolved.state === 'invalid') && 'border-danger bg-danger-soft/40',
            )}
          >
            <span id={`${id}-v`} className="sr-only">{faceText(resolved, t, kindLabel)}</span>
            <span aria-hidden className="flex min-w-0 flex-1"><Face r={resolved} /></span>
            <ChevronDown aria-hidden className="size-4 shrink-0 text-muted" />
          </button>
        </Popover.Trigger>
        <Popover.Portal>
          <Popover.Content
            align="start"
            sideOffset={6}
            aria-label={t('destinationPicker.popoverAriaLabel', { label })}
            className="z-popover flex w-[min(560px,calc(100vw-2rem))] overflow-hidden rounded-lg border border-line bg-raised shadow-pop data-[state=open]:animate-pop-in"
          >
            <KindRail kinds={kinds} tab={tab} onTab={setTab} catalog={catalog} />
            <div className="flex min-h-[300px] min-w-0 flex-1 flex-col">
              <Panel tab={tab} kinds={kinds} catalog={catalog} value={value} onPick={pick} />
            </div>
          </Popover.Content>
        </Popover.Portal>
      </Popover.Root>
      {resolved.state === 'broken' ? (
        <p id={msgId} className="flex items-start gap-1.5 text-sm text-danger">
          <CircleAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />
          {t('destinationPicker.brokenHint', { kind: kindLabel[resolved.kind].toLowerCase() })}
        </p>
      ) : resolved.state === 'invalid' ? (
        <p id={msgId} className="text-sm text-danger">{t('destinationPicker.invalidHint')}</p>
      ) : required && resolved.state === 'empty' ? (
        <p id={msgId} className="text-sm text-danger">{t('destinationPicker.requiredHint')}</p>
      ) : hint ? (
        <p id={msgId} className="text-sm text-muted">{hint}</p>
      ) : null}
    </div>
  );
}

function KindRail({ kinds, tab, onTab, catalog }: { kinds: DestKind[]; tab: Tab; onTab: (t: Tab) => void; catalog: Catalog }) {
  const { t } = useTranslation('common');
  const kindLabel = useKindLabel();
  const counts = useMemo(() => {
    const c: Partial<Record<DestKind, number>> = {};
    Object.values(catalog).forEach((t) => { c[t.kind] = (c[t.kind] ?? 0) + 1; });
    return c;
  }, [catalog]);
  const tabs: Tab[] = ['all', ...kinds];
  const onKey = (e: KeyboardEvent) => {
    const i = tabs.indexOf(tab);
    const d = e.key === 'ArrowDown' ? 1 : e.key === 'ArrowUp' ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    const next = tabs[(i + d + tabs.length) % tabs.length];
    if (next) onTab(next);
  };
  return (
    <div role="radiogroup" aria-label={t('destinationPicker.kindRailAriaLabel')} onKeyDown={onKey} className="w-44 shrink-0 border-r border-line bg-surface-2/60 p-1.5">
      {tabs.map((tb) => {
        const on = tb === tab;
        const n = tb === 'all' ? undefined : counts[tb];
        return (
          <button
            key={tb}
            type="button"
            role="radio"
            aria-checked={on}
            tabIndex={on ? 0 : -1}
            onClick={() => onTab(tb)}
            className={cn(
              'flex h-8 w-full items-center gap-2 rounded-sm px-2 text-left text-sm transition-colors duration-fast [&_svg]:size-3.5',
              on ? 'bg-surface font-medium text-fg shadow-card' : 'text-muted hover:bg-surface/70 hover:text-fg',
            )}
          >
            <span aria-hidden className={on ? 'text-brand' : ''}>{tb === 'all' ? <Search /> : KIND_ICON[tb]}</span>
            <span className="flex-1 truncate">{tb === 'all' ? t('destinationPicker.all') : kindLabel[tb]}</span>
            {n !== undefined && <span className="num text-xs text-muted">{n}</span>}
          </button>
        );
      })}
    </div>
  );
}

function Panel({ tab, kinds, catalog, value, onPick }: { tab: Tab; kinds: DestKind[]; catalog: Catalog; value: Destination | null; onPick: (d: Destination) => void }) {
  if (tab === 'external') return <ExternalPanel value={value} onPick={onPick} />;
  return <TargetList tab={tab} kinds={kinds} catalog={catalog} value={value} onPick={onPick} />;
}

function TargetList({ tab, kinds, catalog, value, onPick }: { tab: Tab; kinds: DestKind[]; catalog: Catalog; value: Destination | null; onPick: (d: Destination) => void }) {
  const { t } = useTranslation('common');
  const kindLabel = useKindLabel();
  const [q, setQ] = useState('');
  const [active, setActive] = useState(0);
  const listId = useId();
  const needle = q.trim().toLowerCase();
  const items = useMemo(
    () =>
      Object.values(catalog)
        .filter((t) => (tab === 'all' ? kinds.includes(t.kind) : t.kind === tab))
        .filter((t) => !needle || `${t.name} ${t.number ?? ''}`.toLowerCase().includes(needle))
        .sort((a, b) => KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind) || (a.number ?? '').localeCompare(b.number ?? '', 'uz', { numeric: true })),
    [catalog, tab, kinds, needle],
  );
  const selectedId = value && 'targetId' in value ? value.targetId : null;
  const choose = (t: Target) => onPick({ kind: t.kind, targetId: t.id });
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => Math.min(i + 1, items.length - 1)); }
    if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
    if (e.key === 'Enter') { e.preventDefault(); const t = items[active]; if (t) choose(t); }
  };
  let lastKind: DestKind | null = null;
  return (
    <>
      <div className="relative border-b border-line">
        <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
        <input
          autoFocus
          role="combobox"
          aria-expanded
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={items[active] ? `${listId}-${items[active].id}` : undefined}
          aria-label={t('destinationPicker.searchAriaLabel')}
          placeholder={t('destinationPicker.searchPlaceholder')}
          value={q}
          onChange={(e) => { setQ(e.target.value); setActive(0); }}
          onKeyDown={onKey}
          className="h-10 w-full bg-transparent pl-9 pr-3 text-base text-fg placeholder:text-muted focus-visible:outline-none"
        />
      </div>
      <ul id={listId} role="listbox" aria-label={t('destinationPicker.listAriaLabel')} className="max-h-[300px] flex-1 overflow-y-auto p-1.5">
        {items.length === 0 && (
          <li className="px-3 py-8 text-center text-sm text-muted">
            {needle ? t('destinationPicker.notFound', { q }) : t('destinationPicker.emptyKind')}
          </li>
        )}
        {items.map((t, i) => {
          const head = tab === 'all' && t.kind !== lastKind;
          lastKind = t.kind;
          const sel = t.id === selectedId;
          return (
            <li key={t.id} role="presentation">
              {head && <p aria-hidden className="eyebrow px-2 pb-1 pt-2.5 first:pt-1">{kindLabel[t.kind]}</p>}
              <div
                id={`${listId}-${t.id}`}
                role="option"
                aria-selected={sel}
                onMouseEnter={() => setActive(i)}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => choose(t)}
                className={cn(
                  'flex h-9 cursor-pointer items-center gap-2.5 rounded-sm px-2 text-base',
                  i === active ? 'bg-surface-2' : '',
                )}
              >
                <span aria-hidden className="text-muted [&_svg]:size-4">{KIND_ICON[t.kind]}</span>
                <span className="flex-1 truncate text-fg">{t.name}</span>
                {t.number && <span className="num text-sm text-muted">{t.number}</span>}
                <Check aria-hidden className={cn('size-4 text-accent', sel ? 'opacity-100' : 'opacity-0')} />
              </div>
            </li>
          );
        })}
      </ul>
      <p className="border-t border-line px-3 py-1.5 text-xs text-muted">{t('destinationPicker.keyboardHint')}</p>
    </>
  );
}

function ExternalPanel({ value, onPick }: { value: Destination | null; onPick: (d: Destination) => void }) {
  const { t } = useTranslation('common');
  const [num, setNum] = useState(value?.kind === 'external' ? value.number : '');
  const ref = useRef<HTMLInputElement>(null);
  const ok = /^\+?\d{3,15}$/.test(normalizeNumber(num));
  const submit = () => (ok ? onPick({ kind: 'external', number: normalizeNumber(num) }) : ref.current?.focus());
  return (
    <div className="flex flex-1 flex-col gap-3 p-4">
      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium">{t('destinationPicker.externalLabel')}</span>
        <input
          ref={ref}
          autoFocus
          inputMode="tel"
          value={num}
          aria-invalid={num !== '' && !ok ? true : undefined}
          onChange={(e) => setNum(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), submit())}
          placeholder={t('destinationPicker.externalPlaceholder')}
          className={cn(controlBase, 'num h-ctl-lg px-3 text-md')}
        />
      </label>
      <p className="text-sm text-muted">{t('destinationPicker.externalHint')}</p>
      <div><Button variant="primary" size="sm" onClick={submit} disabled={!ok}>{t('destinationPicker.pickNumber')}</Button></div>
    </div>
  );
}
