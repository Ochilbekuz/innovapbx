// Yuqori paneldagi jonli soat: tizim (tenant) zonasida har soniya yangilanadi, zona siljishi yonida.
import { describe, expect, it, afterEach, beforeEach, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import { useSession } from '@/api/session';
import type { User } from '@/api/types';
import { LiveClock } from './LiveClock';

const withZone = (timezone: string) => useSession.setState({ user: { timezone } as User });

describe('LiveClock', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-11-05T09:03:21Z'));
  });
  afterEach(() => {
    vi.useRealTimers();
    useSession.getState().clear();
  });

  it('tizim zonasidagi joriy vaqtni soniyalari bilan va zona siljishini koʻrsatadi', () => {
    withZone('Asia/Tashkent');
    render(<LiveClock />);

    const clock = screen.getByRole('timer');
    expect(clock).toHaveTextContent('14:03:21');
    expect(clock).toHaveTextContent('05.11.2026');
    expect(screen.getByText('UTC+5')).toBeTruthy();
    expect(clock).toHaveAttribute('title', 'Asia/Tashkent');
  });

  it('har soniyada yangilanadi', () => {
    withZone('Asia/Tashkent');
    render(<LiveClock />);

    act(() => { vi.advanceTimersByTime(1000); });
    expect(screen.getByRole('timer')).toHaveTextContent('14:03:22');
  });

  it('zona oʻzgarsa — soat yangi zonaga oʻtadi', () => {
    withZone('Europe/Moscow');
    render(<LiveClock />);

    expect(screen.getByRole('timer')).toHaveTextContent('12:03:21');
    expect(screen.getByText('UTC+3')).toBeTruthy();
  });

  it('unmount boʻlganda taymer toʻxtaydi', () => {
    withZone('Asia/Tashkent');
    const { unmount } = render(<LiveClock />);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});
