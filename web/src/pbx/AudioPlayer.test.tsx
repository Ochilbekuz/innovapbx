import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AudioPlayer } from './AudioPlayer';

const ERROR_TEXT = /Fayl topilmadi/;

describe('AudioPlayer — token bilan olinadigan fayl', () => {
  beforeEach(() => {
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:sinov'), revokeObjectURL: vi.fn() }));
    vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined);
  });
  afterEach(() => vi.restoreAllMocks());

  it('bosilmaguncha faylni yuklamaydi va xato koʻrsatmaydi', () => {
    const load = vi.fn(async () => new Blob(['RIFF']));
    render(<AudioPlayer src={load} variant="inline" />);
    expect(load).not.toHaveBeenCalled();
    expect(screen.queryByText(ERROR_TEXT)).toBeNull();
    expect(screen.getByRole('button', { name: 'Tinglash' })).toBeEnabled();
  });

  it('«Tinglash» bosilganda faylni bir marta oladi va blob manzilidan ijro etadi', async () => {
    const load = vi.fn(async () => new Blob(['RIFF']));
    const { container } = render(<AudioPlayer src={load} variant="inline" />);
    await userEvent.click(screen.getByRole('button', { name: 'Tinglash' }));
    expect(load).toHaveBeenCalledTimes(1);
    expect(container.querySelector('audio')).toHaveAttribute('src', 'blob:sinov');
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalled();
  });

  it('fayl olinmasa (401/404) — xato matni chiqadi va tugma oʻchadi', async () => {
    const load = vi.fn(async () => { throw new Error('404'); });
    render(<AudioPlayer src={load} variant="inline" />);
    await userEvent.click(screen.getByRole('button', { name: 'Tinglash' }));
    expect(await screen.findByText(ERROR_TEXT)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Faylni ijro etib boʻlmaydi' })).toBeDisabled();
  });
});

describe('AudioPlayer — boshqaruv', () => {
  const withDuration = (container: HTMLElement, seconds: number) => {
    const a = container.querySelector('audio')!;
    Object.defineProperty(a, 'duration', { configurable: true, value: seconds });
    fireEvent.loadedMetadata(a);
    return a;
  };

  it('manba yoʻq — xato matni va oʻchiq tugma, tezlik/yuklab olish yoʻq', () => {
    render(<AudioPlayer src={null} title="Eski" />);
    expect(screen.getByText(ERROR_TEXT)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Faylni ijro etib boʻlmaydi' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: /Tezlik/ })).toBeNull();
  });

  it('klaviatura: → 5 s, Shift+→ 15 s, ← orqaga, Home/End chegaralar', () => {
    const { container } = render(<AudioPlayer src="/a.wav" title="Salom" />);
    const a = withDuration(container, 60);
    const slider = screen.getByRole('slider', { name: 'Salom: oʻrin' });
    expect(slider).toHaveAttribute('aria-valuemax', '60');
    fireEvent.keyDown(slider, { key: 'ArrowRight' });
    expect(a.currentTime).toBe(5);
    fireEvent.timeUpdate(a);
    fireEvent.keyDown(slider, { key: 'ArrowRight', shiftKey: true });
    expect(a.currentTime).toBe(20);
    fireEvent.timeUpdate(a);
    fireEvent.keyDown(slider, { key: 'ArrowLeft' });
    expect(a.currentTime).toBe(15);
    fireEvent.keyDown(slider, { key: 'End' });
    expect(a.currentTime).toBe(60);
    fireEvent.keyDown(slider, { key: 'Home' });
    expect(a.currentTime).toBe(0);
  });

  it('tezlik tugmasi 1× → 1.5× → 2× → 1× aylanadi; ochiq manzilda yuklab olish havolasi bor', async () => {
    const { container } = render(<AudioPlayer src="/a.wav" title="Salom" />);
    const a = container.querySelector('audio')!;
    for (const want of [1.5, 2, 1]) {
      await userEvent.click(screen.getByRole('button', { name: /Tezlik/ }));
      expect(a.playbackRate).toBe(want);
    }
    expect(screen.getByRole('link', { name: 'Yuklab olish' })).toHaveAttribute('href', '/a.wav');
  });

  it('full: sarlavha va meta koʻrinadi; inline: koʻrinmaydi', () => {
    const { unmount } = render(<AudioPlayer src="/a.wav" title="Salomlashuv" meta="WAV · 0:09" />);
    expect(screen.getByText('Salomlashuv')).toBeVisible();
    expect(screen.getByText('WAV · 0:09')).toBeVisible();
    unmount();
    render(<AudioPlayer src="/a.wav" title="Salomlashuv" meta="WAV · 0:09" variant="inline" />);
    expect(screen.queryByText('WAV · 0:09')).toBeNull();
  });

  it('funksiya manbada yuklab olish havolasi yoʻq (token URL\'ga chiqmaydi)', () => {
    render(<AudioPlayer src={async () => new Blob()} title="Salom" />);
    expect(screen.queryByRole('link', { name: 'Yuklab olish' })).toBeNull();
  });
});
