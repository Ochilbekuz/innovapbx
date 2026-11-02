// Xatti-harakat testi — qoʻngʻiroqlar tarixida yozuv (tinglash/yuklab olish) jadvalning OXIRGI ustunida.
import { describe, expect, it, afterEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { CallsPage } = await import('./CallsPage');

describe('CallsPage', () => {
  afterEach(() => useSession.getState().clear());

  it('«Yozuv» — oxirgi ustun, yozilgan qoʻngʻiroqda tinglash va yuklab olish tugmalari bor', async () => {
    await loginAs(client, 'admin');
    renderPage(<CallsPage />);

    const plays = await screen.findAllByTestId(/^recording-play-/);
    const headers = screen.getAllByRole('columnheader').map((h) => h.textContent?.trim());
    expect(headers.at(-1)).toBe('Yozuv');

    const first = plays[0] as HTMLElement;
    const row = first.closest('tr') as HTMLTableRowElement;
    const lastCell = row.cells[row.cells.length - 1] as HTMLTableCellElement;
    expect(lastCell.contains(first)).toBe(true);
    expect(lastCell.querySelector('[data-testid^="recording-download-"]')).not.toBeNull();
  });
});
