// Xatti-harakat testi — Paneldan yangilash: updating paytida 502 ("API konteyneri qayta ishga tushdi")
// xato emas, "tizim qayta ishga tushmoqda" banneri koʻrinadi va polling davom etib oxirida "done" boʻladi.
// Shartnoma: ../../replica/m11-update-contract.md §5.
import { describe, expect, it, afterEach, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';
import { ToastProvider } from '@/ui/Toast';

const client = createFakeClient({ updateScenario: 'restart_502' });
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { UpdatePage } = await import('./UpdatePage');

describe('UpdatePage — updating paytida 502 (qayta ishga tushish)', () => {
  afterEach(() => useSession.getState().clear());

  it('502 xato koʻrsatilmaydi — "qayta ishga tushmoqda" banneri chiqadi va jarayon "done" bilan yakunlanadi', async () => {
    const user = userEvent.setup();
    await loginAs(client, 'admin');
    renderPage(<ToastProvider><UpdatePage /></ToastProvider>);

    await user.click(await screen.findByRole('button', { name: 'Yangilash' }));
    const dialog = await screen.findByRole('dialog', { name: '1.0.13 ga yangilash' });
    await user.type(screen.getByPlaceholderText('0.0.0'), '1.0.13');
    await user.click(screen.getByRole('button', { name: 'Boshlash' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    void dialog;

    await screen.findByText('Yangilanish jarayoni');
    // 502 xatoning oʻzi xato toastiga aylanmasligi kerak — "qayta ishga tushmoqda" banneri bilan almashadi.
    await waitFor(() => expect(screen.getByText('Tizim qayta ishga tushmoqda — bu normal holat, kuting…')).toBeTruthy(), {
      timeout: 6000,
    });
    expect(screen.queryByText(/Bad Gateway/i)).toBeNull();

    await waitFor(() => expect(screen.getByText('Yangilandi')).toBeTruthy(), { timeout: 8000 });
  }, 20_000);
});
