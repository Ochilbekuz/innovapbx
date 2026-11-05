// Xatti-harakat testi — Firewall sahifasi (S37, M12 B3): xizmat qatorlarida joriy SSH/veb-panel portlari
// koʻrsatiladi, "Kirish" sahifasiga havola bor. Qarang AccessPage.test.tsx uslubi.
import { describe, expect, it, afterEach, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';
import type { FirewallConfigIn } from '@/api/types';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { FirewallPage } = await import('./FirewallPage');

describe('FirewallPage', () => {
  afterEach(() => useSession.getState().clear());

  it('xizmat qatorlarida joriy SSH/veb-panel portlarini koʻrsatadi va Kirish sahifasiga havola beradi', async () => {
    await loginAs(client, 'admin');
    renderPage(<FirewallPage />);
    const main = within(await screen.findByRole('main'));

    expect(await main.findByText('Port: 22')).toBeTruthy();
    expect(main.getByText('HTTP: 80, HTTPS: 443')).toBeTruthy();

    const link = main.getByRole('link', { name: 'SSH va veb-panelga kirish sozlamalari' });
    expect(link.getAttribute('href')).toBe('/settings/access');
  });

  it('kutilayotgan oʻzgarish boʻlsa — pending banner koʻrinadi, tasdiqlagandan keyin yoʻqoladi', async () => {
    await loginAs(client, 'admin');
    const current = await client.firewallState();
    const payload: FirewallConfigIn = {
      services: current.services.map((s) => ({ name: s.name as FirewallConfigIn['services'][number]['name'], mode: s.mode as FirewallConfigIn['services'][number]['mode'], allow: s.allow })),
      blocked_cidrs: current.blocked_cidrs,
      timeout_s: 60,
    };
    await client.applyFirewall(payload);

    const user = userEvent.setup();
    renderPage(<FirewallPage />);
    const main = within(await screen.findByRole('main'));

    await main.findByText('Oʻzgarish kutilmoqda');
    await user.click(main.getByRole('button', { name: 'Tasdiqlash' }));
    await waitFor(() => expect(main.queryByText('Oʻzgarish kutilmoqda')).toBeNull());
  }, 10_000);
});
