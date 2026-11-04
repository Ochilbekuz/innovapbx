// Qo'llanma katalogi: `docs/qollanma/*.md` xom matnlaridan mundarija, qidiruv va qo'shni bo'limlar.
// Fayl formati — ../../../docs/qollanma/_FORMAT.md. Sof funksiyalar; fayllarni `content.ts` yuklaydi.
import { GROUP_ORDER } from '@/shell/screens';

export const DOC_GROUPS = ['start', ...GROUP_ORDER, 'appendix'] as const;
export type DocGroup = (typeof DOC_GROUPS)[number];

export type Doc = {
  id: string;
  title: string;
  group: DocGroup;
  order: number;
  path?: string;
  summary: string;
  /** Sarlavha blokisiz markdown. */
  body: string;
};

export type Catalog = {
  groups: { id: DocGroup; docs: Doc[] }[];
  flat: Doc[];
  byId: Map<string, Doc>;
};

const FRONT_RE = /^---\n([\s\S]*?)\n---\n?/;

function readFields(block: string): Record<string, string> {
  const fields: Record<string, string> = {};
  for (const line of block.split('\n')) {
    const m = /^([a-z]+):\s*(.*)$/.exec(line.trim());
    if (m?.[1]) fields[m[1]] = (m[2] ?? '').trim();
  }
  return fields;
}

const isDocGroup = (g: string | undefined): g is DocGroup => g !== undefined && (DOC_GROUPS as readonly string[]).includes(g);

const baseName = (path: string) => path.replace(/^.*\//, '');

/** Bitta faylni tekshiradi; xato bo'lsa — fayl nomi bilan otadi (test/qurishda ushlanadi, jimgina tushib qolmaydi). */
export function parseDoc(fileName: string, raw: string): Doc {
  const src = raw.replace(/\r\n?/g, '\n');
  const m = FRONT_RE.exec(src);
  if (!m) throw new Error(`${fileName}: sarlavha bloki (---) yo'q`);
  const f = readFields(m[1] ?? '');
  const fileId = baseName(fileName).replace(/\.md$/, '');
  const order = Number(f.order);
  if (f.id !== fileId) throw new Error(`${fileName}: id "${f.id}" fayl nomiga mos emas`);
  if (!f.title) throw new Error(`${fileName}: title yo'q`);
  if (!isDocGroup(f.group)) throw new Error(`${fileName}: noma'lum group "${f.group}"`);
  if (!Number.isFinite(order)) throw new Error(`${fileName}: order raqam emas`);
  return {
    id: fileId, title: f.title, group: f.group, order,
    ...(f.path ? { path: f.path } : {}),
    summary: f.summary ?? '',
    body: src.slice(m[0].length),
  };
}

/** Tarjima fayllarini asl fayllar ustiga nomi bo'yicha qo'yadi: tarjimasi yo'q bo'lim asl tilda qoladi (yo'qolmaydi). */
export function overlayByName(base: Record<string, string>, over: Record<string, string>): Record<string, string> {
  const byName = (files: Record<string, string>) => Object.entries(files).map(([path, raw]) => [baseName(path), raw] as const);
  return Object.fromEntries([...byName(base), ...byName(over)]);
}

export function buildCatalog(files: Record<string, string>): Catalog {
  const flatUnsorted = Object.entries(files)
    .filter(([name]) => !/(^|\/)_[^/]*$/.test(name))
    .map(([name, raw]) => parseDoc(name, raw));
  const groups = DOC_GROUPS
    .map((id) => ({ id, docs: flatUnsorted.filter((d) => d.group === id).sort((a, b) => a.order - b.order || a.id.localeCompare(b.id)) }))
    .filter((g) => g.docs.length > 0);
  const flat = groups.flatMap((g) => g.docs);
  return { groups, flat, byId: new Map(flat.map((d) => [d.id, d])) };
}

export function neighbours(cat: Catalog, id: string): { prev?: Doc; next?: Doc } {
  const i = cat.flat.findIndex((d) => d.id === id);
  if (i < 0) return {};
  return { prev: cat.flat[i - 1], next: cat.flat[i + 1] };
}

// ── Qidiruv ─────────────────────────────────────────────────────────────────────────────────────

/** Markdown belgilarisiz matn (qidiruv va parcha uchun). */
export function toPlain(md: string): string {
  return md
    .replace(/```[\w-]*\n?/g, ' ')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/\[!(NOTE|TIP|WARNING|CAUTION)\]/gi, ' ')
    .replace(/^#{1,3}\s+/gm, '')
    .replace(/^>\s?/gm, '')
    .replace(/^\|?[\s:|-]+\|?$/gm, ' ')
    .replace(/\*\*|`|\|/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export type SearchHit = { doc: Doc; snippet: string };

const SNIPPET_RADIUS = 70;

function snippetAround(text: string, at: number): string {
  const from = Math.max(0, at - SNIPPET_RADIUS);
  const to = Math.min(text.length, at + SNIPPET_RADIUS);
  return `${from > 0 ? '…' : ''}${text.slice(from, to).trim()}${to < text.length ? '…' : ''}`;
}

type Haystack = { title: string; summary: string; body: string };

const TERM_WEIGHTS: [keyof Haystack, number][] = [['title', 10], ['summary', 5], ['body', 1]];

/** Har so'z kamida bitta maydonda bo'lishi shart; aks holda `null`. */
function scoreDoc(hay: Haystack, terms: string[]): number | null {
  let score = 0;
  for (const t of terms) {
    const s = TERM_WEIGHTS.reduce((acc, [field, w]) => acc + (hay[field].includes(t) ? w : 0), 0);
    if (s === 0) return null;
    score += s;
  }
  return score;
}

export function searchDocs(cat: Catalog, query: string): SearchHit[] {
  const terms = query.toLocaleLowerCase().split(/\s+/).filter(Boolean);
  if (terms.length === 0) return [];
  const scored = cat.flat.flatMap((doc) => {
    const plain = toPlain(doc.body);
    const hay = { title: doc.title.toLocaleLowerCase(), summary: doc.summary.toLocaleLowerCase(), body: plain.toLocaleLowerCase() };
    const score = scoreDoc(hay, terms);
    if (score === null) return [];
    const at = hay.body.indexOf(terms[0] ?? '');
    return [{ doc, score, snippet: at >= 0 ? snippetAround(plain, at) : doc.summary }];
  });
  return scored.sort((a, b) => b.score - a.score).map(({ doc, snippet }) => ({ doc, snippet }));
}
