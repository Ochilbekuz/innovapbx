// Xatti-harakat testi — `/parking` FAQAT admin uchun: ParkedCallsCard operatorda butunlay yashirin
// (xato sifatida ko'rsatilmaydi), admin uchun esa ko'rinadi. Qarang ../../../replica/m2a-contract.md §3.
import { describe, expect, it, afterEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { DashboardPage } = await import('./DashboardPage');

describe('DashboardPage — Kutish xonasi (park) kartasi', () => {
  afterEach(() => useSession.getState().clear());

  it('admin — karta ko\'rinadi va /parking 403 bermaydi', async () => {
    await loginAs(client, 'admin');
    renderPage(<DashboardPage />);

    expect(await screen.findByRole('region', { name: 'Kutish xonasidagi qoʻngʻiroqlar' })).toBeTruthy();
    // Seeddagi 701-slot ko'rinadi.
    expect(await screen.findByText('701')).toBeTruthy();
  });

  it("operator — karta butunlay yo'q (xato ham ko'rsatilmaydi)", async () => {
    await loginAs(client, 'operator');
    renderPage(<DashboardPage />);

    // Boshqa karta (jonli qo'ng'iroqlar) ko'rinishini kutib, sahifa to'liq yuklanganini tasdiqlaymiz.
    await screen.findByRole('region', { name: 'Jonli qoʻngʻiroqlar' });

    expect(screen.queryByRole('region', { name: 'Kutish xonasidagi qoʻngʻiroqlar' })).toBeNull();
    expect(screen.queryByText('Kutish xonasi (park)')).toBeNull();
    expect(screen.queryByText(/Yuklab boʻlmadi/)).toBeNull();
  });
});
