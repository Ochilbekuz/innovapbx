// Xatti-harakat testi — qo'shish, anonim/yashirin raqam almashtirish, o'chirish (tasdiq bilan).
// Qarang ../../../replica/m2a-contract.md §5.
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

const { BlacklistPage } = await import('./BlacklistPage');

describe('BlacklistPage', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it("raqam qo'shish — ro'yxatda ko'rinadi", async () => {
    const user = userEvent.setup();
    renderPage(<BlacklistPage />);

    await user.click(await screen.findByRole('button', { name: "Qoʻshish" }));
    await user.type(screen.getByRole('textbox', { name: 'Raqam' }), '998991112233');
    await user.type(screen.getByRole('textbox', { name: 'Sabab' }), 'Spam');
    await user.click(screen.getByRole('button', { name: "Qoʻshish" }));

    await waitFor(() => expect(screen.queryByRole('textbox', { name: 'Raqam' })).toBeNull());
    expect(await screen.findByText('998991112233')).toBeTruthy();
    expect(screen.getByText('Spam')).toBeTruthy();
  });

  it('yashirin raqamlar bloklash — toggle holatini almashtiradi va saqlanadi', async () => {
    const user = userEvent.setup();
    renderPage(<BlacklistPage />);

    const toggle = await screen.findByRole('switch', { name: 'Yashirin/anonim raqamlarni bloklash' });
    await waitFor(() => expect(toggle).toHaveAttribute('aria-checked', 'true')); // seedda anonymous allaqachon bor

    await user.click(toggle);
    await waitFor(() => expect(toggle).toHaveAttribute('aria-checked', 'false'));
    expect((await client.listBlacklist({})).items.some((b) => b.number === 'anonymous')).toBe(false);

    await user.click(toggle);
    await waitFor(() => expect(toggle).toHaveAttribute('aria-checked', 'true'));
    expect((await client.listBlacklist({})).items.some((b) => b.number === 'anonymous')).toBe(true);
  });

  it("o'chirish — tasdiqlash dialogi, tasdiqlagandan keyin ro'yxatdan yo'qoladi", async () => {
    const user = userEvent.setup();
    renderPage(<BlacklistPage />);

    await screen.findByText('998998887766');
    await user.click(screen.getByRole('button', { name: '998998887766ni qora roʻyxatdan olib tashlash' }));

    await screen.findByRole('heading', { name: /998998887766ni olib tashlash/ });
    await user.click(screen.getByRole('button', { name: "Olib tashlash" }));

    await waitFor(() => expect(screen.queryByText('998998887766')).toBeNull());
    expect((await client.listBlacklist({})).items.some((b) => b.number === '998998887766')).toBe(false);
  });

  it("operator — faqat o'qiydi, qo'shish/o'chirish bo'lmaydi", async () => {
    await loginAs(client, 'operator');
    renderPage(<BlacklistPage />);

    expect(await screen.findByText(/ruxsati yo/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: "Qoʻshish" })).toBeNull();
    const toggle = screen.getByRole('switch', { name: 'Yashirin/anonim raqamlarni bloklash' });
    expect(toggle).toBeDisabled();
  });
});
