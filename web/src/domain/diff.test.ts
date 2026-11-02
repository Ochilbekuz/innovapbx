import { describe, expect, it } from 'vitest';
import { unifiedDiff } from './diff';

describe('unifiedDiff', () => {
  it('bir xil matnda faqat kontekst qatorlar beradi', () => {
    const d = unifiedDiff('a\nb\nc', 'a\nb\nc', 'r1', 'r2');
    expect(d).toContain('--- r1');
    expect(d).toContain('+++ r2');
    const body = d.split('\n').slice(2).join('\n');
    expect(body).not.toMatch(/^[-+]/m);
  });

  it("o'zgargan qatorni -/+ bilan ko'rsatadi", () => {
    const d = unifiedDiff('salom\nikkinchi', 'xayr\nikkinchi', 'r1', 'r2');
    expect(d).toContain('-salom');
    expect(d).toContain('+xayr');
    expect(d).toContain(' ikkinchi');
  });

  it('qo‘shilgan qatorni + bilan ko‘rsatadi', () => {
    const d = unifiedDiff('a', 'a\nb', 'r1', 'r2');
    expect(d).toContain(' a');
    expect(d).toContain('+b');
  });
});
