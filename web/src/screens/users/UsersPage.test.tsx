// Xatti-harakat testi — foydalanuvchi yaratish, bogʻlangan ichki raqamni band qilish poyga holati
// (extension_taken) va oʻzini bloklab qoʻymaslik (self_lockout) UI darajasida oldindan toʻsilishi (M2b §3).
// Qarang ../../../replica/m2b-contract.md §3.
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { UsersPage } = await import('./UsersPage');

describe('UsersPage', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('yangi foydalanuvchi muvaffaqiyatli yaratiladi', async () => {
    const user = userEvent.setup();
    renderPage(<UsersPage />);

    await user.click(await screen.findByRole('button', { name: 'Yangi foydalanuvchi' }));
    await user.type(screen.getByLabelText(/^Login/), 'nodira');
    await user.type(screen.getByLabelText(/^Toʻliq ism/), 'Nodira Qosimova');
    await user.type(screen.getByLabelText(/^Parol/), 'Password123!');
    await user.click(screen.getByRole('button', { name: 'Qoʻshish' }));

    expect(await screen.findByText('nodira')).toBeTruthy();
    const item = (await client.listUsers()).items.find((u) => u.username === 'nodira');
    expect(item?.full_name).toBe('Nodira Qosimova');
  });

  it('poyga holati — tanlangan ichki raqam yuborishdan oldin boshqa foydalanuvchiga bogʻlanib qolsa, extension_taken xatosi maydon ostida chiqadi', async () => {
    const user = userEvent.setup();
    renderPage(<UsersPage />);

    await user.click(await screen.findByRole('button', { name: 'Yangi foydalanuvchi' }));
    await user.type(screen.getByLabelText(/^Login/), 'race2');
    await user.type(screen.getByLabelText(/^Toʻliq ism/), 'Poyga Testi');
    await user.type(screen.getByLabelText(/^Parol/), 'Password123!');

    await user.click(screen.getByRole('combobox', { name: 'Ichki raqam' }));
    await user.click(await screen.findByRole('option', { name: '103 — Aziz Rahimov' }));

    // Forma ochiq paytda — boshqa foydalanuvchi xuddi shu ichki raqamni oladi (poyga holati).
    await client.createUser({
      username: 'race', full_name: 'Poyga Boshqasi', password: 'Password123!',
      role: 'operator', extension_id: 'e-103', language: 'uz', email: null,
    });

    await user.click(screen.getByRole('button', { name: 'Qoʻshish' }));

    expect(await screen.findByText(/103 allaqachon «race»ga bogʻlangan/)).toBeTruthy();
    // Drawer ochiq qolgan — saqlanmagan.
    expect(screen.getByLabelText(/^Login/)).toHaveValue('race2');
    const item = (await client.listUsers()).items.find((u) => u.username === 'race2');
    expect(item).toBeUndefined();
  });

  it('oʻzini: oʻchirish tugmasi va rol/faollik boshqaruvlari oldindan oʻchirilgan (self_lockout UI darajasida)', async () => {
    const user = userEvent.setup();
    renderPage(<UsersPage />);

    const row = (await screen.findByText('admin')).closest('tr')!;
    expect(within(row).getByRole('button', { name: 'adminni oʻchirish' })).toBeDisabled();

    await user.click(within(row).getByRole('button', { name: 'adminni tahrirlash' }));
    expect(screen.getByRole('combobox', { name: 'Rol' })).toBeDisabled();
    expect(screen.getByRole('switch', { name: 'Faol' })).toBeDisabled();
  });
});
