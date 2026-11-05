// Xatti-harakat testi — Kirish (SSH va veb-panel) sahifasi (S50, M12 B4): seed holat, login buyrugʻi,
// 422 maydon xatolari, SSH port oʻzgartirish → pending → tasdiqlash, veb-panel portini oʻzgartirish →
// tasdiqlash modali → redirect. Qarang NetworkPage.test.tsx uslubi.
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

const navigateTo = vi.fn();
vi.mock('@/lib/browser', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/browser')>();
  return { ...actual, navigateTo };
});

const { AccessPage } = await import('./AccessPage');

describe('AccessPage', () => {
  afterEach(() => { useSession.getState().clear(); navigateTo.mockClear(); });

  it('seed SSH holatini va login buyrugʻini koʻrsatadi', async () => {
    await loginAs(client, 'admin');
    renderPage(<AccessPage />);
    const main = within(await screen.findByRole('main'));

    expect(await main.findByText('Ishlayapti')).toBeTruthy();
    expect(main.getByText(/Joriy port.*22/)).toBeTruthy();
    expect(main.getByText('ssh -p 22 innova@localhost')).toBeTruthy();
  });

  it('band portni kiritganda 422 maydon xatosi koʻrsatiladi', async () => {
    const user = userEvent.setup();
    await loginAs(client, 'admin');
    renderPage(<ToastProvider><AccessPage /></ToastProvider>);
    const main = within(await screen.findByRole('main'));

    const portInput = await main.findByLabelText('Yangi SSH port');
    const sshForm = portInput.closest('form') as HTMLElement;
    await user.clear(portInput);
    await user.type(portInput, '5060');
    await user.click(within(sshForm).getByRole('button', { name: 'Qoʻllash' }));

    expect(await main.findByText(/boshqa xizmat uchun band/)).toBeTruthy();
  });

  it('SSH portini oʻzgartirish — pending banner, tasdiqlagandan keyin yangi port qoladi', async () => {
    const user = userEvent.setup();
    await loginAs(client, 'admin');
    renderPage(<ToastProvider><AccessPage /></ToastProvider>);
    const main = within(await screen.findByRole('main'));

    const portInput = await main.findByLabelText('Yangi SSH port');
    const sshForm = portInput.closest('form') as HTMLElement;
    await user.clear(portInput);
    await user.type(portInput, '2222');
    await user.click(within(sshForm).getByRole('button', { name: 'Qoʻllash' }));

    await main.findByText('Oʻzgarish kutilmoqda');
    expect(main.getAllByText(/ssh -p 2222 innova@localhost/).length).toBeGreaterThan(0);

    await user.click(main.getByRole('button', { name: 'Tasdiqlash' }));
    await waitFor(() => expect(main.queryByText('Oʻzgarish kutilmoqda')).toBeNull());
    expect(await main.findByText(/Joriy port.*2222/)).toBeTruthy();
  }, 10_000);

  it('veb-panel portini oʻzgartirish — tasdiqlash modali, tasdiqlagandan keyin yoʻnaltiradi', async () => {
    const user = userEvent.setup();
    await loginAs(client, 'admin');
    renderPage(<ToastProvider><AccessPage /></ToastProvider>);
    const main = within(await screen.findByRole('main'));

    const httpInput = await main.findByLabelText('HTTP port');
    const webForm = httpInput.closest('form') as HTMLElement;
    await user.clear(httpInput);
    await user.type(httpInput, '8080');
    await user.click(within(webForm).getByRole('button', { name: 'Qoʻllash' }));

    const dialog = await screen.findByRole('dialog', { name: 'Veb-panel manzili oʻzgaradi' });
    expect(within(dialog).getByText(/http:\/\/localhost:8080/)).toBeTruthy();
    await user.click(within(dialog).getByRole('button', { name: 'Qoʻllash' }));

    await waitFor(() => expect(navigateTo).toHaveBeenCalledWith(expect.stringContaining('http://localhost:8080/access-confirm#')));
  }, 10_000);
});
