// Xatti-harakat testi — ro'yxat, tahrirlash, operator faqat o'qiydi. Qarang ../../../replica/m9-freepbx-gaps-contract.md §A1.
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { AnnouncementsPage } = await import('./AnnouncementsPage');

describe('AnnouncementsPage', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('ro\'yxatda mavjud e\'lon ko\'rinadi', async () => {
    renderPage(<AnnouncementsPage />);
    const row = (await screen.findByText('Tushlik tanaffusi')).closest('tr');
    expect(row).toBeTruthy();
    expect(row && within(row).getByText('Ish vaqti')).toBeTruthy();
  });

  it('nomni tahrirlash — saqlanadi', async () => {
    const user = userEvent.setup();
    renderPage(<AnnouncementsPage />);

    await user.click(await screen.findByRole('button', { name: /Tushlik tanaffusini tahrirlash/ }));
    const nameInput = await screen.findByRole('textbox', { name: 'Nom' });
    await user.clear(nameInput);
    await user.type(nameInput, 'Tushlik vaqti eʼloni');
    await user.click(screen.getByRole('button', { name: 'Saqlash' }));

    await waitFor(() => expect(screen.queryByRole('textbox', { name: 'Nom' })).toBeNull());
    expect(await screen.findByText('Tushlik vaqti eʼloni')).toBeTruthy();
  });

  it('operator — faqat o\'qiydi, yangi e\'lon tugmasi yo\'q', async () => {
    await loginAs(client, 'operator');
    renderPage(<AnnouncementsPage />);
    expect(await screen.findByText(/ruxsati yo/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: "Yangi eʼlon" })).toBeNull();
  });
});
