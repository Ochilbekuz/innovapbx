// Xatti-harakat testi — 92 kundan uzun/teskari sana oralig'i mahalliy darajada rad etiladi, KPI raqamlari
// fake klient hisob-kitobiga mos keladi (M2b §5). Qarang ../../../replica/m2b-contract.md §5.
import { describe, expect, it, afterEach, vi } from 'vitest';
import { fireEvent, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { AnalyticsPage } = await import('./AnalyticsPage');

async function pickCustomRange(user: ReturnType<typeof userEvent.setup>, from: string, to: string) {
  await user.click(screen.getByRole('combobox', { name: 'Davr' }));
  await user.click(await screen.findByRole('option', { name: 'Boshqa' }));
  fireEvent.change(screen.getByLabelText('Boshlanishi'), { target: { value: from } });
  fireEvent.change(screen.getByLabelText('Tugashi'), { target: { value: to } });
}

describe('AnalyticsPage', () => {
  afterEach(() => useSession.getState().clear());

  it('teskari sana oraligʻi (from > to) mahalliy darajada rad etiladi — KPI/jadvallar yashiriladi', async () => {
    await loginAs(client, 'admin');
    const user = userEvent.setup();
    renderPage(<AnalyticsPage />);

    await pickCustomRange(user, '2026-10-20', '2026-10-01');

    expect(await screen.findByRole('alert')).toHaveTextContent(/notoʻgʻri/);
    expect(screen.queryByText('Jami qoʻngʻiroqlar')).toBeNull();
  });

  it('92 kundan uzun oraliq rad etiladi', async () => {
    await loginAs(client, 'admin');
    const user = userEvent.setup();
    renderPage(<AnalyticsPage />);

    await pickCustomRange(user, '2026-01-01', '2026-10-28');

    expect(await screen.findByRole('alert')).toHaveTextContent(/notoʻgʻri/);
  });

  it('KPI raqamlari seed maʼlumotiga mos keladi (jami 42, javob berilgan 21, oʻtkazib yuborilgan 7)', async () => {
    await loginAs(client, 'admin');
    const user = userEvent.setup();
    renderPage(<AnalyticsPage />);

    await pickCustomRange(user, '2026-08-01', '2026-10-28');

    const totalLabel = await screen.findByText('Jami qoʻngʻiroqlar');
    const grid = totalLabel.closest('div')!.parentElement!.parentElement!; // KPI kartasi > KPI panjarasi.
    const kpi = (label: string) => within(grid).getByText(label).closest('div')!.parentElement!;
    expect(await within(kpi('Jami qoʻngʻiroqlar')).findByText('42')).toBeTruthy();
    expect(await within(kpi('Javob berilgan')).findByText('21')).toBeTruthy();
    expect(await within(kpi('Oʻtkazib yuborilgan')).findByText('7')).toBeTruthy();
  });
});
