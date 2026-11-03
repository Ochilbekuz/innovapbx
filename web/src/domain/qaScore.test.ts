import { describe, expect, it } from 'vitest';
import { computeScorePct, isComplete, type QaCriterionLike } from './qaScore';

const criteria: QaCriterionLike[] = [
  { id: 'c1', kind: 'yesno', weight: 2, critical: false },
  { id: 'c2', kind: 'scale5', weight: 1, critical: false },
];

describe('qaScore', () => {
  it('computes 100% when all answers are maximal', () => {
    expect(computeScorePct(criteria, { c1: true, c2: 5 })).toBe(100);
  });

  it('computes 0% when all answers are minimal', () => {
    expect(computeScorePct(criteria, { c1: false, c2: 1 })).toBe(0);
  });

  it('weights yesno(yes)+scale5(mid) correctly', () => {
    // c1: 1*2=2; c2: (3-1)/4=0.5*1=0.5 -> sum=2.5 / weight=3 -> 83.33%
    expect(computeScorePct(criteria, { c1: true, c2: 3 })).toBe(83.33);
  });

  it('forces 0 when a critical criterion fails, regardless of others', () => {
    const withCritical: QaCriterionLike[] = [
      { id: 'c1', kind: 'yesno', weight: 1, critical: true },
      { id: 'c2', kind: 'scale5', weight: 5, critical: false },
    ];
    expect(computeScorePct(withCritical, { c1: false, c2: 5 })).toBe(0);
  });

  it('forces 0 when a critical scale5 criterion is below max (5), not only at minimum', () => {
    // Backend qoidasi: critical scale5 uchun faqat 5 "muvaffaqiyatli" — 4 ham fail.
    const withCritical: QaCriterionLike[] = [{ id: 'c1', kind: 'scale5', weight: 1, critical: true }];
    expect(computeScorePct(withCritical, { c1: 4 })).toBe(0);
  });

  it('treats a missing answer as 0 contribution but still counts its weight in the denominator', () => {
    // c1 javobsiz -> ulushi 0, lekin og'irligi (2) maxrajga qo'shiladi: 0 / 3 -> faqat c2 (5) ulushi hisoblanadi.
    // c2: (5-1)/4=1*1=1 -> 1 / 3 -> 33.33%
    expect(computeScorePct(criteria, { c2: 5 })).toBe(33.33);
  });

  it('forces 0 when a critical criterion has no answer at all', () => {
    const withCritical: QaCriterionLike[] = [
      { id: 'c1', kind: 'yesno', weight: 1, critical: true },
      { id: 'c2', kind: 'scale5', weight: 5, critical: false },
    ];
    expect(computeScorePct(withCritical, { c2: 5 })).toBe(0);
  });

  it('reports completeness based on criteria vs answers', () => {
    expect(isComplete(criteria, { c1: true })).toBe(false);
    expect(isComplete(criteria, { c1: true, c2: 2 })).toBe(true);
  });
});
