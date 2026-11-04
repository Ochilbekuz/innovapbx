// Xatti-harakat testi — Paneldan yangilash: xato kodi bilan yakunlangan holat (M11 §5 — "failed").
import { describe, expect, it, afterEach, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';
import { ToastProvider } from '@/ui/Toast';

const client = createFakeClient({ updateScenario: 'install_failed' });
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { UpdatePage } = await import('./UpdatePage');

describe('UpdatePage — yangilanish muvaffaqiyatsiz (install_failed)', () => {
  afterEach(() => useSession.getState().clear());

  it('xato kodiga mos oʻzbekcha tushuntirish, zaxira fayli va jurnalni koʻrish tugmasi chiqadi', async () => {
    const user = userEvent.setup();
    await loginAs(client, 'admin');
    renderPage(<ToastProvider><UpdatePage /></ToastProvider>);

    await user.click(await screen.findByRole('button', { name: 'Yangilash' }));
    await screen.findByRole('dialog', { name: '1.0.13 ga yangilash' });
    await user.type(screen.getByPlaceholderText('0.0.0'), '1.0.13');
    await user.click(screen.getByRole('button', { name: 'Boshlash' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());

    await waitFor(() => expect(screen.getByText("O'rnatishda xatolik")).toBeTruthy(), { timeout: 10_000 });
    expect(screen.getByText(/Zaxira olingan, lekin o'rnatish bosqichi/)).toBeTruthy();
    expect(screen.getByText(/pre-update-1\.0\.12-20261104-100000\.sql\.gz/)).toBeTruthy();

    const viewLogBtn = screen.getByRole('button', { name: 'Jurnalni ko‘rish' });
    expect(screen.queryByText(/Zaxira olinmoqda/)).toBeNull();
    await user.click(viewLogBtn);
    expect(await screen.findByText(/Zaxira olinmoqda/)).toBeTruthy();
  }, 20_000);
});
