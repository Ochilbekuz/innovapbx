// Xatti-harakat testi — jonli monitoring: faol qoʻngʻiroqlar/navbatlar/ichki raqamlar koʻrinadi,
// ichki raqami yoʻq admin nazorat (spy) qilmoqchi boʻlsa no_extension xabari chiqadi (M2b §2).
// Qarang ../../../replica/m2b-contract.md §2.
import { describe, expect, it, afterEach, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
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

const { LivePage } = await import('./LivePage');

describe('LivePage', () => {
  afterEach(() => useSession.getState().clear());

  it('faol qoʻngʻiroqlar, navbat kartasi va ichki raqamlar holati koʻrinadi', async () => {
    await loginAs(client, 'admin');
    renderPage(<ToastProvider><LivePage /></ToastProvider>);

    expect(await screen.findByText('998901112233')).toBeTruthy();
    const queueCard = (await screen.findByText('Sotuv boʻlimi')).closest('div')!.parentElement!;
    expect(within(queueCard).getByText('1')).toBeTruthy(); // lc-2 — navbatda kutmoqda.

    expect(await screen.findByText('Dilnoza Karimova')).toBeTruthy();
  });

  it('ichki raqami yoʻq admin nazorat qilishga urinsa — "no_extension" xabari toast orqali chiqadi', async () => {
    await loginAs(client, 'admin'); // SEED_ADMIN hech qaysi ichki raqamga bogʻlanmagan.
    const user = userEvent.setup();
    renderPage(<ToastProvider><LivePage /></ToastProvider>);

    const row = (await screen.findByText('998901112233')).closest('tr')!;
    await user.click(within(row).getByRole('button', { name: 'Tinglash' }));

    expect(await screen.findByText('Nazoratni boshlab boʻlmadi')).toBeTruthy();
    expect(await screen.findByText(/ichki raqamga bogʻlanmagan/)).toBeTruthy();
  });
});
