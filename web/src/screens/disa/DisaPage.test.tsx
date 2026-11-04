// Xatti-harakat testi — yaratish (PIN bo'sh bo'lsa allow_no_pin talab qilinadi),
// in_use o'chirishda bloklanishi, operator faqat o'qiydi. Qarang ../../../replica/m12-contract.md §A2.
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

const { DisaPage } = await import('./DisaPage');

describe('DisaPage', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('yaratish — PIN bilan, jadvalda «Oʻrnatilgan» koʻrinadi', async () => {
    const user = userEvent.setup();
    renderPage(<DisaPage />);

    await user.click(await screen.findByRole('button', { name: 'Yangi DISA' }));
    await user.type(screen.getByRole('textbox', { name: 'Nom' }), 'Tashqi kirish');
    await user.type(screen.getByLabelText('PIN'), '2468');
    await user.click(screen.getByRole('button', { name: "Qoʻshish" }));

    await waitFor(() => expect(screen.queryByRole('textbox', { name: 'Nom' })).toBeNull());
    const row = (await screen.findByText('Tashqi kirish')).closest('tr')!;
    expect(row.textContent).toContain('Oʻrnatilgan');
  });

  it("PIN boʻsh va allow_no_pin oʻchirilgan boʻlsa — qoʻshish tugmasi oʻchirilgan", async () => {
    const user = userEvent.setup();
    renderPage(<DisaPage />);

    await user.click(await screen.findByRole('button', { name: 'Yangi DISA' }));
    await user.type(screen.getByRole('textbox', { name: 'Nom' }), 'PINsiz sinov');
    expect(screen.getByRole('button', { name: "Qoʻshish" })).toBeDisabled();

    await user.click(screen.getByRole('switch', { name: 'PINsiz kirishga ruxsat' }));
    expect(screen.getByRole('button', { name: "Qoʻshish" })).not.toBeDisabled();
  });

  it("in_use — ishlatilayotgan DISA'ni o'chirib bo'lmaydi, kim ishlatayotgani ko'rsatiladi", async () => {
    const user = userEvent.setup();
    const { items } = await client.listDisa();
    const disa = items[0]!;
    await client.createInboundRoute({ name: 'DISA marshrut', did: '998712000077', cid: null, target_id: disa.id, enabled: true });

    renderPage(<DisaPage />);
    await user.click(await screen.findByRole('button', { name: `${disa.name}ni oʻchirish` }));
    await screen.findByRole('heading', { name: new RegExp(`${disa.name}ni oʻchirish`) });
    await user.click(screen.getByRole('button', { name: 'Oʻchirish' }));

    expect(await screen.findByText(new RegExp(`«${disa.name}» hali ishlatilmoqda`))).toBeTruthy();
    expect(screen.getByText('DISA marshrut')).toBeTruthy();
    expect((await client.listDisa()).items.some((d) => d.id === disa.id)).toBe(true);
  });

  it("operator — faqat o'qiydi, yangi DISA tugmasi yo'q", async () => {
    await loginAs(client, 'operator');
    renderPage(<DisaPage />);

    expect(await screen.findByText(/ruxsati yo/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Yangi DISA' })).toBeNull();
  });
});
