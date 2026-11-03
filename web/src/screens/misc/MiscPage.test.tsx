// Xatti-harakat testi — ikki tab, tahrirlash, operator faqat o'qiydi. Qarang ../../../replica/m9-freepbx-gaps-contract.md §A2.
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

const { MiscPage } = await import('./MiscPage');

describe('MiscPage', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('manzillar tabida mavjud yozuv koʻrinadi', async () => {
    renderPage(<MiscPage />);
    expect(await screen.findByText('Faks liniyasi')).toBeTruthy();
  });

  it('maxsus kodlar tabiga oʻtib mavjud kodni koʻrish', async () => {
    const user = userEvent.setup();
    renderPage(<MiscPage />);
    await user.click(await screen.findByRole('tab', { name: 'Maxsus kodlar' }));
    expect(await screen.findByText('Direktorga toʻgʻridan-toʻgʻri')).toBeTruthy();
    expect(screen.getByText('*501')).toBeTruthy();
  });

  it('manzil nomini tahrirlash — saqlanadi', async () => {
    const user = userEvent.setup();
    renderPage(<MiscPage />);

    await user.click(await screen.findByRole('button', { name: /Faks liniyasini tahrirlash/ }));
    const nameInput = await screen.findByRole('textbox', { name: 'Nom' });
    await user.clear(nameInput);
    await user.type(nameInput, 'Faks (yangi)');
    await user.click(screen.getByRole('button', { name: 'Saqlash' }));

    await waitFor(() => expect(screen.queryByRole('textbox', { name: 'Nom' })).toBeNull());
    expect(await screen.findByText('Faks (yangi)')).toBeTruthy();
  });

  it('operator — faqat oʻqiydi, yangi manzil tugmasi yoʻq', async () => {
    await loginAs(client, 'operator');
    renderPage(<MiscPage />);
    expect(await screen.findByText(/ruxsati yo/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Yangi manzil' })).toBeNull();
  });
});
