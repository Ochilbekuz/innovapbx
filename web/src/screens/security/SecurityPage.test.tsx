// Xatti-harakat testi — Holat/Bloklangan IP/Toll-fraud/Sozlamalar/Hodisalar tablari.
// Qarang ../../../replica/m2c-contract.md §1-3.
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

const { SecurityPage } = await import('./SecurityPage');

describe('SecurityPage', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('Holat — KPI va top IP roʻyxati seed maʼlumotlari bilan toʻladi, bloklanmagan IP ni bloklash mumkin', async () => {
    const user = userEvent.setup();
    renderPage(<SecurityPage />);

    expect(await screen.findByText('Faol banlar')).toBeTruthy();
    expect(await screen.findByText('203.0.113.77')).toBeTruthy();

    const blockBtn = await screen.findByRole('button', { name: '45.33.12.9 ni bloklash' });
    await user.click(blockBtn);

    await waitFor(() => expect(screen.queryByRole('button', { name: '45.33.12.9 ni bloklash' })).toBeNull());
    expect((await client.securityBans()).items.some((b) => b.ip === '45.33.12.9')).toBe(true);
  });

  it('Bloklangan IP — 422 bad_ip va 409 trusted_ip xatolari IP maydoni ostida chiqadi, soʻng muvaffaqiyatli bloklanadi', async () => {
    const user = userEvent.setup();
    renderPage(<SecurityPage />);

    await user.click(await screen.findByRole('tab', { name: 'Bloklangan IP' }));
    await user.click(await screen.findByRole('button', { name: 'IPʼni bloklash' }));

    const ipField = screen.getByRole('textbox', { name: 'IP manzil' });
    await user.type(ipField, 'not-an-ip');
    await user.click(screen.getByRole('button', { name: 'Bloklash' }));
    expect(await screen.findByText('IP manzil notoʻgʻri.')).toBeTruthy();

    await user.clear(ipField);
    await user.type(ipField, '10.0.0.5');
    await user.click(screen.getByRole('button', { name: 'Bloklash' }));
    expect(await screen.findByText(/ishonchli tarmoqda/)).toBeTruthy();

    await user.clear(ipField);
    await user.type(ipField, '203.0.113.200');
    await user.click(screen.getByRole('button', { name: 'Bloklash' }));

    await waitFor(() => expect(screen.queryByRole('textbox', { name: 'IP manzil' })).toBeNull());
    expect(await screen.findByText('203.0.113.200')).toBeTruthy();
  });

  it('Bloklangan IP — blokdan chiqarish tasdiqlash dialogi orqali ishlaydi', async () => {
    const user = userEvent.setup();
    renderPage(<SecurityPage />);

    await user.click(await screen.findByRole('tab', { name: 'Bloklangan IP' }));
    await screen.findByText('198.51.100.23');
    await user.click(screen.getByRole('button', { name: '198.51.100.23 ni blokdan chiqarish' }));

    await screen.findByRole('heading', { name: '198.51.100.23 ni blokdan chiqarish' });
    await user.click(screen.getByRole('button', { name: 'Blokdan chiqarish' }));

    await waitFor(() => expect(screen.queryByText('198.51.100.23')).toBeNull());
    expect((await client.securityBans()).items.some((b) => b.ip === '198.51.100.23')).toBe(false);
  });

  it('Bloklangan IP — qidiruv maydoni IP/izoh boʻyicha ekanini aytadi (umumiy «raqam yoki nom» emas)', async () => {
    const user = userEvent.setup();
    renderPage(<SecurityPage />);

    await user.click(await screen.findByRole('tab', { name: 'Bloklangan IP' }));
    expect(await screen.findByPlaceholderText('IP yoki izoh boʻyicha')).toBeTruthy();
  });

  it('Toll-fraud — bloklangan ichki raqamni blokdan chiqarish', async () => {
    const user = userEvent.setup();
    renderPage(<SecurityPage />);

    await user.click(await screen.findByRole('tab', { name: 'Toll-fraud' }));
    await screen.findByText('Jahongir Mirzayev');
    await user.click(screen.getByRole('button', { name: '105 ni blokdan chiqarish' }));

    await waitFor(() => expect(screen.queryByText('Jahongir Mirzayev')).toBeNull());
    const ext = (await client.listExtensions({})).items.find((e) => e.number === '105');
    expect(ext?.toll_blocked_at).toBeNull();
  });

  it('Sozlamalar — saqlash ishlaydi va stale (409) holatida ogohlantirish chiqadi', async () => {
    const user = userEvent.setup();
    renderPage(<SecurityPage />);

    await user.click(await screen.findByRole('tab', { name: 'Sozlamalar' }));
    const maxFailures = await screen.findByRole('textbox', { name: 'Maksimal muvaffaqiyatsiz urinish' });
    await user.clear(maxFailures);
    await user.type(maxFailures, '10');

    // Fon jarayonida sozlamalar boshqa joyda o'zgargan - submit paytida 409 stale qaytadi.
    await client.updateSecuritySettings({ updated_at: (await client.securitySettings()).updated_at, sip_guard: { window_s: 120 } });

    await user.click(screen.getByRole('button', { name: 'Saqlash' }));
    expect(await screen.findByText(/boshqa joyda oʻzgartirilgan/)).toBeTruthy();
  });

  it('Sozlamalar — LAN qurilmalarini bloklamaslik (sukut yoqiq) oʻchirilib saqlanadi', async () => {
    const user = userEvent.setup();
    renderPage(<SecurityPage />);

    await user.click(await screen.findByRole('tab', { name: 'Sozlamalar' }));
    const toggle = await screen.findByRole('switch', { name: 'Lokal tarmoqdagi qurilmalarni avtomatik bloklamaslik' });
    expect(toggle.getAttribute('aria-checked')).toBe('true');
    await user.click(toggle);
    await user.click(screen.getByRole('button', { name: 'Saqlash' }));

    await waitFor(async () => expect((await client.securitySettings()).sip_guard.trust_lan).toBe(false));
  });

  it('Hodisalar — tur boʻyicha filtr ishlaydi', async () => {
    const user = userEvent.setup();
    renderPage(<SecurityPage />);

    await user.click(await screen.findByRole('tab', { name: 'Hodisalar' }));
    await screen.findByText('Xavfsizlik hodisalari');

    await user.click(screen.getByRole('combobox', { name: 'Tur boʻyicha' }));
    await user.click(await screen.findByRole('option', { name: 'Toll-fraud bloklash' }));

    await waitFor(() => expect(screen.queryByText('IP bloklandi')).toBeNull());
  });

  it("operator — faqat o'qiydi, bloklash/sozlash tugmalari bo'lmaydi", async () => {
    await loginAs(client, 'operator');
    renderPage(<SecurityPage />);

    expect(await screen.findByText(/ruxsati yo/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: '45.33.12.9 ni bloklash' })).toBeNull();
  });
});
