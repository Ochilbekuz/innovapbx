// Xatti-harakat testi — holatni almashtirish (*28N), in_use o'chirishda bloklanishi,
// operator faqat o'qiydi. Qarang ../../../replica/m12-contract.md §A1.
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

const { DayNightPage } = await import('./DayNightPage');

describe('DayNightPage', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('holatni almashtirish — Kunduzgi -> Tungi, jadval yangilanadi', async () => {
    const user = userEvent.setup();
    const { items } = await client.listDayNight();
    const rule = items[0]!;
    expect(rule.mode).toBe('day');

    renderPage(<DayNightPage />);
    const row = (await screen.findByText(rule.name)).closest('tr')!;
    expect(row.textContent).toContain('Kunduzgi');

    await user.click(screen.getByRole('button', { name: `${rule.name} holatini almashtirish` }));
    await waitFor(() => expect(row.textContent).toContain('Tungi'));
    expect((await client.listDayNight()).items[0]!.mode).toBe('night');
  });

  it("in_use — ishlatilayotgan qoidani o'chirib bo'lmaydi, kim ishlatayotgani ko'rsatiladi", async () => {
    const user = userEvent.setup();
    const { items } = await client.listDayNight();
    const rule = items[0]!;
    await client.createInboundRoute({ name: 'Kun/tun marshrut', did: '998712000088', cid: null, target_id: rule.id, enabled: true });

    renderPage(<DayNightPage />);
    await user.click(await screen.findByRole('button', { name: `${rule.name}ni oʻchirish` }));
    await screen.findByRole('heading', { name: new RegExp(`${rule.name}ni oʻchirish`) });
    await user.click(screen.getByRole('button', { name: 'Oʻchirish' }));

    expect(await screen.findByText(new RegExp(`«${rule.name}» hali ishlatilmoqda`))).toBeTruthy();
    expect(screen.getByText('Kun/tun marshrut')).toBeTruthy();
    expect((await client.listDayNight()).items.some((d) => d.id === rule.id)).toBe(true);
  });

  it("operator — faqat o'qiydi, yangi qoida tugmasi yo'q va holatni almashtirish o'chirilgan", async () => {
    await loginAs(client, 'operator');
    renderPage(<DayNightPage />);

    expect(await screen.findByText(/ruxsati yo/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Yangi qoida' })).toBeNull();
    const { items } = await client.listDayNight();
    expect(screen.getByRole('button', { name: `${items[0]!.name} holatini almashtirish` })).toBeDisabled();
  });
});
