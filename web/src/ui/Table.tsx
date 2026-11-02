import { useMemo, useState, type ReactNode } from 'react';
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, ChevronsUpDown, CloudOff, Inbox, Search } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';
import { queryRows, type Sort } from '@/domain/table';
import { Button } from './Button';
import { Checkbox } from './Toggle';
import { Input } from './Field';

export type Column<T> = {
  key: string;
  header: string;
  cell: (row: T) => ReactNode;
  /** Saralash qiymati; berilmasa ustun saralanmaydi. */
  sortValue?: (row: T) => string | number;
  align?: 'left' | 'right';
  width?: string;
};

export type TableState = 'ready' | 'loading' | 'error';

/** `useQuery`'ning `isLoading`/`isError`'ini `DataTable`'ning `state` propiga aylantiradi. */
export function queryState(isLoading: boolean, isError: boolean): TableState {
  if (isLoading) return 'loading';
  if (isError) return 'error';
  return 'ready';
}

type Props<T> = {
  caption: string;
  rows: readonly T[];
  columns: Column<T>[];
  rowId: (row: T) => string;
  searchText: (row: T) => string;
  /** Qidiruv maydoni matni — sukut `table.searchPlaceholder` (raqam/nom). */
  searchPlaceholder?: string;
  state?: TableState;
  pageSize?: number;
  onRetry?: () => void;
  empty?: { title: string; body: string; action?: ReactNode };
  bulkActions?: (selected: string[]) => ReactNode;
  toolbar?: ReactNode;
  onRowOpen?: (row: T) => void;
};

function SortIcon({ dir }: { dir: 'asc' | 'desc' | null }) {
  const I = dir === 'asc' ? ArrowUp : dir === 'desc' ? ArrowDown : ChevronsUpDown;
  return <I aria-hidden className={cn('size-3.5', dir ? 'text-brand' : 'text-muted/70')} />;
}

const nextSort = (cur: Sort, key: string): Sort =>
  cur?.key !== key ? { key, dir: 'asc' } : cur.dir === 'asc' ? { key, dir: 'desc' } : null;

export function DataTable<T>({
  caption, rows, columns, rowId, searchText, searchPlaceholder, state = 'ready', pageSize = 8, onRetry, empty, bulkActions, toolbar, onRowOpen,
}: Props<T>) {
  const { t } = useTranslation('common');
  const [filter, setFilter] = useState('');
  const [sort, setSort] = useState<Sort>(null);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());

  const sorters = useMemo(() => Object.fromEntries(columns.map((c) => [c.key, c.sortValue])), [columns]);
  const view = queryRows(rows, {
    filter, sort, page, pageSize, text: searchText,
    value: (r, k) => sorters[k]?.(r) ?? '',
  });
  const pageIds = view.rows.map(rowId);
  const onPage = pageIds.filter((id) => selected.has(id)).length;
  const headState = onPage === 0 ? false : onPage === pageIds.length ? true : 'indeterminate';

  const toggle = (id: string, on: boolean) =>
    setSelected((s) => { const n = new Set(s); if (on) n.add(id); else n.delete(id); return n; });
  const togglePage = (on: boolean) =>
    setSelected((s) => { const n = new Set(s); pageIds.forEach((id) => (on ? n.add(id) : n.delete(id))); return n; });

  const colSpan = columns.length + (bulkActions ? 1 : 0);
  const showRows = state === 'ready' && view.total > 0;

  return (
    <div className="overflow-hidden rounded-lg border border-line bg-surface shadow-card">
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2">
        {selected.size > 0 && bulkActions ? (
          <div className="flex flex-1 items-center gap-2" role="region" aria-label={t('table.bulkRegion')}>
            <span className="num rounded-sm bg-accent-soft px-2 py-0.5 text-sm text-on-accent-soft">{t('table.selectedCount', { n: selected.size })}</span>
            {bulkActions([...selected])}
            <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>{t('table.cancel')}</Button>
          </div>
        ) : (
          <>
            <div className="w-full max-w-72">
              <Input
                size="sm"
                type="search"
                aria-label={t('table.searchAriaLabel', { caption })}
                placeholder={searchPlaceholder ?? t('table.searchPlaceholder')}
                leading={<Search />}
                value={filter}
                onChange={(e) => { setFilter(e.target.value); setPage(1); }}
              />
            </div>
            <div className="ml-auto flex items-center gap-2">{toolbar}</div>
          </>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm" aria-busy={state === 'loading' || undefined}>
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr className="border-b border-line bg-surface-2/70">
              {bulkActions && (
                <th scope="col" className="w-10 px-3 py-2">
                  <Checkbox checked={headState} onCheckedChange={togglePage} aria-label={t('table.selectAllAriaLabel')} disabled={!showRows} />
                </th>
              )}
              {columns.map((c) => {
                const dir = sort?.key === c.key ? sort.dir : null;
                return (
                  <th
                    key={c.key}
                    scope="col"
                    style={c.width ? { width: c.width } : undefined}
                    aria-sort={dir === 'asc' ? 'ascending' : dir === 'desc' ? 'descending' : undefined}
                    className={cn('h-9 px-3 text-left text-2xs uppercase text-muted', c.align === 'right' && 'text-right')}
                  >
                    {c.sortValue ? (
                      <button
                        type="button"
                        onClick={() => setSort((s) => nextSort(s, c.key))}
                        className={cn('-mx-1 inline-flex items-center gap-1 rounded-sm px-1 uppercase hover:text-fg', c.align === 'right' && 'flex-row-reverse')}
                      >
                        {c.header}
                        <SortIcon dir={dir} />
                      </button>
                    ) : (
                      c.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {state === 'loading' &&
              Array.from({ length: 4 }, (_, i) => (
                <tr key={i} className="border-b border-line last:border-0">
                  {Array.from({ length: colSpan }, (__, j) => (
                    <td key={j} className="h-11 px-3"><div className="skeleton h-3" style={{ width: `${40 + ((i * 7 + j * 13) % 45)}%` }} /></td>
                  ))}
                </tr>
              ))}
            {state === 'error' && (
              <tr><td colSpan={colSpan}>
                <TableMessage icon={<CloudOff />} tone="danger" title={t('table.errorTitle')} body={t('table.errorBody')}>
                  {onRetry && <Button size="sm" onClick={onRetry}>{t('table.retry')}</Button>}
                </TableMessage>
              </td></tr>
            )}
            {state === 'ready' && view.total === 0 && (
              <tr><td colSpan={colSpan}>
                {filter ? (
                  <TableMessage icon={<Search />} title={t('table.noMatchTitle', { filter })} body={t('table.noMatchBody')}>
                    <Button size="sm" variant="ghost" onClick={() => setFilter('')}>{t('table.clearFilter')}</Button>
                  </TableMessage>
                ) : (
                  <TableMessage icon={<Inbox />} title={empty?.title ?? t('table.emptyTitle')} body={empty?.body ?? ''}>{empty?.action}</TableMessage>
                )}
              </td></tr>
            )}
            {showRows &&
              view.rows.map((r) => {
                const id = rowId(r);
                const on = selected.has(id);
                return (
                  <tr
                    key={id}
                    aria-selected={bulkActions ? on : undefined}
                    onDoubleClick={onRowOpen ? () => onRowOpen(r) : undefined}
                    className={cn('h-11 border-b border-line transition-colors duration-fast last:border-0 hover:bg-surface-2/60', on && 'bg-accent-soft/60 hover:bg-accent-soft')}
                  >
                    {bulkActions && (
                      <td className="px-3"><Checkbox checked={on} onCheckedChange={(v) => toggle(id, v)} aria-label={t('table.selectRowAriaLabel', { id })} /></td>
                    )}
                    {columns.map((c) => (
                      <td key={c.key} className={cn('px-3 text-fg', c.align === 'right' && 'text-right')}>{c.cell(r)}</td>
                    ))}
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>
      {showRows && (
        <nav aria-label={t('table.paginationAriaLabel')} className="flex items-center justify-between gap-3 border-t border-line px-3 py-2 text-sm text-muted">
          <span className="num" aria-live="polite">{(view.page - 1) * pageSize + 1}–{Math.min(view.page * pageSize, view.total)} / {view.total}</span>
          <div className="flex items-center gap-1">
            <Button size="sm" variant="ghost" iconOnly icon={<ChevronLeft />} aria-label={t('table.prevPage')} disabled={view.page <= 1} onClick={() => setPage(view.page - 1)} />
            <span className="num px-1" aria-current="page">{view.page} / {view.pages}</span>
            <Button size="sm" variant="ghost" iconOnly icon={<ChevronRight />} aria-label={t('table.nextPage')} disabled={view.page >= view.pages} onClick={() => setPage(view.page + 1)} />
          </div>
        </nav>
      )}
    </div>
  );
}

function TableMessage({ icon, title, body, tone, children }: { icon: ReactNode; title: string; body: string; tone?: 'danger'; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-12 text-center" role={tone === 'danger' ? 'alert' : undefined}>
      <span className={cn('grid size-10 place-items-center rounded-md border [&_svg]:size-5', tone === 'danger' ? 'border-danger/25 bg-danger-soft text-danger' : 'border-line bg-surface-2 text-muted')}>{icon}</span>
      <p className="mt-1 text-md font-semibold text-fg">{title}</p>
      {body && <p className="max-w-sm text-sm text-muted">{body}</p>}
      {children && <div className="mt-2">{children}</div>}
    </div>
  );
}
