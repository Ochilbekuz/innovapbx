// Qo'llanma markdown'ining kichik to'plami (docs/qollanma/_FORMAT.md §2) — AST xatti-harakati.
import { describe, expect, it } from 'vitest';
import { headingAnchor, parseInline, parseMarkdown, plainText, safeHref } from './markdown';

describe('parseInline', () => {
  it('oddiy matn — bitta text tugun', () => {
    expect(parseInline('salom dunyo')).toEqual([{ t: 'text', v: 'salom dunyo' }]);
  });

  it('qalin, kursiv, kod va havola', () => {
    expect(parseInline('a **Saqlash** b *kursiv* `*28` [IVR](/docs/ivr) z')).toEqual([
      { t: 'text', v: 'a ' },
      { t: 'strong', c: [{ t: 'text', v: 'Saqlash' }] },
      { t: 'text', v: ' b ' },
      { t: 'em', c: [{ t: 'text', v: 'kursiv' }] },
      { t: 'text', v: ' ' },
      { t: 'code', v: '*28' },
      { t: 'text', v: ' ' },
      { t: 'link', href: '/docs/ivr', c: [{ t: 'text', v: 'IVR' }] },
      { t: 'text', v: ' z' },
    ]);
  });

  it('kod ichidagi yulduzcha formatlanmaydi', () => {
    expect(parseInline('`**x**`')).toEqual([{ t: 'code', v: '**x**' }]);
  });

  it('yolg\'iz yulduzcha (xususiyat kodi *97) matn bo\'lib qoladi', () => {
    expect(parseInline('*97 ni tering')).toEqual([{ t: 'text', v: '*97 ni tering' }]);
  });

  it('qalin ichida havola', () => {
    expect(parseInline('**[a](/b)**')).toEqual([{ t: 'strong', c: [{ t: 'link', href: '/b', c: [{ t: 'text', v: 'a' }] }] }]);
  });
});

describe('safeHref', () => {
  it.each([
    ['/docs/ivr', '/docs/ivr'],
    ['/extensions', '/extensions'],
    ['#maydonlar', '#maydonlar'],
    ['https://example.uz/x', 'https://example.uz/x'],
    ['http://example.uz', 'http://example.uz'],
  ])('%s ruxsat etiladi', (href, out) => expect(safeHref(href)).toBe(out));

  it.each(['javascript:alert(1)', '//evil.example', 'data:text/html,x', 'mailto:x@y', ''])('%s rad etiladi', (href) => {
    expect(safeHref(href)).toBeNull();
  });
});

describe('headingAnchor', () => {
  it('kichik harf, apostrof tushadi, boshqa belgilar chiziqcha', () => {
    expect(headingAnchor("Qanday qo'shiladi?")).toBe('qanday-qoshiladi');
    expect(headingAnchor('Maydonlar va  sozlamalar')).toBe('maydonlar-va-sozlamalar');
    expect(headingAnchor('Oʻchirish (ehtiyot)')).toBe('ochirish-ehtiyot');
  });
});

describe('parseMarkdown', () => {
  it('sarlavhalar darajasi va takroriy langarlar noyob', () => {
    const blocks = parseMarkdown('# Bosh\n\n## Qadam\n\n### Qadam\n');
    expect(blocks.map((b) => (b.t === 'heading' ? [b.level, b.anchor] : null))).toEqual([[1, 'bosh'], [2, 'qadam'], [3, 'qadam-2']]);
  });

  it('paragraf — ketma-ket qatorlar bitta bo\'shliq bilan qo\'shiladi', () => {
    expect(parseMarkdown('bir\nikki\n\nuch')).toEqual([
      { t: 'para', c: [{ t: 'text', v: 'bir ikki' }] },
      { t: 'para', c: [{ t: 'text', v: 'uch' }] },
    ]);
  });

  it('raqamlangan va oddiy ro\'yxat, ichma-ich daraja', () => {
    const [list] = parseMarkdown('1. Bir\n2. Ikki\n  - ichki a\n  - ichki b\n3. Uch');
    expect(list).toEqual({
      t: 'list', ordered: true, items: [
        { c: [{ t: 'text', v: 'Bir' }] },
        { c: [{ t: 'text', v: 'Ikki' }], sub: { ordered: false, items: [[{ t: 'text', v: 'ichki a' }], [{ t: 'text', v: 'ichki b' }]] } },
        { c: [{ t: 'text', v: 'Uch' }] },
      ],
    });
  });

  it('ro\'yxat bandining davomi (chekinishli qator) shu bandga qo\'shiladi', () => {
    const [list] = parseMarkdown('- birinchi\n  davomi\n- ikkinchi');
    expect(list).toEqual({ t: 'list', ordered: false, items: [{ c: [{ t: 'text', v: 'birinchi davomi' }] }, { c: [{ t: 'text', v: 'ikkinchi' }] }] });
  });

  it('jadval: sarlavha, ajratgich va qatorlar; kod ichidagi | buzmaydi', () => {
    const [table] = parseMarkdown('| Kod | Nima |\n|---|:---|\n| `*28` | Kun/Tun |\n| `a\\|b` | x |');
    expect(table).toEqual({
      t: 'table',
      head: [[{ t: 'text', v: 'Kod' }], [{ t: 'text', v: 'Nima' }]],
      rows: [
        [[{ t: 'code', v: '*28' }], [{ t: 'text', v: 'Kun/Tun' }]],
        [[{ t: 'code', v: 'a|b' }], [{ t: 'text', v: 'x' }]],
      ],
    });
  });

  it('kod bloki — ichidagi markdown xom qoladi', () => {
    expect(parseMarkdown('```bash\n# izoh\nsudo ./install.sh\n```')).toEqual([{ t: 'code', lang: 'bash', v: '# izoh\nsudo ./install.sh' }]);
  });

  it('ichki band davomi ichki bandga, ro\'yxatdan keyingi chekinishsiz satr — yangi paragraf', () => {
    const [list, para] = parseMarkdown('- bosh\n  - ichki\n    davomi\noddiy matn');
    expect(list).toEqual({ t: 'list', ordered: false, items: [{ c: [{ t: 'text', v: 'bosh' }], sub: { ordered: false, items: [[{ t: 'text', v: 'ichki davomi' }]] } }] });
    expect(para).toEqual({ t: 'para', c: [{ t: 'text', v: 'oddiy matn' }] });
  });

  it('yopilmagan kod bloki fayl oxirigacha davom etadi (yo\'qolmaydi)', () => {
    expect(parseMarkdown('```\nx')).toEqual([{ t: 'code', lang: '', v: 'x' }]);
  });

  it('[!WARNING] eslatma bloki va oddiy iqtibos', () => {
    expect(parseMarkdown('> [!WARNING]\n> Ehtiyot **bo\'ling**.\n\n> oddiy')).toEqual([
      { t: 'callout', kind: 'warning', blocks: [{ t: 'para', c: [{ t: 'text', v: 'Ehtiyot ' }, { t: 'strong', c: [{ t: 'text', v: "bo'ling" }] }, { t: 'text', v: '.' }] }] },
      { t: 'quote', blocks: [{ t: 'para', c: [{ t: 'text', v: 'oddiy' }] }] },
    ]);
  });

  it('paragraf sarlavha/ro\'yxat/jadval boshlanganda uziladi', () => {
    expect(parseMarkdown('matn\n## S\nmatn2\n- a').map((b) => b.t)).toEqual(['para', 'heading', 'para', 'list']);
  });
});

describe('plainText', () => {
  it('formatlashsiz matn (qidiruv uchun)', () => {
    expect(plainText(parseInline('**A** `b` [c](/d)'))).toBe('A b c');
  });
});
