// Xatti-harakat testi — sozlamalar, jonli roʻyxat, operator faqat o'qiydi. Qarang ../../../replica/m9-freepbx-gaps-contract.md §A3.
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

const { ParkingPage } = await import('./ParkingPage');

describe('ParkingPage', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('sozlamalar va jonli parklangan qoʻngʻiroq koʻrinadi', async () => {
    renderPage(<ParkingPage />);
    expect(await screen.findByDisplayValue('700')).toBeTruthy();
    expect(await screen.findByText('998901112233')).toBeTruthy();
  });

  it('lot kodini oʻzgartirib saqlash', async () => {
    const user = userEvent.setup();
    renderPage(<ParkingPage />);
    const lotInput = await screen.findByDisplayValue('700');
    await user.clear(lotInput);
    await user.type(lotInput, '750');
    await user.click(screen.getByRole('button', { name: 'Saqlash' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Saqlash' })).not.toBeDisabled());
    expect(await screen.findByDisplayValue('750')).toBeTruthy();
  });

  it('operator — faqat oʻqiydi, saqlash tugmasi yoʻq', async () => {
    await loginAs(client, 'operator');
    renderPage(<ParkingPage />);
    expect(await screen.findByText(/ruxsati yo/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Saqlash' })).toBeNull();
  });
});
