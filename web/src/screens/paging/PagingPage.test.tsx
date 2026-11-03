// Xatti-harakat testi — ro'yxat, tahrirlash, operator faqat o'qiydi. Qarang ../../../replica/m9-freepbx-gaps-contract.md §A4.
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

const { PagingPage } = await import('./PagingPage');

describe('PagingPage', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('ro\'yxatda mavjud guruh ko\'rinadi', async () => {
    renderPage(<PagingPage />);
    expect(await screen.findByText('Butun ofis')).toBeTruthy();
    expect(screen.getByText('800')).toBeTruthy();
  });

  it('nomni tahrirlash — saqlanadi', async () => {
    const user = userEvent.setup();
    renderPage(<PagingPage />);

    await user.click(await screen.findByRole('button', { name: /Butun ofisni tahrirlash/ }));
    const nameInput = await screen.findByRole('textbox', { name: 'Nom' });
    await user.clear(nameInput);
    await user.type(nameInput, 'Butun ofis (yangi)');
    await user.click(screen.getByRole('button', { name: 'Saqlash' }));

    await waitFor(() => expect(screen.queryByRole('textbox', { name: 'Nom' })).toBeNull());
    expect(await screen.findByText('Butun ofis (yangi)')).toBeTruthy();
  });

  it('operator — faqat o\'qiydi, yangi guruh tugmasi yo\'q', async () => {
    await loginAs(client, 'operator');
    renderPage(<PagingPage />);
    expect(await screen.findByText(/ruxsati yo/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Yangi guruh' })).toBeNull();
  });
});
