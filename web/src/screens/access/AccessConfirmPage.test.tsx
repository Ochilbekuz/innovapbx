// Xatti-harakat testi — ommaviy /access-confirm sahifasi (M12 B4 §3): pending_id yo'q, muvaffaqiyatli
// tasdiqlash (login tugmasi), muvaffaqiyatsiz tasdiqlash (yaroqsiz/eskirgan havola).
import { describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const navigateTo = vi.fn();
vi.mock('@/lib/browser', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/browser')>();
  return { ...actual, navigateTo };
});

const { AccessConfirmPage } = await import('./AccessConfirmPage');

/** Admin sifatida kirib veb-panel portini o'zgartiradi — qaytgan `pending.id`ni beradi. */
async function createWebPendingId(): Promise<string> {
  await loginAs(client, 'admin');
  const state = await client.applyWeb({ http_port: 8080, https_port: 8443, timeout_s: 60 });
  useSession.getState().clear();
  if (!state.pending) throw new Error('kutilayotgan oʻzgarish yaratilmadi');
  return state.pending.id;
}

describe('AccessConfirmPage', () => {
  it('pending_id yoʻq — xato koʻrsatiladi', async () => {
    renderPage(<AccessConfirmPage />, '/access-confirm');

    expect(await screen.findByText('Veb-panel manzilini tasdiqlash')).toBeTruthy();
    expect(await screen.findByText('Tasdiqlash havolasi yaroqsiz.')).toBeTruthy();
  });

  it('toʻgʻri pending_id — muvaffaqiyat va login tugmasi', async () => {
    const pendingId = await createWebPendingId();
    const user = userEvent.setup();
    renderPage(<AccessConfirmPage />, `/access-confirm#${pendingId}`);

    const loginButton = await screen.findByRole('button', { name: 'Kirish' });
    await user.click(loginButton);

    expect(navigateTo).toHaveBeenCalledWith('/');
  });

  it('notoʻgʻri/eskirgan pending_id — muvaffaqiyatsizlik koʻrsatiladi', async () => {
    renderPage(<AccessConfirmPage />, '/access-confirm#notogri-id');

    expect(await screen.findByText(/Tasdiqlab boʻlmadi/)).toBeTruthy();
  });
});
