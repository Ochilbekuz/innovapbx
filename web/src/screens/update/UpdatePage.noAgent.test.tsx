// Xatti-harakat testi — Paneldan yangilash: agent oʻrnatilmagan holat (dev muhiti), M11 §5.
import { describe, expect, it, afterEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';

const client = createFakeClient({ updateAgent: false });
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { UpdatePage } = await import('./UpdatePage');

describe('UpdatePage — agent yoʻq', () => {
  afterEach(() => useSession.getState().clear());

  it('agent topilmasa izohli boʻsh holat va CLI yoʻriqnomasi koʻrsatiladi', async () => {
    await loginAs(client, 'admin');
    renderPage(<UpdatePage />);

    await screen.findByText("Paneldan yangilash o'rnatilmagan");
    expect(screen.getByText('sudo innova-update')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Tekshirish' })).toBeNull();
  }, 10_000);
});
