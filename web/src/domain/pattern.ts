// Asterisk terish naqshi (dial pattern): tahlil, moslash, marshrut qo'llash. Sof funksiyalar.
// Grammatika: 0-9 * # — aniq belgi; X=0-9, Z=1-9, N=2-9; [15-7] — sinf;
// '.' — kamida bitta istalgan belgi, '!' — nol yoki ko'p; ikkalasi faqat oxirida.

export type PatternToken =
  | { t: 'lit'; ch: string }
  | { t: 'set'; chars: string }
  | { t: 'tail'; min: 0 | 1 };

export type PatternErrorCode =
  | 'empty'
  | 'bad-char'
  | 'unclosed-class'
  | 'empty-class'
  | 'bad-range'
  | 'wildcard-not-last';

export type PatternError = { code: PatternErrorCode; at: number };

export type ParsedPattern =
  | { ok: true; normalized: string; tokens: PatternToken[]; minLength: number; maxLength: number | null }
  | { ok: false; error: PatternError };

const DIGITS = '0123456789';
const CLASS: Record<string, string> = { X: DIGITS, Z: DIGITS.slice(1), N: DIGITS.slice(2) };
const LITERAL = /[0-9*#+]/;

type Step = { token: PatternToken; next: number } | { error: PatternError };

function readClass(src: string, start: number): Step {
  const close = src.indexOf(']', start);
  if (close < 0) return { error: { code: 'unclosed-class', at: start } };
  const body = src.slice(start + 1, close);
  if (body.length === 0) return { error: { code: 'empty-class', at: start } };
  let chars = '';
  for (let i = 0; i < body.length; i++) {
    const c = body[i] as string;
    const at = start + 1 + i;
    if (!DIGITS.includes(c)) return { error: { code: 'bad-char', at } };
    if (body[i + 1] === '-') {
      const end = body[i + 2];
      if (end === undefined || !DIGITS.includes(end)) return { error: { code: 'bad-char', at: at + 1 } };
      if (end < c) return { error: { code: 'bad-range', at } };
      chars += DIGITS.slice(Number(c), Number(end) + 1);
      i += 2;
    } else {
      chars += c;
    }
  }
  return { token: { t: 'set', chars }, next: close + 1 };
}

function readToken(src: string, i: number): Step {
  const c = src[i] as string;
  if (c === '[') return readClass(src, i);
  if (c === '.' || c === '!') {
    if (i !== src.length - 1) return { error: { code: 'wildcard-not-last', at: i } };
    return { token: { t: 'tail', min: c === '.' ? 1 : 0 }, next: i + 1 };
  }
  const cls = CLASS[c];
  if (cls) return { token: { t: 'set', chars: cls }, next: i + 1 };
  if (LITERAL.test(c)) return { token: { t: 'lit', ch: c }, next: i + 1 };
  return { error: { code: 'bad-char', at: i } };
}

export function parsePattern(input: string): ParsedPattern {
  const trimmed = input.trim();
  const body = (trimmed.startsWith('_') ? trimmed.slice(1) : trimmed).toUpperCase();
  if (body.length === 0) return { ok: false, error: { code: 'empty', at: 0 } };
  const offset = trimmed.length - body.length;
  const tokens: PatternToken[] = [];
  let i = 0;
  while (i < body.length) {
    const step = readToken(body, i);
    if ('error' in step) return { ok: false, error: { ...step.error, at: step.error.at + offset } };
    tokens.push(step.token);
    i = step.next;
  }
  const fixed = tokens.filter((t) => t.t !== 'tail').length;
  const tail = tokens.find((t): t is Extract<PatternToken, { t: 'tail' }> => t.t === 'tail');
  return {
    ok: true,
    normalized: body,
    tokens,
    minLength: fixed + (tail?.min ?? 0),
    maxLength: tail ? null : fixed,
  };
}

function tokenAccepts(token: PatternToken, ch: string): boolean {
  return token.t === 'lit' ? token.ch === ch : token.t === 'set' ? token.chars.includes(ch) : true;
}

export function matchPattern(pattern: string, number: string): boolean {
  const parsed = parsePattern(pattern);
  if (!parsed.ok) return false;
  const { tokens, minLength, maxLength } = parsed;
  if (number.length < minLength || (maxLength !== null && number.length > maxLength)) return false;
  return tokens.every((tok, i) => tok.t === 'tail' || tokenAccepts(tok, number[i] ?? ''));
}

export type RouteRule = { prepend: string; prefix: string; pattern: string };
export type RouteResult = { matched: false } | { matched: true; dialed: string };

/** Chiquvchi marshrut qoidasi: prefiks mos kelsa kesiladi, qolgani naqshga tekshiriladi, oldiga prepend qo'shiladi. */
export function applyRoute(rule: RouteRule, number: string): RouteResult {
  if (!number.startsWith(rule.prefix)) return { matched: false };
  const rest = number.slice(rule.prefix.length);
  if (!matchPattern(rule.pattern, rest)) return { matched: false };
  return { matched: true, dialed: rule.prepend + rest };
}

/** Naqshning tilsiz tavsifi — matnga UI qatlami (`pbx/domainText.ts`, i18n) aylantiradi. */
export type PatternDescription =
  | { ok: false; code: PatternErrorCode }
  | { ok: true; minLength: number; open: boolean; prefix: string };

export function describePattern(p: ParsedPattern): PatternDescription {
  if (!p.ok) return { ok: false, code: p.error.code };
  const lead = p.tokens.findIndex((t) => t.t !== 'lit');
  const prefix = p.tokens.slice(0, lead < 0 ? undefined : lead).map((t) => (t.t === 'lit' ? t.ch : '')).join('');
  return { ok: true, minLength: p.minLength, open: p.maxLength === null, prefix };
}
