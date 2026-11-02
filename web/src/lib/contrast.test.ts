import { describe, expect, it } from 'vitest';
import { contrast } from './contrast';

describe('contrast', () => {
  it('contrast.py bilan bir xil natija', () => {
    expect(contrast('#FFFFFF', '#000000')).toBeCloseTo(21, 5);
    expect(contrast('#D7621D', '#FFFFFF')).toBeCloseTo(3.71, 2);
    expect(contrast('#FFFFFF', '#AB4C17')).toBeGreaterThanOrEqual(4.5);
  });
});
