// Qo'llanma uchun markdown'ning kichik, xavfsiz to'plami (qarang ../../../docs/qollanma/_FORMAT.md §2).
// Natija — oddiy AST; React'ga `Markdown.tsx` aylantiradi (HTML satr yo'q → XSS yo'q).

export type Inline =
  | { t: 'text'; v: string }
  | { t: 'strong'; c: Inline[] }
  | { t: 'em'; c: Inline[] }
  | { t: 'code'; v: string }
  | { t: 'link'; href: string; c: Inline[] };

export type CalloutKind = 'note' | 'tip' | 'warning' | 'caution';
export type SubList = { ordered: boolean; items: Inline[][] };
export type ListItem = { c: Inline[]; sub?: SubList };

export type Block =
  | { t: 'heading'; level: 1 | 2 | 3; c: Inline[]; anchor: string }
  | { t: 'para'; c: Inline[] }
  | { t: 'list'; ordered: boolean; items: ListItem[] }
  | { t: 'table'; head: Inline[][]; rows: Inline[][][] }
  | { t: 'code'; lang: string; v: string }
  | { t: 'callout'; kind: CalloutKind; blocks: Block[] }
  | { t: 'quote'; blocks: Block[] };

// ── Inline ──────────────────────────────────────────────────────────────────────────────────────

const INLINE_RE = /`([^`]+)`|\*\*(.+?)\*\*|\*([^*\s](?:[^*]*[^*\s])?)\*|\[([^\]]+)\]\(([^)\s]+)\)/g;

export function parseInline(src: string): Inline[] {
  const out: Inline[] = [];
  let last = 0;
  for (const m of src.matchAll(INLINE_RE)) {
    const at = m.index ?? 0;
    if (at > last) out.push({ t: 'text', v: src.slice(last, at) });
    const [, code, strong, em, label = '', href = ''] = m;
    if (code !== undefined) out.push({ t: 'code', v: code });
    else if (strong !== undefined) out.push({ t: 'strong', c: parseInline(strong) });
    else if (em !== undefined) out.push({ t: 'em', c: parseInline(em) });
    else out.push({ t: 'link', href, c: parseInline(label) });
    last = at + m[0].length;
  }
  if (last < src.length) out.push({ t: 'text', v: src.slice(last) });
  return out;
}

export function plainText(nodes: Inline[]): string {
  return nodes.map((n) => (n.t === 'text' || n.t === 'code' ? n.v : plainText(n.c))).join('');
}

/** Faqat ilova ichidagi yo'l (`/x`, `//` emas), sahifa langari va http(s) — qolgani (javascript:, data:…) rad. */
export function safeHref(href: string): string | null {
  if (/^\/(?!\/)/.test(href) || /^#[\w-]+$/.test(href) || /^https?:\/\/[^\s]+$/i.test(href)) return href;
  return null;
}

export function headingAnchor(text: string): string {
  return text
    .toLowerCase()
    .replace(/['ʻʼ‘’`]/g, '')
    .replace(/[^\p{L}\p{N}]+/gu, '-')
    .replace(/^-+|-+$/g, '');
}

// ── Bloklar ─────────────────────────────────────────────────────────────────────────────────────

/** `noUncheckedIndexedAccess`: chegaradan tashqari qator — bo'sh satr (sikllar `length` bilan cheklangan). */
const ln = (lines: string[], i: number): string => lines[i] ?? '';

const HEADING_RE = /^(#{1,3})\s+(.*)$/;
const LIST_RE = /^(\s*)([-*]|\d+\.)\s+(.*)$/;
const FENCE_RE = /^```\s*([\w-]*)\s*$/;
const TABLE_SEP_RE = /^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;
const CALLOUT_RE = /^\[!(NOTE|TIP|WARNING|CAUTION)\]\s*$/i;

const isTableStart = (lines: string[], i: number) => ln(lines, i).trimStart().startsWith('|') && TABLE_SEP_RE.test(ln(lines, i + 1) ?? '');
const isBlockStart = (lines: string[], i: number) =>
  HEADING_RE.test(ln(lines, i)) || LIST_RE.test(ln(lines, i)) || FENCE_RE.test(ln(lines, i).trim()) || ln(lines, i).startsWith('>') || isTableStart(lines, i);

function splitRow(line: string): string[] {
  const body = line.trim().replace(/^\|/, '').replace(/(?<!\\)\|$/, '');
  return body.split(/(?<!\\)\|/).map((cell) => cell.trim().replace(/\\\|/g, '|'));
}

type Step = { block: Block; next: number };

function readFence(lines: string[], i: number): Step {
  const lang = FENCE_RE.exec(ln(lines, i).trim())?.[1] ?? '';
  let j = i + 1;
  while (j < lines.length && !/^```\s*$/.test(ln(lines, j).trim())) j++;
  return { block: { t: 'code', lang, v: lines.slice(i + 1, j).join('\n') }, next: j + 1 };
}

function readQuote(lines: string[], i: number, ctx: Ctx): Step {
  let j = i;
  const inner: string[] = [];
  while (j < lines.length && ln(lines, j).startsWith('>')) inner.push(ln(lines, j++).replace(/^>\s?/, ''));
  const kind = CALLOUT_RE.exec(inner[0]?.trim() ?? '')?.[1];
  if (kind) return { block: { t: 'callout', kind: kind.toLowerCase() as CalloutKind, blocks: parseLines(inner.slice(1), ctx) }, next: j };
  return { block: { t: 'quote', blocks: parseLines(inner, ctx) }, next: j };
}

function readTable(lines: string[], i: number): Step {
  let j = i + 2;
  const rows: Inline[][][] = [];
  while (j < lines.length && ln(lines, j).trimStart().startsWith('|')) rows.push(splitRow(ln(lines, j++)).map(parseInline));
  return { block: { t: 'table', head: splitRow(ln(lines, i)).map(parseInline), rows }, next: j };
}

type RawItem = { text: string; sub?: { ordered: boolean; items: string[] } };

/** Band davomi (chekinishli oddiy satr) — oxirgi ichki bandga, u bo'lmasa bandning o'ziga ulanadi. */
function continueItem(item: RawItem, line: string): void {
  const more = ` ${line.trim()}`;
  const tail = item.sub?.items ?? [];
  if (tail.length > 0) tail[tail.length - 1] += more; else item.text += more;
}

/** Ro'yxatning bitta qatorini qo'shadi: yangi band, ichki band yoki davom satri. `false` — ro'yxat tugadi. */
function addListLine(raw: RawItem[], line: string): boolean {
  const [, indent, marker = '', text = ''] = LIST_RE.exec(line) ?? [];
  const current = raw[raw.length - 1];
  if (indent !== undefined && indent.length < 2) raw.push({ text });
  else if (!current) return false;
  else if (indent !== undefined) (current.sub ??= { ordered: /\d/.test(marker), items: [] }).items.push(text);
  else if (/^\s+/.test(line)) continueItem(current, line);
  else return false;
  return true;
}

function readList(lines: string[], i: number): Step {
  const ordered = /\d/.test(LIST_RE.exec(ln(lines, i))?.[2] ?? '');
  const raw: RawItem[] = [];
  let j = i;
  while (j < lines.length && ln(lines, j).trim() !== '' && addListLine(raw, ln(lines, j))) j++;
  const items: ListItem[] = raw.map((r) => ({
    c: parseInline(r.text),
    ...(r.sub ? { sub: { ordered: r.sub.ordered, items: r.sub.items.map(parseInline) } } : {}),
  }));
  return { block: { t: 'list', ordered, items }, next: j };
}

function readHeading(lines: string[], i: number, ctx: Ctx): Step {
  const [, hashes = '#', text = ''] = HEADING_RE.exec(ln(lines, i)) ?? [];
  const c = parseInline(text.trim());
  return { block: { t: 'heading', level: hashes.length as 1 | 2 | 3, c, anchor: ctx.anchor(plainText(c)) }, next: i + 1 };
}

function readPara(lines: string[], i: number): Step {
  let j = i + 1;
  while (j < lines.length && ln(lines, j).trim() !== '' && !isBlockStart(lines, j)) j++;
  return { block: { t: 'para', c: parseInline(lines.slice(i, j).map((l) => l.trim()).join(' ')) }, next: j };
}

/** Hujjat bo'yicha umumiy holat: langarlar butun hujjatda noyob (iqtibos ichidagi sarlavha ham). */
type Ctx = { anchor: (text: string) => string };

function makeCtx(): Ctx {
  const seen = new Map<string, number>();
  return {
    anchor(text) {
      const base = headingAnchor(text) || 'bolim';
      const n = (seen.get(base) ?? 0) + 1;
      seen.set(base, n);
      return n === 1 ? base : `${base}-${n}`;
    },
  };
}

function readBlock(lines: string[], i: number, ctx: Ctx): Step {
  const line = ln(lines, i);
  if (FENCE_RE.test(line.trim())) return readFence(lines, i);
  if (HEADING_RE.test(line)) return readHeading(lines, i, ctx);
  if (line.startsWith('>')) return readQuote(lines, i, ctx);
  if (isTableStart(lines, i)) return readTable(lines, i);
  if (LIST_RE.test(line)) return readList(lines, i);
  return readPara(lines, i);
}

function parseLines(lines: string[], ctx: Ctx): Block[] {
  const blocks: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    if (ln(lines, i).trim() === '') { i++; continue; }
    const { block, next } = readBlock(lines, i, ctx);
    blocks.push(block);
    i = next;
  }
  return blocks;
}

export function parseMarkdown(src: string): Block[] {
  return parseLines(src.replace(/\r\n?/g, '\n').split('\n'), makeCtx());
}
