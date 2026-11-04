// Toast: hammasi o'zi yopiladi va bir xil xabar ustma-ust qalanmaydi (foydalanuvchi talabi, 2026-11-04).
import { describe, expect, it, vi, afterEach } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import { DURATION, pushToast, ToastProvider, useToast, type ToastInput } from './Toast';

const busy: ToastInput = { kind: 'error', title: 'Boshqa yangilanish amali hali ketmoqda' };

describe('pushToast', () => {
  it('bir xil tur+sarlavha — eskisi almashtiriladi, nusxa qoʻshilmaydi', () => {
    const one = pushToast([], busy, 1);
    const two = pushToast(one, busy, 2);
    expect(two).toEqual([{ ...busy, id: 2 }]);
  });
  it('turli xabarlar — koʻpi bilan 4 tasi turadi, eng eskisi tushadi', () => {
    let xs = pushToast([], { kind: 'info', title: 'a' }, 1);
    for (const [i, title] of ['b', 'c', 'd', 'e'].entries()) xs = pushToast(xs, { kind: 'info', title }, i + 2);
    expect(xs.map((x) => x.title)).toEqual(['b', 'c', 'd', 'e']);
  });
  it('sarlavha bir xil, tur boshqa — ikkalasi qoladi', () => {
    const xs = pushToast(pushToast([], { kind: 'success', title: 'x' }, 1), { kind: 'error', title: 'x' }, 2);
    expect(xs).toHaveLength(2);
  });
});

describe('DURATION', () => {
  it('hech qaysi tur cheksiz emas; xato muvaffaqiyatdan uzoqroq turadi', () => {
    for (const ms of Object.values(DURATION)) expect(Number.isFinite(ms)).toBe(true);
    expect(DURATION.error).toBeGreaterThan(DURATION.success);
  });
});

function Pusher({ toast }: { toast: ToastInput }) {
  const push = useToast();
  return <button onClick={() => push(toast)}>push</button>;
}

describe('ToastProvider', () => {
  afterEach(() => vi.useRealTimers());

  it('xato xabari 3 marta bosilsa ham bitta koʻrinadi va vaqti tugagach yopiladi', async () => {
    vi.useFakeTimers();
    render(<ToastProvider><Pusher toast={busy} /></ToastProvider>);
    const btn = screen.getByRole('button', { name: 'push' });
    act(() => { btn.click(); btn.click(); btn.click(); });
    expect(screen.getAllByText(busy.title)).toHaveLength(1);

    await act(async () => { vi.advanceTimersByTime(DURATION.error + 1000); });
    expect(screen.queryByText(busy.title)).toBeNull();
  });
});
