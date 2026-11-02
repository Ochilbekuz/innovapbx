import { describe, expect, it } from 'vitest';
import { formatNumber, resolveDestination, type Catalog } from './destination';
import { buildFlow, flowIssues, issueList } from './flow';

const catalog: Catalog = {
  ivr1: { id: 'ivr1', kind: 'ivr', name: 'Asosiy menyu', number: '7000', next: [
    { label: '1', dest: { kind: 'queue', targetId: 'q1' } },
    { label: '2', dest: { kind: 'extension', targetId: 'gone' } },
    { label: 'vaqt tugadi', dest: { kind: 'ivr', targetId: 'ivr1' } },
  ] },
  q1: { id: 'q1', kind: 'queue', name: 'Sotuv', number: '600', next: [{ label: 'toʻlsa', dest: { kind: 'hangup', targetId: 'hu1' } }] },
  e101: { id: 'e101', kind: 'extension', name: 'Dilnoza Karimova', number: '101' },
  hu1: { id: 'hu1', kind: 'hangup', name: 'Qoʻngʻiroqni yakunlash' },
};

describe('resolveDestination', () => {
  it("tanlanmagan — bo'sh holat", () => {
    expect(resolveDestination(null, catalog).state).toBe('empty');
  });

  it('mavjud obyekt — ok va nom', () => {
    const r = resolveDestination({ kind: 'extension', targetId: 'e101' }, catalog);
    expect(r).toMatchObject({ state: 'ok', label: 'Dilnoza Karimova', number: '101' });
  });

  it("o'chirilgan obyekt — singan havola, turi saqlanadi", () => {
    const r = resolveDestination({ kind: 'queue', targetId: 'q404' }, catalog);
    expect(r).toMatchObject({ state: 'broken', kind: 'queue' });
  });

  it('id bor, lekin turi boshqa — ham singan', () => {
    expect(resolveDestination({ kind: 'ivr', targetId: 'e101' }, catalog).state).toBe('broken');
  });

  it('tashqi raqam: yaroqli va yaroqsiz', () => {
    expect(resolveDestination({ kind: 'external', number: '+998 90 123-45-67' }, catalog)).toMatchObject({
      state: 'ok',
      number: '+998901234567',
    });
    expect(resolveDestination({ kind: 'external', number: '12' }, catalog).state).toBe('invalid');
  });

  it('osish (hangup) — tizim manzili, katalogda id orqali topiladi', () => {
    expect(resolveDestination({ kind: 'hangup', targetId: 'hu1' }, catalog).state).toBe('ok');
  });
});

describe('buildFlow', () => {
  it('halqa va singan manzilni topadi, daraxt cheksiz emas', () => {
    const tree = buildFlow({ kind: 'ivr', targetId: 'ivr1' }, catalog);
    expect(tree.children.map((c) => c.state)).toEqual(['ok', 'broken', 'loop']);
    expect(tree.children[0]?.children[0]?.resolved).toMatchObject({ state: 'ok', kind: 'hangup' });
    expect(flowIssues(tree)).toEqual({ loops: 1, broken: 1 });
  });

  it('toza oqimda muammo yoʻq', () => {
    expect(flowIssues(buildFlow({ kind: 'queue', targetId: 'q1' }, catalog))).toEqual({ loops: 0, broken: 0 });
  });

  it('muammolar roʻyxati: tur va yoʻl (tarmoq yorliqlari)', () => {
    const tree = buildFlow({ kind: 'ivr', targetId: 'ivr1' }, catalog);
    expect(issueList(tree)).toEqual([
      { state: 'broken', key: tree.children[1]?.key, path: ['2'] },
      { state: 'loop', key: tree.children[2]?.key, path: ['vaqt tugadi'] },
    ]);
  });

  it('toza oqimda roʻyxat boʻsh', () => {
    expect(issueList(buildFlow({ kind: 'queue', targetId: 'q1' }, catalog))).toEqual([]);
  });
});

describe('formatNumber', () => {
  it('Oʻzbekiston raqamini guruhlaydi', () => {
    expect(formatNumber('+998903184207')).toBe('+998 90 318 42 07');
    expect(formatNumber('998712000000')).toBe('+998 71 200 00 00');
  });
  it('qisqa va xorijiy raqam oʻzgarmaydi', () => {
    expect(formatNumber('101')).toBe('101');
    expect(formatNumber('+74951234567')).toBe('+74951234567');
  });
});
