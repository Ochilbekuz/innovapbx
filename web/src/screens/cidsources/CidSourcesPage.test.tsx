// Xatti-harakat testi — ro'yxat, tahrirlash, sinash, operator faqat o'qiydi. Qarang ../../../replica/m9-freepbx-gaps-contract.md §B2.
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

const { CidSourcesPage } = await import('./CidSourcesPage');

describe('CidSourcesPage', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('ro\'yxatda mavjud manba koʻrinadi', async () => {
    renderPage(<CidSourcesPage />);
    expect(await screen.findByText('Telefon kitobi')).toBeTruthy();
  });

  it('sinash — raqam topilganda natija koʻrsatadi', async () => {
    const user = userEvent.setup();
    renderPage(<CidSourcesPage />);

    await user.click(await screen.findByRole('button', { name: /Telefon kitobini sinash/ }));
    const numberInput = await screen.findByRole('textbox', { name: 'Sinov raqami' });
    await user.type(numberInput, '998901112233');
    await user.click(screen.getByRole('button', { name: 'Ishga tushirish' }));

    expect(await screen.findByText(/Topildi:|Topilmadi/)).toBeTruthy();
  });

  it('nomni tahrirlash — saqlanadi', async () => {
    const user = userEvent.setup();
    renderPage(<CidSourcesPage />);

    await user.click(await screen.findByRole('button', { name: /Telefon kitobini tahrirlash/ }));
    const nameInput = await screen.findByRole('textbox', { name: 'Nom' });
    await user.clear(nameInput);
    await user.type(nameInput, 'Telefon kitobi (yangi)');
    await user.click(screen.getByRole('button', { name: 'Saqlash' }));

    await waitFor(() => expect(screen.queryByRole('textbox', { name: 'Nom' })).toBeNull());
    expect(await screen.findByText('Telefon kitobi (yangi)')).toBeTruthy();
  });

  it('operator — faqat o\'qiydi, yangi manba tugmasi yoʻq', async () => {
    await loginAs(client, 'operator');
    renderPage(<CidSourcesPage />);
    expect(await screen.findByText(/ruxsati yo/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Yangi manba' })).toBeNull();
  });
});
