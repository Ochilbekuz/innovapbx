// Qattiq yozilgan (hardcoded) matnni topish uchun yengil skaner — to'liq AST emas, satr bo'yicha
// heuristika: JSX matn tugunlari (`>matn<`) va placeholder/aria-label/title atributlari.
// `i18nScanner.test.ts` va `src/screens/**/*.scan.test.ts` shu modulni ishlatadi.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

export type ScanHit = { line: number; kind: 'text' | 'attr'; snippet: string };

const ATTR_RE = /(?:placeholder|aria-label|title)=(?:"([^"]+)"|'([^']+)'|\{`([^`]*)`\})/g;
const TEXT_RE = />([^<>{}\n]{2,})</g;
const HAS_LETTER = /[A-Za-zÀ-ÖØ-öø-ÿʻʼʽЀ-ӿ]/;

function isNoise(raw: string): boolean {
  const s = raw.trim();
  if (s.length === 0) return true;
  if (!HAS_LETTER.test(s)) return true;
  return false;
}

/** Bitta fayl matnini skanerlab, qattiq yozilgan matn nomzodlarini qaytaradi. */
export function scanSource(content: string): ScanHit[] {
  const hits: ScanHit[] = [];
  content.split('\n').forEach((lineText, idx) => {
    for (const m of lineText.matchAll(ATTR_RE)) {
      const value = m[1] ?? m[2] ?? m[3] ?? '';
      if (!isNoise(value)) hits.push({ line: idx + 1, kind: 'attr', snippet: value.trim() });
    }
    for (const m of lineText.matchAll(TEXT_RE)) {
      const text = m[1] ?? '';
      // `a >= 1 && b <= 2` — JSX matn emas, taqqoslash operatorlari.
      if (text.startsWith('=')) continue;
      if (!isNoise(text)) hits.push({ line: idx + 1, kind: 'text', snippet: text.trim() });
    }
  });
  return hits;
}

/** Katalogni rekursiv aylanib, berilgan kengaytmali fayllarni qaytaradi (exclude — regex ro'yxati). */
export function listFiles(dir: string, ext: string, exclude: RegExp[] = []): string[] {
  const out: string[] = [];
  const walk = (d: string) => {
    for (const entry of readdirSync(d)) {
      const full = join(d, entry);
      const st = statSync(full);
      if (st.isDirectory()) { walk(full); continue; }
      if (!full.endsWith(ext)) continue;
      if (exclude.some((re) => re.test(full))) continue;
      out.push(full);
    }
  };
  walk(dir);
  return out;
}

export function scanFile(path: string): ScanHit[] {
  return scanSource(readFileSync(path, 'utf-8'));
}
