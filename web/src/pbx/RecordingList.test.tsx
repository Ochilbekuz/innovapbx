// Xatti-harakat testi — yozuvni tinglash (play/pause), yuklab olish, admin uchun oʻchirish.
// Qarang ../../../replica/m3b-contract.md §1.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const fetchRecordingAudio = vi.fn(async () => new Blob(['RIFF']));
const deleteRecording = vi.fn(async () => {});
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: { ...actual.apiClient, fetchRecordingAudio, deleteRecording } };
});

const { RecordingList } = await import('./RecordingList');

function wrap(children: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{children}</QueryClientProvider>);
}

describe('RecordingList', () => {
  beforeEach(() => {
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:sinov'), revokeObjectURL: vi.fn() }));
    vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined);
  });
  afterEach(() => vi.restoreAllMocks());

  it('yozuv yoʻq boʻlsa — hech narsa chiqarmaydi', () => {
    const { container } = wrap(<RecordingList recordings={[]} canDelete={false} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('tinglash — bosilganda faylni bir marta oladi, ijro etadi', async () => {
    const user = userEvent.setup();
    const { container } = wrap(<RecordingList recordings={[{ id: 'rec-1', duration_s: 42 }]} canDelete={false} />);
    await user.click(screen.getByTestId('recording-play-rec-1'));
    await waitFor(() => expect(fetchRecordingAudio).toHaveBeenCalledWith('rec-1'));
    expect(container.querySelector('audio')).toHaveAttribute('src', 'blob:sinov');
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalled();
  });

  it('yuklab olish tugmasi faylni oladi', async () => {
    const user = userEvent.setup();
    wrap(<RecordingList recordings={[{ id: 'rec-2', duration_s: 10 }]} canDelete={false} />);
    await user.click(screen.getByTestId('recording-download-rec-2'));
    await waitFor(() => expect(fetchRecordingAudio).toHaveBeenCalledWith('rec-2'));
  });

  it('canDelete=false boʻlsa — oʻchirish tugmasi koʻrinmaydi', () => {
    wrap(<RecordingList recordings={[{ id: 'rec-3', duration_s: 10 }]} canDelete={false} />);
    expect(screen.queryByRole('button', { name: 'Yozuvni oʻchirish' })).toBeNull();
  });

  it('canDelete=true — tasdiqlab oʻchirish `deleteRecording`ni chaqiradi', async () => {
    const user = userEvent.setup();
    wrap(<RecordingList recordings={[{ id: 'rec-4', duration_s: 10 }]} canDelete={true} />);
    await user.click(screen.getByRole('button', { name: 'Yozuvni oʻchirish' }));
    await user.click(screen.getByRole('button', { name: 'Oʻchirish' }));
    await waitFor(() => expect(deleteRecording).toHaveBeenCalledWith('rec-4'));
  });
});
