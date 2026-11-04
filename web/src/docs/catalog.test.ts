import { describe, expect, it } from 'vitest';
import { buildCatalog, neighbours, overlayByName, parseDoc, searchDocs } from './catalog';

const doc = (id: string, group: string, order: number, body = '', extra = '') =>
  `---\nid: ${id}\ntitle: ${id.toUpperCase()}\ngroup: ${group}\norder: ${order}\nsummary: ${id} haqida\n${extra}---\n# ${id.toUpperCase()}\n\n${body}\n`;

describe('parseDoc', () => {
  it('sarlavha blokini va tanani ajratadi', () => {
    const d = parseDoc('ivr.md', doc('ivr', 'routing', 20, 'Ovozli menyu.', 'path: /ivr\n'));
    expect(d).toMatchObject({ id: 'ivr', title: 'IVR', group: 'routing', order: 20, path: '/ivr', summary: 'ivr haqida' });
    expect(d.body.trim()).toBe('# IVR\n\nOvozli menyu.');
  });

  it('noma\'lum guruh, raqam bo\'lmagan order yoki fayl nomiga mos kelmagan id — xato (qurishda ushlanadi)', () => {
    expect(() => parseDoc('a.md', doc('a', 'nimadir', 1))).toThrow(/group/);
    expect(() => parseDoc('a.md', doc('a', 'apps', Number.NaN))).toThrow(/order/);
    expect(() => parseDoc('b.md', doc('a', 'apps', 1))).toThrow(/id/);
    expect(() => parseDoc('a.md', '# sarlavhasiz')).toThrow(/sarlavha bloki/);
  });
});

describe('buildCatalog', () => {
  const raw = {
    '/x/ivr.md': doc('ivr', 'routing', 20),
    '/x/queues.md': doc('queues', 'routing', 10),
    '/x/kirish.md': doc('kirish', 'start', 10),
    '/x/_FORMAT.md': 'yozuvchilar uchun',
  };

  it('`_` bilan boshlangan fayl tashlanadi; guruhlar DOC_GROUPS tartibida, ichida order bo\'yicha', () => {
    const cat = buildCatalog(raw);
    expect(cat.groups.map((g) => [g.id, g.docs.map((d) => d.id)])).toEqual([['start', ['kirish']], ['routing', ['queues', 'ivr']]]);
    expect(cat.flat.map((d) => d.id)).toEqual(['kirish', 'queues', 'ivr']);
    expect(cat.byId.get('ivr')?.title).toBe('IVR');
  });

  it('qo\'shni bo\'limlar (oldingi/keyingi) tekis tartib bo\'yicha', () => {
    const cat = buildCatalog(raw);
    expect(neighbours(cat, 'queues')).toEqual({ prev: cat.byId.get('kirish'), next: cat.byId.get('ivr') });
    expect(neighbours(cat, 'kirish').prev).toBeUndefined();
    expect(neighbours(cat, 'ivr').next).toBeUndefined();
  });
});

describe('searchDocs', () => {
  const cat = buildCatalog({
    '/x/a.md': doc('a', 'apps', 10, 'Bu yerda kampaniya haqida gap boradi. **Navbat** emas.'),
    '/x/navbat.md': doc('navbat', 'routing', 10, 'Qo\'ng\'iroqlar navbati.'),
  });

  it('bo\'sh so\'rov — hech narsa', () => {
    expect(searchDocs(cat, '  ')).toEqual([]);
  });

  it('sarlavhadagi moslik matndagidan yuqorida; registrga bog\'liq emas', () => {
    expect(searchDocs(cat, 'NAVBAT').map((r) => r.doc.id)).toEqual(['navbat', 'a']);
  });

  it('matndagi moslik uchun formatlashsiz parcha qaytaradi', () => {
    const [hit] = searchDocs(cat, 'kampaniya');
    expect(hit?.doc.id).toBe('a');
    expect(hit?.snippet).toContain('kampaniya haqida');
    expect(hit?.snippet).not.toContain('**');
  });

  it('bir nechta so\'z — hammasi bo\'lishi kerak', () => {
    expect(searchDocs(cat, 'kampaniya navbat').map((r) => r.doc.id)).toEqual(['a']);
  });
});

describe('overlayByName', () => {
  it('tarjima fayli asl faylni nomi bo\'yicha almashtiradi, tarjimasizi asl tilda qoladi', () => {
    const merged = overlayByName(
      { '../docs/qollanma/ivr.md': 'uz-ivr', '../docs/qollanma/cdr.md': 'uz-cdr' },
      { '../docs/qollanma/ru/ivr.md': 'ru-ivr' },
    );
    expect(merged).toEqual({ 'ivr.md': 'ru-ivr', 'cdr.md': 'uz-cdr' });
  });

  it('asl tilda yo\'q tarjima fayli ham kiradi (buildCatalog uni tekshiradi)', () => {
    expect(overlayByName({}, { 'en/x.md': 'en-x' })).toEqual({ 'x.md': 'en-x' });
  });
});
