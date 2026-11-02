// Xatti-harakat testi — yaratish, PIN (`has_pin`) ko'rinishi, 409 `in_use` o'chirishda.
// Qarang ../../../replica/m2a-contract.md §4.
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

const { ConferencesPage } = await import('./ConferencesPage');

describe('ConferencesPage', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it("yaratish — PIN bilan, jadvalda «PIN bilan» ko'rinadi", async () => {
    const user = userEvent.setup();
    renderPage(<ConferencesPage />);

    await user.click(await screen.findByRole('button', { name: 'Yangi konferensiya' }));
    await user.type(screen.getByRole('textbox', { name: 'Nom' }), 'Marketing yigʻilishi');
    await user.click(screen.getByRole('switch', { name: 'PIN' }));
    await user.type(screen.getByRole('textbox', { name: 'PIN' }), '1357');
    await user.click(screen.getByRole('button', { name: "Qoʻshish" }));

    await waitFor(() => expect(screen.queryByRole('textbox', { name: 'Nom' })).toBeNull());
    const row = (await screen.findByText('Marketing yigʻilishi')).closest('tr')!;
    expect(row.textContent).toContain('PIN bilan');
  });

  it("in_use — boshqa joyda ishlatilayotgan konferensiyani o'chirib bo'lmaydi, kim ishlatayotgani ko'rsatiladi", async () => {
    const user = userEvent.setup();
    const { items } = await client.listConferences();
    const conf = items[0]!;
    await client.createInboundRoute({ name: 'Konf marshrut', did: '998712000077', cid: null, target_id: conf.target_id, enabled: true });

    renderPage(<ConferencesPage />);
    await user.click(await screen.findByRole('button', { name: `${conf.name}ni oʻchirish` }));
    await screen.findByRole('heading', { name: new RegExp(`${conf.name}ni oʻchirish`) });
    await user.click(screen.getByRole('button', { name: 'Oʻchirish' }));

    expect(await screen.findByText(new RegExp(`«${conf.name}» hali ishlatilmoqda`))).toBeTruthy();
    expect(screen.getByText('Konf marshrut')).toBeTruthy();
    // Natija: konferensiya ro'yxatda qolgan (o'chirilmagan).
    expect((await client.listConferences()).items.some((c) => c.id === conf.id)).toBe(true);
  });

  it("operator — faqat o'qiydi, yangi konferensiya tugmasi yo'q", async () => {
    await loginAs(client, 'operator');
    renderPage(<ConferencesPage />);

    expect(await screen.findByText(/ruxsati yo/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Yangi konferensiya' })).toBeNull();
  });
});
