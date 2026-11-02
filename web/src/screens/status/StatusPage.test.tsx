// Xatti-harakat testi — Tizim holati (S36): disk, tranklar, internet, SIP kartalari + diskni tozalash
// modali (preview va o'chirish). Qarang CallsPage.test.tsx/BackupPage.test.tsx uslubi.
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

const { StatusPage } = await import('./StatusPage');

function section(heading: string): HTMLElement {
  return screen.getByRole('heading', { name: heading }).closest('section') as HTMLElement;
}

describe('StatusPage', () => {
  afterEach(() => useSession.getState().clear());

  it('disk, tranklar, internet va SIP kartalari seed maʼlumotlariga mos koʻrinadi', async () => {
    await loginAs(client, 'admin');
    renderPage(<StatusPage />);

    await screen.findByRole('button', { name: 'Diskni tozalash' });
    const diskSection = section('Disk');
    expect(within(diskSection).getByRole('progressbar')).toHaveAttribute('aria-valuenow');

    const sipSection = section('SIP interfeysi');
    expect(within(sipSection).getByText('UDP')).toBeTruthy();
    expect(within(sipSection).getByText('TCP')).toBeTruthy();
    expect(within(sipSection).getAllByText('0.0.0.0:5060')).toHaveLength(2);

    const internetSection = section('Internet');
    expect(within(internetSection).getByText(/18/)).toBeTruthy();
  }, 10_000);

  it(
    'diskni tozalash — oldindan koʻrish hisoblanadi va "O\'chirish" bilan haqiqatan oʻchiradi',
    async () => {
      const user = userEvent.setup();
      await loginAs(client, 'admin');
      renderPage(<ToastProvider><StatusPage /></ToastProvider>);

      await user.click(await screen.findByRole('button', { name: 'Diskni tozalash' }));
      const dialog = await screen.findByRole('dialog', { name: 'Diskni tozalash' });

      await waitFor(() => expect(within(dialog).getByText(/Boʻshaydi:/)).toBeTruthy(), { timeout: 3000 });

      const deleteBtn = within(dialog).getByRole('button', { name: 'Oʻchirish' });
      expect(deleteBtn).not.toBeDisabled();
      await user.click(deleteBtn);

      await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Diskni tozalash' })).toBeNull());
      expect(await screen.findByText(/ozod qilindi/)).toBeTruthy();
    },
    10_000,
  );

  it('hech narsa tanlanmasa "Oʻchirish" oʻchirilgan boʻladi', async () => {
    const user = userEvent.setup();
    await loginAs(client, 'admin');
    renderPage(<ToastProvider><StatusPage /></ToastProvider>);

    await user.click(await screen.findByRole('button', { name: 'Diskni tozalash' }));
    const dialog = await screen.findByRole('dialog', { name: 'Diskni tozalash' });

    await user.click(within(dialog).getByRole('checkbox', { name: /yozuvlar/i }));
    await user.click(within(dialog).getByRole('checkbox', { name: /zaxira/i }));

    expect(within(dialog).getByRole('button', { name: 'Oʻchirish' })).toBeDisabled();
  });
});
