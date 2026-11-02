// Sahifa (screen) darajasidagi xatti-harakat testlari uchun umumiy yordamchi — AppShell marshrutizator
// (`react-router-dom`) va TanStack Query'ga tayanadi, shuning uchun har bir test shu ikkisini o'raydi.
// `vi.mock('@/api', ...)` har bir test faylida o'zi chaqirilishi kerak (hoisting tufayli bu yerdan eksport
// qilib bo'lmaydi) — odatda `{ ...actual, apiClient: createFakeClient() }` bilan yangi, mustaqil fake klient.
import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { render } from '@testing-library/react';
import type { ApiClient } from '@/api/client';
import { useSession } from '@/api/session';
import { SEED_ADMIN, SEED_ADMIN_PASSWORD, SEED_OPERATOR, SEED_OPERATOR_PASSWORD } from '@/api/fakeSeed';

/** Yangi `QueryClient` (retry'siz) + `MemoryRouter` bilan render — sahifalar `AppShell` ichida navigatsiyaga tayanadi. */
export function renderPage(children: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>,
  );
}

/**
 * Berilgan (test uchun yaratilgan) fake klientga admin/operator sifatida "kiradi": klientning ichki
 * `currentUser`'ini (server tomoni ruxsat tekshiruvi uchun) VA `useSession` doʻkonini (`usePermission` /
 * UI uchun) bitta chaqiruvda sozlaydi.
 */
export async function loginAs(client: ApiClient, role: 'admin' | 'operator') {
  const { login, password } = role === 'admin'
    ? { login: SEED_ADMIN.login, password: SEED_ADMIN_PASSWORD }
    : { login: SEED_OPERATOR.login, password: SEED_OPERATOR_PASSWORD };
  const res = await client.login(login, password);
  useSession.setState({ access: res.access, refresh: res.refresh, user: res.user });
  return res.user;
}
