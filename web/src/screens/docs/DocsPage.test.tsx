// Qo'llanma interfeys tilida ko'rsatiladi va til almashganda darhol tarjimaga o'tadi.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, screen, within } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';
import i18n from '@/lib/i18n';
import { useSession } from '@/api/session';
import { createFakeClient } from '@/api/fake';
import { loginAs, renderPage } from '@/test-pages';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { DocsPage } = await import('./DocsPage');

const renderDoc = (route: string) =>
  renderPage(<Routes><Route path="/docs/:id?" element={<DocsPage />} /></Routes>, route);

describe('DocsPage — til', () => {
  afterEach(async () => {
    await act(() => i18n.changeLanguage('uz'));
    useSession.getState().clear();
  });

  it('bo\'lim interfeys tilida ochiladi va til almashsa tarjimaga o\'tadi', async () => {
    await loginAs(client, 'admin');
    await act(() => i18n.changeLanguage('ru'));
    renderDoc('/docs/trunks');
    expect(screen.getByRole('heading', { level: 1, name: /Транк/i })).toBeInTheDocument();

    await act(() => i18n.changeLanguage('en'));
    expect(screen.getByRole('heading', { level: 1, name: /Trunk/i })).toBeInTheDocument();
    expect(screen.queryByText(/available in Uzbek only/i)).not.toBeInTheDocument();
  });

  it('mundarija ham tanlangan tilda', async () => {
    await loginAs(client, 'admin');
    await act(() => i18n.changeLanguage('en'));
    renderDoc('/docs');
    const toc = screen.getByRole('navigation', { name: 'Guide contents' });
    expect(within(toc).getByRole('link', { name: 'Inbound routes' })).toBeInTheDocument();
  });
});
