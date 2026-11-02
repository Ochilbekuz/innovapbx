// Xatti-harakat testi — zaxiradan tiklangach login xabari (M4b): `clear(notice)` dan keyin `RequireAuth`
// o'zi (state'siz) `/login`ga yo'naltirsa ham xabar ko'rinishi, muvaffaqiyatli kirishda esa o'chishi shart.
import { describe, expect, it, afterEach, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs } from '@/test-pages';
import { SEED_ADMIN, SEED_ADMIN_PASSWORD } from '@/api/fakeSeed';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { LoginPage } = await import('./LoginPage');
const { RequireAuth, RedirectIfAuthed } = await import('@/auth/guards');

const NOTICE = 'Tizim zaxiradan tiklandi — qaytadan kiring.';

function renderAt(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } });
  queryClient.setQueryData(['setup-state'], { needed: false });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/login" element={<RedirectIfAuthed><LoginPage /></RedirectIfAuthed>} />
          <Route path="/dashboard" element={<RequireAuth><div>Boshqaruv paneli</div></RequireAuth>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('LoginPage — tiklashdan keyingi xabar', () => {
  afterEach(() => useSession.getState().clear());

  it('RequireAuth yo‘naltirsa ham xabar ko‘rinadi', async () => {
    await loginAs(client, 'admin');
    renderAt('/dashboard');
    expect(await screen.findByText('Boshqaruv paneli')).toBeInTheDocument();

    act(() => useSession.getState().clear(NOTICE));

    expect(await screen.findByRole('status')).toHaveTextContent(NOTICE);
  });

  it('muvaffaqiyatli kirishda xabar o‘chadi', async () => {
    useSession.getState().clear(NOTICE);
    renderAt('/login');
    expect(await screen.findByRole('status')).toHaveTextContent(NOTICE);

    await userEvent.type(screen.getByLabelText(/Login/), SEED_ADMIN.login);
    await userEvent.type(screen.getByLabelText(/Parol/), SEED_ADMIN_PASSWORD);
    await userEvent.click(screen.getByRole('button', { name: /Kirish/ }));

    expect(await screen.findByText('Boshqaruv paneli')).toBeInTheDocument();
    expect(useSession.getState().notice).toBeNull();
  });
});
