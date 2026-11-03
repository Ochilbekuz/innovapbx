// Xatti-harakat testi — ro'yxat, tahrirlash, PIN qo'shish, operator faqat o'qiydi. Qarang ../../../replica/m9-freepbx-gaps-contract.md §B1.
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

const { PinSetsPage } = await import('./PinSetsPage');

describe('PinSetsPage', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('ro\'yxatda mavjud toʻplam koʻrinadi', async () => {
    renderPage(<PinSetsPage />);
    expect(await screen.findByText('Xalqaro qoʻngʻiroqlar')).toBeTruthy();
  });

  it('PINlar oynasida yangi PIN qoʻshish ishlaydi', async () => {
    const user = userEvent.setup();
    renderPage(<PinSetsPage />);

    await user.click(await screen.findByRole('button', { name: /Xalqaro qoʻngʻiroqlar: PINlarni boshqarish/ }));
    const textarea = await screen.findByPlaceholderText(/1234;Direktor/);
    await user.type(textarea, '9999;Mehmon');
    await user.click(screen.getByRole('button', { name: 'Qoʻshish' }));

    expect(await screen.findByText('Mehmon')).toBeTruthy();
  });

  it('nomni tahrirlash — saqlanadi', async () => {
    const user = userEvent.setup();
    renderPage(<PinSetsPage />);

    await user.click(await screen.findByRole('button', { name: /Xalqaro qoʻngʻiroqlarni tahrirlash/ }));
    const nameInput = await screen.findByRole('textbox', { name: 'Nom' });
    await user.clear(nameInput);
    await user.type(nameInput, 'Xalqaro (yangi)');
    await user.click(screen.getByRole('button', { name: 'Saqlash' }));

    await waitFor(() => expect(screen.queryByRole('textbox', { name: 'Nom' })).toBeNull());
    expect(await screen.findByText('Xalqaro (yangi)')).toBeTruthy();
  });

  it('operator — faqat o\'qiydi, yangi toʻplam tugmasi yoʻq', async () => {
    await loginAs(client, 'operator');
    renderPage(<PinSetsPage />);
    expect(await screen.findByText(/ruxsati yo/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Yangi toʻplam' })).toBeNull();
  });
});
