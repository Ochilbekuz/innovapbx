/**
 * Sinov/demo uchun ohang: 8 kHz mono 16-bit PCM WAV (Asterisk formati bilan bir xil).
 * Fake API audio kutubxonasi shu bilan «tinglanadi» — tashqi ovoz fayllari kerak emas.
 */
const RATE = 8000;

export function toneWav(durationMs: number, hz = 440): Blob {
  const samples = Math.round((RATE * durationMs) / 1000);
  const view = new DataView(new ArrayBuffer(44 + samples * 2));
  const text = (at: number, s: string) => [...s].forEach((c, i) => view.setUint8(at + i, c.charCodeAt(0)));
  text(0, 'RIFF');
  view.setUint32(4, 36 + samples * 2, true);
  text(8, 'WAVE');
  text(12, 'fmt ');
  view.setUint32(16, 16, true); // fmt bo'lagi hajmi
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, RATE, true);
  view.setUint32(28, RATE * 2, true); // bayt/soniya
  view.setUint16(32, 2, true); // blok
  view.setUint16(34, 16, true); // bit
  text(36, 'data');
  view.setUint32(40, samples * 2, true);
  for (let i = 0; i < samples; i++) {
    view.setInt16(44 + i * 2, Math.round(Math.sin((2 * Math.PI * hz * i) / RATE) * 8000), true);
  }
  return new Blob([view.buffer], { type: 'audio/wav' });
}
