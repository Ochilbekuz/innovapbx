import { describe, expect, it } from 'vitest';
import { toneWav } from './wav';

const ascii = (b: Uint8Array, at: number) => String.fromCharCode(...b.slice(at, at + 4));

describe('toneWav', () => {
  it('8 kHz mono 16-bit PCM WAV yasaydi — sarlavha va hajm toʻgʻri', async () => {
    const bytes = new Uint8Array(await toneWav(500).arrayBuffer());
    const view = new DataView(bytes.buffer);
    const samples = 8000 * 0.5;

    expect(ascii(bytes, 0)).toBe('RIFF');
    expect(ascii(bytes, 8)).toBe('WAVE');
    expect(ascii(bytes, 36)).toBe('data');
    expect(view.getUint16(22, true)).toBe(1); // mono
    expect(view.getUint32(24, true)).toBe(8000);
    expect(view.getUint16(34, true)).toBe(16);
    expect(view.getUint32(40, true)).toBe(samples * 2);
    expect(view.getUint32(4, true)).toBe(36 + samples * 2);
    expect(bytes.length).toBe(44 + samples * 2);
  });

  it('sukut emas — namunalarda signal bor', async () => {
    const view = new DataView(await toneWav(100).arrayBuffer());
    const peak = Math.max(...Array.from({ length: 800 }, (_, i) => Math.abs(view.getInt16(44 + i * 2, true))));
    expect(peak).toBeGreaterThan(1000);
  });
});
