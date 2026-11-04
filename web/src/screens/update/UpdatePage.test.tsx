// Xatti-harakat testi — Paneldan yangilash (S45, M11): versiya+changelog, tasdiq modali (qoʻlda yozish),
// yangilanish jarayoni (bosqichlar + jurnal), done→muvaffaqiyat. Qarang NetworkPage.test.tsx uslubi.
// Shartnoma: ../../replica/m11-update-contract.md §5.
import { describe, expect, it, afterEach, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';
import { ToastProvider } from '@/ui/Toast';

const client = createFakeClient({ updateAvailable: true });
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { UpdatePage } = await import('./UpdatePage');

describe('UpdatePage', () => {
  afterEach(() => useSession.getState().clear());

  it('joriy versiya, tekshirilmagan holat va yangi versiya + changelog (xavfsiz render) koʻrsatiladi', async () => {
    await loginAs(client, 'admin');
    renderPage(<UpdatePage />);

    await screen.findByText('1.0.12');
    expect(screen.getByText('Hali tekshirilmagan')).toBeTruthy();
    expect(screen.getByText('Yangi versiya: 1.0.13')).toBeTruthy();
    expect(screen.getByText(/Paneldan yangilash qo'shildi/)).toBeTruthy();
    // Markdown — xavfsiz: literal matn koʻrinadi, HTML teg sifatida parse qilinmaydi.
    expect(screen.getByText(/<xato>/)).toBeTruthy();
    expect(document.querySelector('xato')).toBeNull();
  }, 10_000);

  it('"Tekshirish" bosilganda holat yangilanadi (oxirgi tekshiruv vaqti koʻrinadi)', async () => {
    const user = userEvent.setup();
    await loginAs(client, 'admin');
    renderPage(<UpdatePage />);

    await user.click(await screen.findByRole('button', { name: 'Tekshirish' }));
    await waitFor(() => expect(screen.queryByText('Hali tekshirilmagan')).toBeNull(), { timeout: 6000 });
  }, 10_000);

  it(
    'tasdiq modali: notoʻgʻri versiya yozilsa tugma oʻchiq, toʻgʻri yozilsa yangilash boshlanadi va bosqichlar + jurnal koʻrinadi',
    async () => {
      const user = userEvent.setup();
      await loginAs(client, 'admin');
      renderPage(<ToastProvider><UpdatePage /></ToastProvider>);

      await user.click(await screen.findByRole('button', { name: 'Yangilash' }));
      const dialog = await screen.findByRole('dialog', { name: '1.0.13 ga yangilash' });

      const input = within(dialog).getByPlaceholderText('0.0.0');
      await user.type(input, '9.9.9');
      const startBtn = within(dialog).getByRole('button', { name: 'Boshlash' });
      expect(startBtn).toBeDisabled();

      await user.clear(input);
      await user.type(input, '1.0.13');
      expect(startBtn).not.toBeDisabled();
      await user.click(startBtn);

      await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
      expect(await screen.findByText('Yangilanish jarayoni')).toBeTruthy();
      await waitFor(() => expect(screen.getByText(/Zaxira olinmoqda/)).toBeTruthy(), { timeout: 6000 });
      // API javob berib turibdi — bu "qayta ishga tushish" EMAS (faqat 502/503/tarmoq xatosida)
      expect(screen.queryByText(/Tizim qayta ishga tushmoqda/)).toBeNull();
    },
    15_000,
  );

  it('yangilanish yakunlanganda muvaffaqiyat xabari va "Sahifani yangilash" tugmasi chiqadi', async () => {
    await loginAs(client, 'admin');
    renderPage(<UpdatePage />);

    await waitFor(() => expect(screen.getByText('Yangilandi')).toBeTruthy(), { timeout: 8000 });
    expect(screen.getByText(/1\.0\.13 versiyasiga muvaffaqiyatli yangilandi/)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Sahifani yangilash' })).toBeTruthy();
  }, 12_000);
});
