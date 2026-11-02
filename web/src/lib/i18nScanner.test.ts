import { describe, expect, it } from 'vitest';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { listFiles, scanFile, scanSource } from './i18nScanner';

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC = join(HERE, '..'); // .../web/src

describe('i18nScanner: catches a deliberately bad example', () => {
  it('flags hardcoded Uzbek text in a JSX text node', () => {
    const bad = "export const Bad = () => <p>Hali audio fayl yoʻq</p>;";
    const hits = scanSource(bad);
    expect(hits).toHaveLength(1);
    expect(hits[0]).toMatchObject({ kind: 'text', snippet: 'Hali audio fayl yoʻq' });
  });

  it('flags hardcoded text in placeholder/aria-label/title attributes', () => {
    const bad = '<input placeholder="Nomi (ixtiyoriy)" aria-label="Yozuv nomi" title="Band etilgan" />';
    const hits = scanSource(bad);
    expect(hits.filter((h) => h.kind === 'attr')).toHaveLength(3);
  });

  it('flags hardcoded text mixed into a template-literal attribute', () => {
    const bad = "<button aria-label={`${r.name}ni oʻchirish`} />";
    const hits = scanSource(bad);
    expect(hits.some((h) => h.kind === 'attr' && h.snippet.includes('oʻchirish'))).toBe(true);
  });
});

describe('i18nScanner: does not false-positive on translated code', () => {
  it('ignores JSX text that is purely a t() call', () => {
    expect(scanSource("export const Good = () => <p>{t('title')}</p>;")).toHaveLength(0);
  });

  it('ignores symbols, numbers, and pure-expression children', () => {
    const good = '<span>—</span><Badge>{count}</Badge><em>12</em>';
    expect(scanSource(good)).toHaveLength(0);
  });

  it('ignores comparison operators in plain TS (>= … <=)', () => {
    expect(scanSource('const ok = portNum >= 1 && portNum <= 65535;')).toHaveLength(0);
  });

  it('ignores attributes bound to variables or t() calls', () => {
    const good = "<input aria-label={t('form.nameLabel')} placeholder={placeholderText} />";
    expect(scanSource(good)).toHaveLength(0);
  });
});

describe('i18nScanner: real scan over screens/shell/ui/pbx', () => {
  const EXCLUDE = [/[/\\]design[/\\]/, /\.test\.tsx?$/];
  const DIRS = ['screens', 'shell', 'ui', 'pbx'];
  const allFiles = DIRS.flatMap((d) => listFiles(join(SRC, d), '.tsx', EXCLUDE));

  // M1c i18n ko'chirishi bosqichma-bosqich davom etmoqda (replica/m1c-contract.md §4).
  // Quyidagi naqshlarga mos fayllar hali to'liq ko'chirilmagan — asl o'zbekcha matn saqlanib
  // qolgan. Bu ro'yxat ekranlar ko'chirilgan sari qisqarib boradi; hozircha ular uchun skaner
  // faqat hisoblaydi (pastdagi "informational" testda), testni qulatmaydi. Yangi/ko'chirilgan
  // kodda qattiq yozilgan matn paydo bo'lishini ushbu test shart ko'radi (quyidagi "migrated" test).
  const PENDING: RegExp[] = [];
  const isPending = (f: string) => PENDING.some((re) => re.test(f));

  const migrated = allFiles.filter((f) => !isPending(f));
  const pending = allFiles.filter((f) => isPending(f));

  it('scans a non-trivial number of files', () => {
    expect(allFiles.length).toBeGreaterThan(10);
    expect(migrated.length).toBeGreaterThan(0);
  });

  it.each(migrated.map((f) => relative(SRC, f)))('%s has no hardcoded text (migrated)', (rel) => {
    const hits = scanFile(join(SRC, rel));
    expect(hits, JSON.stringify(hits)).toHaveLength(0);
  });

  it('reports remaining pending files without failing the suite (informational)', () => {
    const total = pending.reduce((n, f) => n + scanFile(f).length, 0);
    expect(total).toBeGreaterThanOrEqual(0);
  });
});
