export type Sort = { key: string; dir: 'asc' | 'desc' } | null;

type Query<T> = {
  filter: string;
  sort: Sort;
  page: number;
  pageSize: number;
  /** Qidiruv uchun qatorning matni. */
  text: (row: T) => string;
  /** Saralash uchun ustun qiymati. */
  value: (row: T, key: string) => string | number;
};

const collator = new Intl.Collator('uz', { numeric: true, sensitivity: 'base' });

function compare(a: string | number, b: string | number): number {
  return typeof a === 'number' && typeof b === 'number' ? a - b : collator.compare(String(a), String(b));
}

/** Filtr → saralash → sahifalash. Sof funksiya: server tomonda ham xuddi shu tartib. */
export function queryRows<T>(rows: readonly T[], q: Query<T>) {
  const needle = q.filter.trim().toLocaleLowerCase('uz');
  const filtered = needle ? rows.filter((r) => q.text(r).toLocaleLowerCase('uz').includes(needle)) : [...rows];
  const sort = q.sort;
  if (sort) {
    const sign = sort.dir === 'asc' ? 1 : -1;
    filtered.sort((a, b) => sign * compare(q.value(a, sort.key), q.value(b, sort.key)));
  }
  const pages = Math.max(1, Math.ceil(filtered.length / q.pageSize));
  const page = Math.min(Math.max(1, q.page), pages);
  const start = (page - 1) * q.pageSize;
  return { rows: filtered.slice(start, start + q.pageSize), total: filtered.length, pages, page };
}
