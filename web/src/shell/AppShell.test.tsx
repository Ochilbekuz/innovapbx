// Yig'iladigan menyu (M8 §6): guruh sarlavhasi tugma, holat `localStorage['innova.nav.collapsed']`'da
// saqlanadi, faol ekran guruhi doim ochiq qoladi.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';
import { loadCollapsedGroups } from './navCollapse';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { AppShellPage } = await import('./AppShellPage');

describe('AppShell — yig\'iladigan menyu', () => {
  afterEach(() => {
    useSession.getState().clear();
    localStorage.clear();
  });

  it('guruh tugmasi bosilsa — aria-expanded oʻchadi va localStorage ga yoziladi', async () => {
    const user = userEvent.setup();
    await loginAs(client, 'admin');
    renderPage(<AppShellPage title="Test">x</AppShellPage>);

    const header = await screen.findByRole('button', { name: /tizim/i });
    expect(header).toHaveAttribute('aria-expanded', 'true');

    await user.click(header);
    expect(header).toHaveAttribute('aria-expanded', 'false');
    expect(loadCollapsedGroups()).toContain('system');

    await user.click(header);
    expect(header).toHaveAttribute('aria-expanded', 'true');
    expect(loadCollapsedGroups()).not.toContain('system');
  });

  it('oldindan yopilgan guruh — localStorage dagi holatdan oʻqiladi', async () => {
    localStorage.setItem('innova.nav.collapsed', JSON.stringify(['system']));
    await loginAs(client, 'admin');
    renderPage(<AppShellPage title="Test">x</AppShellPage>);

    const header = await screen.findByRole('button', { name: /tizim/i });
    expect(header).toHaveAttribute('aria-expanded', 'false');
  });
});
