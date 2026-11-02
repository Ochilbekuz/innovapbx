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

const { RecordingList, recordingFileBase, recordingFileName } = await import('./RecordingList');

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

  it('yuklab olingan fayl nomi — Toshkent vaqti + kimdan + kimga (bir nechta yozuvda tartib raqami)', async () => {
    const user = userEvent.setup();
    const names: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) { names.push(this.download); });
    const call = { started_at: '2026-11-02T20:12:35Z', src: '+998 90 123-45-67', dst: '101' };
    wrap(<RecordingList recordings={[{ id: 'a', duration_s: 1 }, { id: 'b', duration_s: 1 }]} canDelete={false} fileBase={recordingFileBase(call)} />);
    await user.click(screen.getByTestId('recording-download-a'));
    await user.click(screen.getByTestId('recording-download-b'));
    await waitFor(() => expect(names).toEqual([
      '2026-11-03_01-12-35_+998901234567_101_1.wav',
      '2026-11-03_01-12-35_+998901234567_101_2.wav',
    ]));
  });

  it('fayl nomi: bitta yozuv — tartib raqamisiz; raqam boʻsh — «nomalum»; fileBase yoʻq — id', () => {
    expect(recordingFileName(recordingFileBase({ started_at: '2026-01-05T03:04:05Z', src: '', dst: '*97' }), 'r', 0, 1))
      .toBe('2026-01-05_08-04-05_nomalum_97.wav');
    expect(recordingFileName(undefined, 'rec-9', 0, 1)).toBe('rec-9.wav');
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
