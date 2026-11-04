// Xatti-harakat testi — Paneldan yangilash: yangi versiya yoʻq holati (M11 §5 — "upToDate").
import { describe, expect, it, afterEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';

const client = createFakeClient({ updateAvailable: false });
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { UpdatePage } = await import('./UpdatePage');

describe('UpdatePage — yangi versiya yoʻq', () => {
  afterEach(() => useSession.getState().clear());

  it('"eng soʻnggi versiyadasiz" xabari koʻrinadi, changelog va "Yangilash" tugmasi yoʻq', async () => {
    await loginAs(client, 'admin');
    renderPage(<UpdatePage />);

    await screen.findByText('1.0.12');
    expect(screen.getByText('Siz eng so‘nggi versiyadasiz.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Yangilash' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Tekshirish' })).toBeTruthy();
  }, 10_000);
});
