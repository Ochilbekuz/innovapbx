import { describe, expect, it } from 'vitest';
import { slaLevel } from './sla';

describe('sla — slaLevel', () => {
  it('null — unknown', () => {
    expect(slaLevel(null)).toBe('unknown');
  });

  it('>= 80 — good', () => {
    expect(slaLevel(80)).toBe('good');
    expect(slaLevel(95.5)).toBe('good');
  });

  it('50..79.9 — warn', () => {
    expect(slaLevel(50)).toBe('warn');
    expect(slaLevel(79.9)).toBe('warn');
  });

  it('< 50 — bad', () => {
    expect(slaLevel(0)).toBe('bad');
    expect(slaLevel(49.9)).toBe('bad');
  });
});
