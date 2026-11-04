// Sof mantiq — Paneldan yangilash (M11, ../../replica/m11-update-contract.md §5). `src/api/fake.ts`
// (simulyatsiya) va `src/screens/update/*` shu yerdan foydalanadi — qoida bitta joyda yashaydi (dryer).
import type { SystemUpdateOut, UpdateState } from '@/api/types';

// ─────────────────────── Polling (§5: checking/updating yoki pending bo'lsa 2s) ───────────────────────

type PollableState = Pick<SystemUpdateOut, 'state' | 'pending'> | undefined;

/** Asosiy holat (`GET /system/update`) qancha tez-tez so'ralsin — aks holda `false` (polling yo'q). */
export function updateStatePollMs(data: PollableState): number | false {
  if (!data) return false;
  if (data.state === 'checking' || data.state === 'updating') return 2000;
  return data.pending ? 2000 : false;
}

/** Jurnal faqat `updating` paytida tez-tez so'raladi — `done`/`failed`da bir martalik yakuniy o'qish yetarli. */
export function updateLogPollMs(state: UpdateState | undefined): number | false {
  return state === 'updating' ? 2000 : false;
}

/** Jurnal bo'limi qachon ko'rsatilsin — jarayon davomida va yakunlangandan keyin (ko'rib chiqish uchun). */
export function shouldShowUpdateLog(state: UpdateState | undefined): boolean {
  return state === 'updating' || state === 'done' || state === 'failed';
}

/** API 502/503 yoki tarmoq xatosi (status yo'q) — oxirgi ma'lum holat `updating` bo'lsa bu xato emas,
 * "tizim qayta ishga tushmoqda" (shartnoma §5). Boshqa holatlarda (idle/checking/done/failed) — haqiqiy xato. */
export function isRestartingDuringUpdate(lastState: UpdateState | undefined, errorStatus: number | null): boolean {
  if (lastState !== 'updating') return false;
  return errorStatus === null || errorStatus === 502 || errorStatus === 503;
}

// ─────────────────────── Jurnal (log?offset) — o'sib boradigan matn ───────────────────────

export type UpdateLogAccum = { text: string; offset: number };
export const EMPTY_LOG: UpdateLogAccum = { text: '', offset: 0 };

/**
 * Yangi parchani qo'shadi. `response.offset` oldingi saqlangan `offset`dan KICHIK bo'lsa — jurnal
 * qayta yaratilgan (server 0'dan qaytargan, shartnoma §4) — eski matn tashlanib, yangisidan boshlanadi.
 */
export function appendUpdateLog(prev: UpdateLogAccum, response: { offset: number; text: string }): UpdateLogAccum {
  if (response.offset < prev.offset) return { text: response.text, offset: response.offset };
  if (!response.text) return prev;
  return { text: prev.text + response.text, offset: response.offset };
}

// ─────────────────────── Bosqichlar (zaxira → kod → o'rnatish → qayta ishga tushish) ───────────────────────

export type DisplayPhase = 'backup' | 'code' | 'install' | 'restart';
export const UPDATE_PHASES: readonly DisplayPhase[] = ['backup', 'code', 'install', 'restart'];

/** Joriy bosqichga nisbatan berilgan bosqich holati — stepper UI uchun. */
export function phaseStatus(phase: DisplayPhase, current: DisplayPhase | null): 'done' | 'current' | 'pending' {
  if (!current) return 'pending';
  const ci = UPDATE_PHASES.indexOf(current);
  const pi = UPDATE_PHASES.indexOf(phase);
  if (pi < ci) return 'done';
  return pi === ci ? 'current' : 'pending';
}

// ─────────────────────── Changelog markdown — xavfsiz (HTML yo'q) mini-renderer uchun sof qism ───────────────────────

export type MdBlock = { type: 'heading'; level: 2 | 3; text: string } | { type: 'list'; items: string[] } | { type: 'paragraph'; text: string };

function flushBuffer<T extends MdBlock>(buf: string[], make: (items: string[]) => T, out: MdBlock[]): string[] {
  if (buf.length) out.push(make(buf));
  return [];
}

type ClassifiedLine =
  | { kind: 'heading'; level: 2 | 3; text: string }
  | { kind: 'list'; text: string }
  | { kind: 'blank' }
  | { kind: 'text'; text: string };

/** Bitta qatorni turkumlaydi (sarlavha/roʻyxat/boʻsh/matn) — `parseMarkdownLite`dan CC ni ajratish uchun. */
export function classifyMdLine(raw: string): ClassifiedLine {
  const line = raw.trim();
  const heading = /^(#{2,3})\s+(.*)$/.exec(line);
  if (heading) return { kind: 'heading', level: heading[1]!.length === 2 ? 2 : 3, text: heading[2] ?? '' };
  const listItem = /^[-*]\s+(.*)$/.exec(line);
  if (listItem) return { kind: 'list', text: listItem[1] ?? '' };
  if (line === '') return { kind: 'blank' };
  return { kind: 'text', text: line };
}

/** Markdown satrlarini sarlavha/ro'yxat/paragraf bloklariga ajratadi — HTML teglari oddiy matn sifatida qoladi. */
export function parseMarkdownLite(md: string): MdBlock[] {
  const blocks: MdBlock[] = [];
  let listBuf: string[] = [];
  let paraBuf: string[] = [];
  const flush = () => {
    listBuf = flushBuffer(listBuf, (items) => ({ type: 'list', items }), blocks);
    paraBuf = flushBuffer(paraBuf, (items) => ({ type: 'paragraph', text: items.join(' ') }), blocks);
  };
  for (const raw of md.replace(/\r\n/g, '\n').split('\n')) {
    const c = classifyMdLine(raw);
    if (c.kind === 'heading') {
      flush();
      blocks.push({ type: 'heading', level: c.level, text: c.text });
    } else if (c.kind === 'list') {
      paraBuf = flushBuffer(paraBuf, (items) => ({ type: 'paragraph', text: items.join(' ') }), blocks);
      listBuf.push(c.text);
    } else if (c.kind === 'blank') {
      flush();
    } else {
      listBuf = flushBuffer(listBuf, (items) => ({ type: 'list', items }), blocks);
      paraBuf.push(c.text);
    }
  }
  flush();
  return blocks;
}

// ─────────────────────── Jurnal avto-skroll (qoʻlda yuqoriga aylantirilsa toʻxtaydi) ───────────────────────

type ScrollBox = { scrollHeight: number; scrollTop: number; clientHeight: number };

/** Foydalanuvchi oxiridan 24px dan koʻproq yuqoriga aylantirdimi — avto-skrollni toʻxtatish mezoni. */
export function isScrolledAwayFromEnd(el: ScrollBox | null): boolean {
  if (!el) return false;
  return el.scrollHeight - el.scrollTop - el.clientHeight > 24;
}

/** `el`ni (mavjud bo'lsa) pastga aylantiradi. */
export function scrollToEnd(el: Pick<ScrollBox, 'scrollTop' | 'scrollHeight'> | null): void {
  if (el) el.scrollTop = el.scrollHeight;
}

export type InlineToken = { type: 'text' | 'bold' | 'code'; value: string };
const INLINE_RE = /(\*\*[^*]+\*\*|`[^`]+`)/g;

/** `**qalin**` va `` `kod` `` ni ajratadi — qolgani oddiy matn (hech qanday HTML parse qilinmaydi). */
export function tokenizeInline(text: string): InlineToken[] {
  const tokens: InlineToken[] = [];
  let lastIndex = 0;
  for (const m of text.matchAll(INLINE_RE)) {
    const idx = m.index ?? 0;
    if (idx > lastIndex) tokens.push({ type: 'text', value: text.slice(lastIndex, idx) });
    const chunk = m[0];
    tokens.push(chunk.startsWith('**') ? { type: 'bold', value: chunk.slice(2, -2) } : { type: 'code', value: chunk.slice(1, -1) });
    lastIndex = idx + chunk.length;
  }
  if (lastIndex < text.length) tokens.push({ type: 'text', value: text.slice(lastIndex) });
  return tokens;
}
