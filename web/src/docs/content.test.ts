// Haqiqiy qo'llanma fayllari tekshiruvi: har fayl to'g'ri formatda, har ichki havola mavjud bo'limga yoki
// panel ekraniga olib boradi, har menyu ekranining o'z bo'limi bor (sahifadagi «?» tugmasi bo'sh qolmasin).
import { describe, expect, it } from 'vitest';
import { EXTRA_ROUTES, SCREENS } from '@/shell/screens';
import { parseMarkdown, safeHref, type Block, type Inline } from './markdown';
import { CATALOG } from './content';

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

describe("qo'llanma fayllari", () => {
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
