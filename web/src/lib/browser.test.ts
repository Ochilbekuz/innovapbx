import { afterEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { copyText, newId } from './browser';
import { listFiles } from './i18nScanner';

// Panel odatda http://<LAN-IP>/ da ochiladi — bu «secure context» emas: crypto.randomUUID va
// navigator.clipboard YO'Q (2026-11-02: /outbound «Yangi marshrut» bo'sh sahifa berdi).

afterEach(() => vi.unstubAllGlobals());

describe('newId: insecure context (http://LAN-IP)', () => {
  it('works without crypto.randomUUID and gives unique uuid-shaped ids', () => {
    vi.stubGlobal('crypto', { getRandomValues: crypto.getRandomValues.bind(crypto) });
    const ids = new Set(Array.from({ length: 200 }, () => newId()));
    expect(ids.size).toBe(200);
    for (const id of ids) expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  });
});

describe('copyText', () => {
  it('uses the Clipboard API when it exists', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { clipboard: { writeText } });
    await expect(copyText('abc')).resolves.toBe(true);
    expect(writeText).toHaveBeenCalledWith('abc');
  });

  it('falls back to a hidden textarea + execCommand without Clipboard API', async () => {
    vi.stubGlobal('navigator', {});
    let copied = '';
    const exec = vi.fn(() => { copied = document.querySelector('textarea')?.value ?? ''; return true; });
    Object.defineProperty(document, 'execCommand', { value: exec, configurable: true });
    await expect(copyText('sip-secret')).resolves.toBe(true);
    expect(exec).toHaveBeenCalledWith('copy');
    expect(copied).toBe('sip-secret');
    expect(document.querySelector('textarea')).toBeNull(); // vaqtinchalik element olib tashlangan
  });

  it('reports failure instead of throwing when nothing can copy', async () => {
    vi.stubGlobal('navigator', {});
    Object.defineProperty(document, 'execCommand', { value: () => false, configurable: true });
    await expect(copyText('x')).resolves.toBe(false);
  });
});

describe('secure-context-only APIs are used only through lib/browser', () => {
  it('no direct crypto.randomUUID / navigator.clipboard elsewhere in src', () => {
    const SRC = join(dirname(fileURLToPath(import.meta.url)), '..');
    const offenders = [...listFiles(SRC, '.ts'), ...listFiles(SRC, '.tsx')]
      .filter((f) => !/\.test\.tsx?$/.test(f) && !f.endsWith(join('lib', 'browser.ts')))
      .filter((f) => /crypto\.randomUUID|navigator\.clipboard/.test(readFileSync(f, 'utf8')))
      .map((f) => relative(SRC, f));
    expect(offenders).toEqual([]);
  });
});
