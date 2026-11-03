// Xatti-harakat testi — foydalanuvchi yaratish, bogʻlangan ichki raqamni band qilish poyga holati
// (extension_taken) va oʻzini bloklab qoʻymaslik (self_lockout) UI darajasida oldindan toʻsilishi (M2b §3).
// Qarang ../../../replica/m2b-contract.md §3.
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createFakeClient } from '@/api/fake';
import { SEED_CUSTOM_USER, SEED_CUSTOM_USER_PASSWORD } from '@/api/fakeSeed';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';

/** M7 — maxsus (koʻrish-tahrirlash) rolli «nazoratchi» sifatida kiradi (qarang fakeSeed.ts, `*` ruxsati yoʻq). */
async function loginAsCustomRole() {
  const res = await client.login(SEED_CUSTOM_USER.login, SEED_CUSTOM_USER_PASSWORD);
  if (res.status !== 'ok') throw new Error('2FA kutilmagan edi');
  useSession.setState({ access: res.access, refresh: res.refresh, user: res.user });
}

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

// M7 §2/§4 — Rollar tabi: jadval, "Yangi rol", tizim rolini faqat koʻrish, oʻchirishda `role_in_use`.
// Qarang ../../../replica/m7-roles-contract.md §2/§4.
describe('UsersPage — Rollar tabi', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('rollar roʻyxatida tizim rollari (belgi bilan) va maxsus rol koʻrinadi', async () => {
    const user = userEvent.setup();
    renderPage(<UsersPage />);

    await user.click(await screen.findByRole('tab', { name: 'Rollar' }));

    const adminRow = (await screen.findByText('Admin')).closest('tr')!;
    expect(within(adminRow).getByText('Tizim')).toBeTruthy();
    const customRow = (await screen.findByText('Nazoratchi')).closest('tr')!;
    expect(within(customRow).queryByText('Tizim')).toBeNull();
    expect(within(customRow).getByText('1')).toBeTruthy();
  });

  it('tizim rolini tahrirlashga urinilsa — faqat oʻqish uchun tasvir koʻrinadi, oʻchirish tugmasi oʻchirilgan', async () => {
    const user = userEvent.setup();
    renderPage(<UsersPage />);

    await user.click(await screen.findByRole('tab', { name: 'Rollar' }));
    const adminRow = (await screen.findByText('Admin')).closest('tr')!;
    expect(within(adminRow).getByRole('button', { name: 'Admin rolini oʻchirish' })).toBeDisabled();

    await user.click(within(adminRow).getByRole('button', { name: 'Admin rolini tahrirlash' }));
    expect(await screen.findByText(/Tizim roli/)).toBeTruthy();
    expect(screen.queryByLabelText(/^Rol nomi/)).toBeNull();
    // Dialogning oʻz X yopish tugmasi ham «Yopish» deb ataladi — pastki footer tugmasi ikkinchisi.
    expect(screen.getAllByRole('button', { name: 'Yopish' }).length).toBeGreaterThan(0);
  });

  it('yangi maxsus rol yaratiladi va u foydalanuvchi shaklidagi "Rol" tanlovida koʻrinadi', async () => {
    const user = userEvent.setup();
    renderPage(<UsersPage />);

    await user.click(await screen.findByRole('tab', { name: 'Rollar' }));
    await user.click(await screen.findByRole('button', { name: 'Yangi rol' }));
    await user.type(screen.getByLabelText(/^Rol nomi/), 'Hisobchi');
    // Har bir hudud qatori oʻzining radiogroup (`aria-label="Hisobotlar"` kabi) ichida — shu bilan
    // bir xil "Koʻrish" nomli radio tugmalar orasidan faqat shu qatornikini tanlaymiz.
    await user.click(within(screen.getByRole('radiogroup', { name: 'Hisobotlar', hidden: true })).getByRole('radio', { name: 'Koʻrish', hidden: true }));
    await user.click(screen.getByRole('button', { name: 'Qoʻshish' }));

    expect(await screen.findByText('Hisobchi')).toBeTruthy();

    await user.click(await screen.findByRole('tab', { name: 'Foydalanuvchilar' }));
    await user.click(await screen.findByRole('button', { name: 'Yangi foydalanuvchi' }));
    await user.click(screen.getByRole('combobox', { name: 'Rol' }));
    expect(await screen.findByRole('option', { name: 'Hisobchi' })).toBeTruthy();
  });

  it('foydalanuvchi bogʻlangan maxsus rolni oʻchirishga urinilsa — role_in_use xabari chiqadi', async () => {
    const user = userEvent.setup();
    renderPage(<UsersPage />);

    await user.click(await screen.findByRole('tab', { name: 'Rollar' }));
    const customRow = (await screen.findByText('Nazoratchi')).closest('tr')!;
    await user.click(within(customRow).getByRole('button', { name: 'Nazoratchi rolini oʻchirish' }));
    await user.click(screen.getByRole('button', { name: 'Oʻchirish' }));

    expect(await screen.findByText(/bogʻlangan — avval ularni boshqa rolga oʻtkazing/)).toBeTruthy();
  });
});

// M7 §1/§4 — koʻrish-huquqli (view-only) foydalanuvchi uchun "Yangi ..." tugmalari butunlay yoʻq.
describe('UsersPage — koʻrish-huquqli rol (useCanEdit emas, lekin bu ekran butunlay `*`ga bogʻliq)', () => {
  afterEach(() => useSession.getState().clear());

  it('`*` ruxsati yoʻq foydalanuvchida "Yangi foydalanuvchi" va "Yangi rol" tugmalari koʻrinmaydi', async () => {
    await loginAsCustomRole();
    renderPage(<UsersPage />);

    expect(await screen.findByText('Foydalanuvchilar', { selector: 'caption' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Yangi foydalanuvchi' })).toBeNull();

    const user = userEvent.setup();
    await user.click(screen.getByRole('tab', { name: 'Rollar' }));
    // `GET /roles` ham Tizim guruhiga tegishli — faqat `*` (m7-roles-contract.md §2) — shuning uchun
    // koʻrish-huquqli foydalanuvchi uchun roʻyxat 403 bilan qaytadi va jadval boʻsh/xato holatini
    // koʻrsatadi; bu yerda faqat "Yangi rol" tugmasi yoʻqligini tekshiramiz (jadval qulab tushmaydi).
    expect(await screen.findByText('Rollar', { selector: 'caption' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Yangi rol' })).toBeNull();
  });
});
