// Xatti-harakat testi — qoʻngʻiroqlar tarixida yozuv (tinglash/yuklab olish) jadvalning OXIRGI ustunida.
import { describe, expect, it, afterEach, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { CallsPage } = await import('./CallsPage');

// `fakeSeed.ts`dagi demo qoʻngʻiroqlar qotgan sanaga bogʻlangan (2026-10-27 atrofida) — sukut
// filtr esa doim "bugundan 7 kun orqaga" (haqiqiy soatga bogʻliq). Vaqt oʻtishi bilan demo
// yozuvlar oynadan chiqib ketmasligi uchun "Boshlanishi"ni ataylab kengaytiramiz.
function widenDateRange() {
  fireEvent.change(screen.getByLabelText('Boshlanishi'), { target: { value: '2026-10-01' } });
}

describe('CallsPage', () => {
  afterEach(() => useSession.getState().clear());

  it('«Yozuv» — oxirgi ustun, yozilgan qoʻngʻiroqda tinglash va yuklab olish tugmalari bor', async () => {
    await loginAs(client, 'admin');
    renderPage(<CallsPage />);
    widenDateRange();

    const plays = await screen.findAllByTestId(/^recording-play-/);
    const headers = screen.getAllByRole('columnheader').map((h) => h.textContent?.trim());
    expect(headers.at(-1)).toBe('Yozuv');

    const first = plays[0] as HTMLElement;
    const row = first.closest('tr') as HTMLTableRowElement;
    const lastCell = row.cells[row.cells.length - 1] as HTMLTableCellElement;
    expect(lastCell.contains(first)).toBe(true);
    expect(lastCell.querySelector('[data-testid^="recording-download-"]')).not.toBeNull();
  });

  it('boshlanish/tugash soat:daqiqasi Toshkent vaqtida API ga ketadi', async () => {
    const spy = vi.spyOn(client, 'listCalls');
    await loginAs(client, 'admin');
    renderPage(<CallsPage />);
    widenDateRange();
    await screen.findAllByTestId(/^recording-play-/);

    const fromTime = screen.getByLabelText('Boshlanish vaqti (soat:daqiqa)') as HTMLInputElement;
    expect(fromTime.value).toBe('00:00');
    expect((screen.getByLabelText('Tugash vaqti (soat:daqiqa)') as HTMLInputElement).value).toBe('23:59');
    fireEvent.change(fromTime, { target: { value: '09:30' } });
    await waitFor(() => expect(spy.mock.calls.at(-1)?.[0]?.from).toMatch(/T04:30:00\.000Z$/));
    expect(spy.mock.calls.at(-1)?.[0]?.to).toMatch(/T18:59:59\.999Z$/);
    spy.mockRestore();
  });

  it('«Kengaytirilgan qidiruv» tugmasi bosilganda panel ochiladi', async () => {
    const user = userEvent.setup();
    await loginAs(client, 'admin');
    renderPage(<CallsPage />);
    widenDateRange();
    await screen.findAllByTestId(/^recording-play-/);

    expect(screen.queryByTestId('advanced-search-panel')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Kengaytirilgan qidiruv' }));
    expect(screen.getByTestId('advanced-search-panel')).toBeTruthy();
    expect(screen.getByLabelText('Kimdan (src)')).toBeTruthy();
  });

  it('src boʻyicha aniq qidiruv — faqat mos keluvchi qatorni qoldiradi, ism koʻrsatiladi', async () => {
    const user = userEvent.setup();
    await loginAs(client, 'admin');
    renderPage(<CallsPage />);
    widenDateRange();
    await screen.findAllByTestId(/^recording-play-/);

    await user.click(screen.getByRole('button', { name: 'Kengaytirilgan qidiruv' }));
    const panel = screen.getByTestId('advanced-search-panel');

    await user.click(within(panel).getByRole('combobox', { name: 'Kimdan (src) — moslik rejimi' }));
    await user.click(await screen.findByRole('option', { name: 'aniq mos' }));
    await user.type(within(panel).getByLabelText('Kimdan (src)'), '998901000000');
    await user.click(within(panel).getByRole('button', { name: 'Qidirish' }));

    await screen.findByText('Anvar Yusupov');
    await waitFor(() => {
      const dataRows = screen.getAllByRole('row').filter((r) => within(r).queryAllByRole('cell').length > 0);
      expect(dataRows).toHaveLength(1);
    });
  });

  it('qidiruvni shablon sifatida saqlash, tozalash va qayta qoʻllash', async () => {
    const user = userEvent.setup();
    await loginAs(client, 'admin');
    renderPage(<CallsPage />);
    widenDateRange();
    await screen.findAllByTestId(/^recording-play-/);

    await user.click(screen.getByRole('button', { name: 'Kengaytirilgan qidiruv' }));
    const panel = screen.getByTestId('advanced-search-panel');

    await user.type(within(panel).getByLabelText('Kimdan (src)'), '998901000000');
    await user.type(within(panel).getByLabelText('Joriy qidiruvni saqlash'), 'VIP qidiruv');
    await user.click(within(panel).getByRole('button', { name: 'Saqlash' }));

    await user.click(within(panel).getByRole('button', { name: 'Tozalash' }));
    expect(within(panel).getByLabelText('Kimdan (src)')).toHaveValue('');

    await user.click(within(panel).getByRole('combobox', { name: 'Saqlangan shablon' }));
    await user.click(await screen.findByRole('option', { name: 'VIP qidiruv' }));
    await user.click(within(panel).getByRole('button', { name: 'Qoʻllash' }));

    expect(within(panel).getByLabelText('Kimdan (src)')).toHaveValue('998901000000');
    expect(await screen.findByText('Anvar Yusupov')).toBeTruthy();
  });
});
