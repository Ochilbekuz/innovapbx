// Xatti-harakat testi — S18 kampaniyalar: seed ro'yxati, detal panel (statistika + kontaktlar), yangi kampaniya.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { CampaignsPage } = await import('./CampaignsPage');

describe('CampaignsPage', () => {
  afterEach(() => useSession.getState().clear());

  it('seed kampaniyalari holat va jadval bilan ko\'rinadi; qatorni ochsa — kontaktlar', async () => {
    await loginAs(client, 'admin');
    renderPage(<CampaignsPage />);

    const row = (await screen.findByText('Qarzdorlik eslatmasi — oktyabr')).closest('tr');
    expect(row).toBeTruthy();
    expect(within(row as HTMLElement).getByText('Tugadi')).toBeTruthy();
    expect(screen.getByText('Pauzada')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Qarzdorlik eslatmasi — oktyabr' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('Tugagan kampaniyaga raqam qoʻshilmaydi — yangisini yarating.')).toBeTruthy();
    expect(await within(dialog).findByText('998998887766')).toBeTruthy();
    expect(within(dialog).getAllByText('Qora roʻyxatda', { exact: false }).length).toBeGreaterThan(0);
  });

  it('yangi kampaniya — audiosiz yaratilmaydi (server xatosi maydon ostida)', async () => {
    await loginAs(client, 'admin');
    renderPage(<CampaignsPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Yangi kampaniya' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText(/Nomi/), { target: { value: 'Sinov kampaniya' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Yaratish' }));
    await waitFor(() => expect(within(dialog).getAllByText(/audio/i).length).toBeGreaterThan(1));
    expect(screen.queryByText('Kampaniya yaratildi — endi raqamlarni yuklang')).toBeNull();
  });
});
