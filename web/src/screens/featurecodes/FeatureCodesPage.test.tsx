// Xatti-harakat testi — fake klient bilan render, foydalanuvchi kabi tahrirlaydi, natija ko'rinishini tekshiradi.
// Qarang ../../../replica/m2a-contract.md §2.
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { FeatureCodesPage } = await import('./FeatureCodesPage');

describe('FeatureCodesPage', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it("kod to'qnashuvi — 409 xabari to'qnashgan kodni ko'rsatadi", async () => {
    const user = userEvent.setup();
    renderPage(<FeatureCodesPage />);

    // `findByRole` jadval yuklanishini kutadi — oddiy matn "Ovozli pochta" yon panelda ham bor (noaniq bo'ladi).
    await user.click(await screen.findByRole('button', { name: 'Ovozli pochta kodini tahrirlash' }));

    const input = screen.getByRole('textbox', { name: 'Kod' });
    await user.clear(input);
    await user.type(input, '*98'); // "Boshqa ichki raqam ovozli pochtasi" kodi bilan to'qnashadi
    await user.click(screen.getByRole('button', { name: 'Saqlash' }));

    expect(await screen.findByText((text) => text.includes('*98') && text.includes('Bu kod'))).toBeTruthy();
    // Tahrirlash rejimida qolgan — saqlanmagan.
    expect(screen.getByRole('textbox', { name: 'Kod' })).toHaveValue('*98');
  });

  it('reset — standart kodga qaytaradi va yoqadi', async () => {
    // "Guruh pickup" — jadvalning 1-sahifasida (pageSize=8); "Eho testi" 2-sahifada bo'lgani uchun tanlanmadi.
    const user = userEvent.setup();
    renderPage(<FeatureCodesPage />);

    await user.click(await screen.findByRole('button', { name: 'Guruh pickup kodini tahrirlash' }));
    const input = screen.getByRole('textbox', { name: 'Kod' });
    await user.clear(input);
    await user.type(input, '*88');
    await user.click(screen.getByRole('button', { name: 'Saqlash' }));

    await waitFor(() => expect(screen.getByText('*88')).toBeTruthy());
    await user.click(screen.getByRole('button', { name: 'Guruh pickup kodini standart holatga qaytarish' }));

    await waitFor(() => expect(screen.getByText('*8')).toBeTruthy());
    const item = (await client.listFeatureCodes()).items.find((f) => f.feature === 'pickup_group');
    expect(item?.code).toBe('*8');
    expect(item?.enabled).toBe(true);
  });

  it('operator — faqat o\'qiydi, tahrirlash tugmasi yo\'q', async () => {
    await loginAs(client, 'operator');
    renderPage(<FeatureCodesPage />);

    expect(await screen.findByText(/ruxsati yo/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Ovozli pochta kodini tahrirlash' })).toBeNull();
  });
});
