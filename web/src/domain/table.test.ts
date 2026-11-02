import { describe, expect, it } from 'vitest';
import { queryRows } from './table';

const rows = [
  { n: '103', name: 'Bobur' },
  { n: '101', name: 'Aziza' },
  { n: '102', name: 'Bekzod' },
  { n: '110', name: 'Dilnoza' },
];
const opts = { text: (r: (typeof rows)[number]) => `${r.n} ${r.name}`, value: (r: (typeof rows)[number], k: string) => r[k as 'n' | 'name'] };

describe('queryRows', () => {
  it('filtr → saralash → sahifa', () => {
    const r = queryRows(rows, { ...opts, filter: 'b', sort: { key: 'n', dir: 'desc' }, page: 1, pageSize: 1 });
    expect(r.total).toBe(2);
    expect(r.pages).toBe(2);
    expect(r.rows.map((x) => x.n)).toEqual(['103']);
  });

  it('raqamlarni tabiiy tartibda saralaydi', () => {
    const r = queryRows([{ n: '9', name: '' }, { n: '10', name: '' }], { ...opts, filter: '', sort: { key: 'n', dir: 'asc' }, page: 1, pageSize: 10 });
    expect(r.rows.map((x) => x.n)).toEqual(['9', '10']);
  });

  it('sahifa chegaradan oshsa — oxirgi sahifa', () => {
    const r = queryRows(rows, { ...opts, filter: '', sort: null, page: 9, pageSize: 3 });
    expect(r.page).toBe(2);
    expect(r.rows).toHaveLength(1);
  });
});
