import { describe, expect, it } from 'vitest';
import { diskLevel, trunkHealthLevel } from './health';

describe('diskLevel', () => {
  it('95%+ — kritik', () => { expect(diskLevel(95)).toBe('crit'); expect(diskLevel(99)).toBe('crit'); });
  it('85–94% — ogohlantirish', () => { expect(diskLevel(85)).toBe('warn'); expect(diskLevel(94)).toBe('warn'); });
  it('84% va kam — ok', () => { expect(diskLevel(84)).toBe('ok'); expect(diskLevel(0)).toBe('ok'); });
});

describe('trunkHealthLevel', () => {
  it('ok → ok', () => { expect(trunkHealthLevel('ok')).toBe('ok'); });
  it('unreachable → crit', () => { expect(trunkHealthLevel('unreachable')).toBe('crit'); });
  it('unknown/disabled → warn', () => { expect(trunkHealthLevel('unknown')).toBe('warn'); expect(trunkHealthLevel('disabled')).toBe('warn'); });
});
