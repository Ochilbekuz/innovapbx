// Xatti-harakat testi — ro'yxat, tahrirlash, operator faqat o'qiydi. Qarang ../../../replica/m9-freepbx-gaps-contract.md §B2.
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

const { PhonebookPage } = await import('./PhonebookPage');

describe('PhonebookPage', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('ro\'yxatda mavjud kontakt ko\'rinadi', async () => {
    renderPage(<PhonebookPage />);
    expect(await screen.findByText('Oqiljon Rustamov')).toBeTruthy();
    expect(screen.getByText('Dildora Ergasheva')).toBeTruthy();
  });

  it('nomni tahrirlash — saqlanadi', async () => {
    const user = userEvent.setup();
    renderPage(<PhonebookPage />);

    await user.click(await screen.findByRole('button', { name: /Oqiljon Rustamovni tahrirlash/ }));
    const nameInput = await screen.findByRole('textbox', { name: 'Nom' });
    await user.clear(nameInput);
    await user.type(nameInput, 'Oqiljon R.');
    await user.click(screen.getByRole('button', { name: 'Saqlash' }));

    await waitFor(() => expect(screen.queryByRole('textbox', { name: 'Nom' })).toBeNull());
    expect(await screen.findByText('Oqiljon R.')).toBeTruthy();
  });

  it('operator — faqat o\'qiydi, yangi kontakt tugmasi yo\'q', async () => {
    await loginAs(client, 'operator');
    renderPage(<PhonebookPage />);
    expect(await screen.findByText(/ruxsati yo/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Yangi kontakt' })).toBeNull();
  });
});
