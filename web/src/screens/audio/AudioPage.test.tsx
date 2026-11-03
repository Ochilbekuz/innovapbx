// Xatti-harakat testi — M10 C A3: "Matndan audio yaratish" (TTS) kartasi/dialogi.
// Qarang ../../../replica/m10-onlinepbx-contract.md §A3.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';
import { ToastProvider } from '@/ui/Toast';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { AudioPage } = await import('./AudioPage');

describe('AudioPage — TTS (matndan audio)', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('sozlanmagan boʻlsa — admin uchun sozlash havolasi koʻrsatiladi, dialog ochilmaydi', async () => {
    renderPage(<AudioPage />);

    expect(await screen.findByText('Nutq sintezi sozlanmagan.')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Sozlashga oʻtish' })).toHaveAttribute('href', '/settings/integrations');
    expect(screen.queryByRole('button', { name: 'Boshlash' })).toBeNull();
  });

  it('sozlangan boʻlsa — matn kiritib tinglab koʻrish va saqlash audio kutubxonaga qoʻshadi', async () => {
    const before = await client.getTtsSettings();
    await client.updateTtsSettings({ provider: 'yandex', api_key: 'sinov-kalit', updated_at: before.updated_at });

    const user = userEvent.setup();
    renderPage(<ToastProvider><AudioPage /></ToastProvider>);

    await user.click(await screen.findByRole('button', { name: 'Boshlash' }));
    await screen.findByRole('dialog', { name: 'Matndan audio yaratish' });

    await user.type(screen.getByRole('textbox', { name: 'Audio nomi' }), 'Sinov salomlashuvi');
    await user.type(screen.getByRole('textbox', { name: 'Matn' }), 'Assalomu alaykum, bu sinov matni.');

    await user.click(screen.getByRole('button', { name: 'Tinglab koʻrish' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Tinglash' })).toBeEnabled());

    await user.click(screen.getByRole('button', { name: 'Saqlash' }));

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(await screen.findByText(/Sinov salomlashuvi/)).toBeTruthy();
    expect((await client.listAudio()).items.some((a) => a.name === 'Sinov salomlashuvi')).toBe(true);
  });

  it('boʻsh matn bilan saqlash/tinglab koʻrish tugmalari oʻchiq boʻladi', async () => {
    const before = await client.getTtsSettings();
    await client.updateTtsSettings({ provider: 'yandex', api_key: 'sinov-kalit-2', updated_at: before.updated_at });

    const user = userEvent.setup();
    renderPage(<AudioPage />);

    await user.click(await screen.findByRole('button', { name: 'Boshlash' }));
    await screen.findByRole('dialog', { name: 'Matndan audio yaratish' });

    expect(screen.getByRole('button', { name: 'Tinglab koʻrish' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Saqlash' })).toBeDisabled();
  });
});
