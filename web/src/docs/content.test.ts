// Haqiqiy qo'llanma fayllari tekshiruvi: har fayl to'g'ri formatda, har ichki havola mavjud bo'limga yoki
// panel ekraniga olib boradi, har menyu ekranining o'z bo'limi bor (sahifadagi «?» tugmasi bo'sh qolmasin).
// Uchala til (uz/ru/en) uchun; ru/en — uz asli bilan bir xil tuzilmada va to'liq tarjima qilingan.
import { describe, expect, it } from 'vitest';
import { EXTRA_ROUTES, SCREENS } from '@/shell/screens';
import { parseMarkdown, safeHref, type Block, type Inline } from './markdown';
import { LANGS } from '@/lib/i18n';
import { CATALOGS, TRANSLATED, catalogFor } from './content';

/** Hali qurilmagan (ScreenStub) ekranlar — hujjat talab qilinmaydi. */
const NO_DOC_SCREENS = ['license'];

const APP_PATHS = [
  ...SCREENS.map((s) => s.path), ...EXTRA_ROUTES.map((r) => r.path.replace(/\/:id$/, '')),
  '/settings/revisions', '/change-password', '/enroll-2fa', '/setup', '/login', '/docs',
];

function linksOf(blocks: Block[]): string[] {
  const fromInline = (nodes: Inline[]): string[] =>
    nodes.flatMap((n) => (n.t === 'link' ? [n.href, ...fromInline(n.c)] : n.t === 'strong' || n.t === 'em' ? fromInline(n.c) : []));
  return blocks.flatMap((b): string[] => {
    switch (b.t) {
      case 'heading': case 'para': return fromInline(b.c);
      case 'list': return b.items.flatMap((it) => [...fromInline(it.c), ...(it.sub?.items.flatMap(fromInline) ?? [])]);
      case 'table': return [...b.head, ...b.rows.flat()].flatMap(fromInline);
      case 'callout': case 'quote': return linksOf(b.blocks);
      default: return [];
    }
  });
}

describe.each(LANGS)("qo'llanma fayllari (%s)", (lang) => {
  const CATALOG = CATALOGS[lang];

  it('kamida bitta bo\'lim bor va har bo\'limda title/summary to\'ldirilgan', () => {
    expect(CATALOG.flat.length).toBeGreaterThan(0);
    for (const d of CATALOG.flat) {
      expect(d.summary, d.id).not.toBe('');
      expect(d.summary.length, `${d.id}: summary 160 belgidan uzun`).toBeLessThanOrEqual(160);
    }
  });

  it('har menyu ekranining o\'z bo\'limi bor (id = ekran id)', () => {
    const missing = SCREENS.filter((s) => !NO_DOC_SCREENS.includes(s.id) && !CATALOG.byId.has(s.id)).map((s) => s.id);
    expect(missing).toEqual([]);
  });

  it('ekran bo\'limidagi `path` ekranning haqiqiy manziliga teng', () => {
    for (const s of SCREENS) {
      const d = CATALOG.byId.get(s.id);
      if (d?.path) expect(d.path, s.id).toBe(s.path);
    }
  });

  it('har havola xavfsiz va ichki havolalar mavjud bo\'lim/ekranga olib boradi', () => {
    const bad: string[] = [];
    for (const d of CATALOG.flat) {
      for (const href of linksOf(parseMarkdown(d.body))) {
        const ok = safeHref(href);
        const path = href.split('#')[0] ?? '';
        const docId = /^\/docs\/([^/#]+)$/.exec(path)?.[1];
        if (!ok) bad.push(`${d.id}: ${href} (xavfli)`);
        else if (docId && !CATALOG.byId.has(docId)) bad.push(`${d.id}: ${href} (bo'lim yo'q)`);
        else if (path.startsWith('/') && !docId && !APP_PATHS.includes(path)) bad.push(`${d.id}: ${href} (ekran yo'q)`);
      }
    }
    expect(bad).toEqual([]);
  });

  it('HTML teg ishlatilmagan (panel ko\'rsatmaydi)', () => {
    const withHtml = CATALOG.flat.filter((d) => /^\s*<[a-z!]/im.test(d.body.replace(/```[\s\S]*?```/g, ''))).map((d) => d.id);
    expect(withHtml).toEqual([]);
  });
});

describe('tarjimalar', () => {
  const uz = CATALOGS.uz;

  it.each(['ru', 'en'] as const)('%s: har uz bo\'limi tarjima qilingan, ortiqcha fayl yo\'q', (lang) => {
    expect([...TRANSLATED[lang]].sort()).toEqual(uz.flat.map((d) => d.id).sort());
  });

  it.each(['ru', 'en'] as const)('%s: guruh/tartib/ekran manzili va ichki havolalar uz asli bilan bir xil', (lang) => {
    const internal = (body: string) => [...new Set(linksOf(parseMarkdown(body)).filter((h) => h.startsWith('/')))].sort();
    for (const d of CATALOGS[lang].flat) {
      const src = uz.byId.get(d.id);
      expect({ group: d.group, order: d.order, path: d.path }, d.id).toEqual({ group: src?.group, order: src?.order, path: src?.path });
      expect(internal(d.body), d.id).toEqual(internal(src?.body ?? ''));
    }
  });

  it('tarjimalar haqiqatan boshqa tilda (uz matni nusxalanmagan)', () => {
    expect(CATALOGS.ru.byId.get('ivr')?.body).toMatch(/[а-яё]/i);
    expect(CATALOGS.en.byId.get('extensions')?.title).not.toBe(uz.byId.get('extensions')?.title);
  });

  it('catalogFor: til kodi bo\'yicha katalog, noma\'lum til — uz', () => {
    expect(catalogFor('ru')).toBe(CATALOGS.ru);
    expect(catalogFor('en')).toBe(CATALOGS.en);
    expect(catalogFor('de')).toBe(uz);
    expect(catalogFor(undefined)).toBe(uz);
  });
});
