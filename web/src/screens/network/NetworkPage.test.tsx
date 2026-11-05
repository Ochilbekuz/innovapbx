// Xatti-harakat testi — Tarmoq sahifasi (S38, M8): seed holat, interfeys sozlash → qo'llash → tasdiqlash/qaytarish,
// marshrut qo'shish/o'chirish, tekshiruv xatosi. Qarang StatusPage.test.tsx uslubi.
import { describe, expect, it, afterEach, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';
import { ToastProvider } from '@/ui/Toast';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { NetworkPage } = await import('./NetworkPage');

describe('NetworkPage', () => {
  afterEach(() => useSession.getState().clear());

  it('seed holatni koʻrsatadi: ens18 statik, ens19 dhcp, 1 statik marshrut', async () => {
    await loginAs(client, 'admin');
    renderPage(<NetworkPage />);

    await screen.findByRole('tab', { name: 'Umumiy' });
    expect(screen.getByDisplayValue('innova-pbx1')).toBeTruthy();

    await userEvent.setup().click(screen.getByRole('tab', { name: 'Interfeyslar' }));
    expect(screen.getByText('ens18')).toBeTruthy();
    expect(screen.getByText('ens19')).toBeTruthy();
    expect(screen.getByText('192.168.10.20/24')).toBeTruthy();

    await userEvent.setup().click(screen.getByRole('tab', { name: 'Statik marshrutlar' }));
    expect(screen.getAllByText('10.20.0.0/16').length).toBeGreaterThan(0);
    expect(screen.getAllByText('192.168.10.254').length).toBeGreaterThan(0);
  }, 10_000);

  it('«Ping» tabi marshrutlardan keyin — shlyuz preseti va host maydoni bor', async () => {
    await loginAs(client, 'admin');
    renderPage(<NetworkPage />);

    const tabs = await screen.findAllByRole('tab');
    expect(tabs.map((tab) => tab.textContent)).toEqual(['Umumiy', 'Interfeyslar', 'Statik marshrutlar', 'Ping']);
    await userEvent.setup().click(screen.getByRole('tab', { name: 'Ping' }));
    expect(screen.getByRole('button', { name: /^Shlyuz · / })).toBeTruthy();
    expect(screen.getByLabelText('Host')).toBeTruthy();
  });

  it(
    'host nomini oʻzgartirib qoʻllash — pending banner chiqadi, tasdiqlagandan keyin yoʻqoladi',
    async () => {
      const user = userEvent.setup();
      await loginAs(client, 'admin');
      renderPage(<ToastProvider><NetworkPage /></ToastProvider>);

      const hostnameInput = await screen.findByDisplayValue('innova-pbx1');
      await user.clear(hostnameInput);
      await user.type(hostnameInput, 'innova-pbx2');

      await user.click(await screen.findByRole('button', { name: 'Qoʻllash' }));
      const dialog = await screen.findByRole('dialog', { name: 'Oʻzgarishlarni qoʻllash' });
      expect(within(dialog).getByText(/innova-pbx1 → innova-pbx2/)).toBeTruthy();

      await user.click(within(dialog).getByRole('button', { name: 'Qoʻllash' }));
      await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Oʻzgarishlarni qoʻllash' })).toBeNull());

      await screen.findByText('Oʻzgarish kutilmoqda');
      await user.click(screen.getByRole('button', { name: 'Tasdiqlash' }));

      await waitFor(() => expect(screen.queryByText('Oʻzgarish kutilmoqda')).toBeNull());
      expect(await screen.findByDisplayValue('innova-pbx2')).toBeTruthy();
    },
    10_000,
  );

  it('notoʻgʻri CIDR bilan interfeysni statikka oʻtkazishda saqlash tugmasi oʻchiq boʻladi', async () => {
    const user = userEvent.setup();
    await loginAs(client, 'admin');
    renderPage(<NetworkPage />);

    await user.click(await screen.findByRole('tab', { name: 'Interfeyslar' }));
    const row = screen.getByText('ens19').closest('tr') as HTMLElement;
    await user.click(within(row).getByRole('button', { name: 'Sozlash' }));

    const dialog = await screen.findByRole('dialog', { name: /ens19/ });
    await user.click(within(dialog).getByRole('radio', { name: 'Statik' }));
    const addrInput = within(dialog).getByPlaceholderText('192.168.10.20/24');
    await user.type(addrInput, 'not-a-cidr');

    expect(within(dialog).getByRole('button', { name: 'Saqlash' })).toBeDisabled();
  });

  it('statik marshrut qoʻshish va oʻchirish', async () => {
    const user = userEvent.setup();
    await loginAs(client, 'admin');
    renderPage(<NetworkPage />);

    await user.click(await screen.findByRole('tab', { name: 'Statik marshrutlar' }));
    await user.click(screen.getByRole('button', { name: 'Marshrut qoʻshish' }));

    const dialog = await screen.findByRole('dialog', { name: 'Marshrut qoʻshish' });
    await user.type(within(dialog).getByPlaceholderText('10.20.0.0/16'), '172.16.0.0/16');
    await user.type(within(dialog).getByLabelText('Shlyuz'), '192.168.10.1');
    await user.click(within(dialog).getByRole('button', { name: 'Saqlash' }));

    expect(await screen.findByText('172.16.0.0/16')).toBeTruthy();
    expect(await screen.findByText(/1 ta oʻzgarish/)).toBeTruthy();

    const row = screen.getByText('172.16.0.0/16').closest('tr') as HTMLElement;
    await user.click(within(row).getByRole('button', { name: 'Oʻchirish' }));
    await waitFor(() => expect(screen.queryByText('172.16.0.0/16')).toBeNull());
  });
});
