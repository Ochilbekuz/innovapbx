import { useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { GripVertical } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';
import { moveItem } from '@/domain/reorder';

type Props<T> = {
  items: T[];
  onChange: (items: T[]) => void;
  itemId: (t: T) => string;
  itemLabel: (t: T) => string;
  render: (t: T, index: number) => ReactNode;
  label: string;
};

/**
 * Tartib ro'yxati (trunk failover, navbat a'zolari).
 * Sichqoncha: tutqichdan sudrash. Klaviatura: tutqichda Space — ko'tarish, ↑↓ — ko'chirish, Space — qo'yish, Esc — bekor.
 * Har harakat aria-live orqali e'lon qilinadi.
 */
export function SortableList<T>({ items, onChange, itemId, itemLabel, render, label }: Props<T>) {
  const { t } = useTranslation('common');
  const [lifted, setLifted] = useState<number | null>(null);
  const [dragIdx, setDragIdx] = useState<number | null>(null);
  const [overIdx, setOverIdx] = useState<number | null>(null);
  const [say, setSay] = useState('');
  const before = useRef<T[] | null>(null);
  const handles = useRef<(HTMLButtonElement | null)[]>([]);

  const focusAt = (i: number) => requestAnimationFrame(() => handles.current[i]?.focus());
  const pos = (i: number) => t('sortableList.position', { n: i + 1, total: items.length });

  const onKey = (e: KeyboardEvent, i: number) => {
    const item = items[i];
    if (!item) return;
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      if (lifted === null) {
        before.current = items;
        setLifted(i);
        setSay(t('sortableList.lifted', { item: itemLabel(item), pos: pos(i) }));
      } else {
        setLifted(null);
        setSay(t('sortableList.dropped', { item: itemLabel(item), pos: pos(i) }));
      }
      return;
    }
    if (e.key === 'Escape' && lifted !== null && before.current) {
      e.preventDefault();
      onChange(before.current);
      const back = before.current.findIndex((x) => itemId(x) === itemId(item));
      setLifted(null);
      setSay(t('sortableList.cancelled'));
      focusAt(back);
      return;
    }
    const d = e.key === 'ArrowUp' ? -1 : e.key === 'ArrowDown' ? 1 : 0;
    if (lifted === null || !d) return;
    e.preventDefault();
    const to = i + d;
    if (to < 0 || to >= items.length) return;
    onChange(moveItem(items, i, to));
    setLifted(to);
    setSay(t('sortableList.moved', { item: itemLabel(item), pos: pos(to) }));
    focusAt(to);
  };

  return (
    <div>
      <ol aria-label={label} className="overflow-hidden rounded-lg border border-line bg-surface shadow-card">
        {items.map((it, i) => {
          const isLifted = lifted === i || dragIdx === i;
          return (
            <li
              key={itemId(it)}
              onDragOver={(e) => { if (dragIdx !== null) { e.preventDefault(); setOverIdx(i); } }}
              onDrop={(e) => {
                e.preventDefault();
                if (dragIdx !== null && dragIdx !== i) onChange(moveItem(items, dragIdx, i));
                setDragIdx(null);
                setOverIdx(null);
              }}
              className={cn(
                'relative flex h-12 items-center gap-3 border-b border-line bg-surface pl-1.5 pr-3 transition-[background-color,box-shadow] duration-fast last:border-b-0',
                isLifted && 'z-10 bg-raised shadow-pop ring-1 ring-brand',
                overIdx === i && dragIdx !== null && dragIdx !== i && 'shadow-[inset_0_2px_0_rgb(var(--c-brand))]',
              )}
            >
              <button
                ref={(el) => { handles.current[i] = el; }}
                type="button"
                draggable
                onDragStart={(e) => { setDragIdx(i); e.dataTransfer.effectAllowed = 'move'; }}
                onDragEnd={() => { setDragIdx(null); setOverIdx(null); }}
                onKeyDown={(e) => onKey(e, i)}
                onBlur={() => lifted === i && setLifted(null)}
                aria-roledescription={t('sortableList.handleRoleDescription')}
                aria-pressed={lifted === i}
                aria-label={t('sortableList.handleAriaLabel', { item: itemLabel(it), pos: pos(i) })}
                className={cn('grid h-8 w-6 cursor-grab place-items-center rounded-sm text-muted hover:bg-surface-2 hover:text-fg active:cursor-grabbing', lifted === i && 'bg-accent-soft text-on-accent-soft')}
              >
                <GripVertical aria-hidden className="size-4" />
              </button>
              <span className="num w-5 text-center text-sm text-muted">{i + 1}</span>
              <div className="flex min-w-0 flex-1 items-center gap-3">{render(it, i)}</div>
            </li>
          );
        })}
      </ol>
      <p aria-live="assertive" className="sr-only">{say}</p>
    </div>
  );
}
