// Regressiya: `useAuthBootstrap` to'liq sahifa yuklanishida (saqlangan refresh token bilan)
// CHEKSIZ `/auth/refresh` tsiklga tushib qolgan edi (haqiqiy Playwright sinovida topildi —
// zustand `refresh` maydoni effekt bog'liqligida bo'lib, har bir token aylanishi effektni
// qaytadan ishga tushirgan). Bu test `apiClient.refresh` chaqiruvi SONINI tekshiradi —
// bir martadan ko'p bo'lsa — regressiya qaytgan.
import { describe, expect, it, vi, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useSession } from '@/api/session';

const refreshMock = vi.fn(async (token: string) => ({ access: `access-for-${token}`, refresh: `rotated-${token}` }));
const meMock = vi.fn(async () => ({
  id: 'u-1', login: 'admin', full_name: 'Admin', role: 'admin' as const, permissions: ['pbx.manage'], language: 'uz' as const,
}));

vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: { ...actual.apiClient, refresh: refreshMock, me: meMock } };
});
vi.mock('@/api/queries', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/queries')>();
  return { ...actual, useSetupState: () => ({ data: { needed: false }, isLoading: false, isError: false }) };
});

// Mocklangan modullar import qilingandan KEYIN import qilinishi kerak (vi.mock hoisting bilan ishlaydi).
const { useAuthBootstrap } = await import('./useAuthBootstrap');

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe('useAuthBootstrap — refresh tokeni aylanishi cheksiz tsikl yaratmasligi kerak', () => {
  afterEach(() => {
    useSession.getState().clear();
    refreshMock.mockClear();
    meMock.mockClear();
  });

  it('saqlangan refresh token bilan — apiClient.refresh FAQAT bir marta chaqiriladi', async () => {
    window.localStorage.setItem('innova.refresh', 'eski-refresh');
    useSession.setState({ refresh: 'eski-refresh', access: null, user: null });

    const { result } = renderHook(() => useAuthBootstrap(), { wrapper });

    await waitFor(() => expect(result.current.ready).toBe(true));
    // Bir oz ko'proq kutamiz — agar tsikl bo'lsa, shu oraliqda qo'shimcha chaqiruvlar ko'rinadi.
    await new Promise((r) => setTimeout(r, 100));

    expect(refreshMock).toHaveBeenCalledTimes(1);
    expect(meMock).toHaveBeenCalledTimes(1);
    expect(useSession.getState().user?.login).toBe('admin');
  });
});
