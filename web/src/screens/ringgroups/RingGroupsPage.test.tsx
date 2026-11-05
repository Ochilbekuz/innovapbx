// 0038 (FreePBX Ring Groups parity) — yangi boʻlimlar (Jiringlash va eʼlonlar/Kengaytirilgan) va
// "Confirm calls" yoqilganda "Tasdiqlash eʼloni" maydoni koʻrinishi, hamda saqlash orqali
// yangi FreePBX maydonlari (skip_busy_agent, confirm_calls, recording_policy) haqiqatan saqlanishi.
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { RingGroupsPage } = await import('./RingGroupsPage');

describe('RingGroupsPage — FreePBX parity boʻlimlari', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('tahrirlash drawer besh boʻlimga boʻlingan', async () => {
    const user = userEvent.setup();
    const { items } = await client.listRingGroups();
    renderPage(<RingGroupsPage />);
    await user.dblClick(await screen.findByText(items[0]!.name));

    expect(await screen.findByRole('heading', { name: 'Umumiy' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Aʼzolar' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Jiringlash va eʼlonlar' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Caller ID' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Kengaytirilgan' })).toBeTruthy();
  });

  it('"Qoʻngʻiroqni tasdiqlash" yoqilmaguncha "Tasdiqlash eʼloni" koʻrinmaydi', async () => {
    const user = userEvent.setup();
    const { items } = await client.listRingGroups();
    renderPage(<RingGroupsPage />);
    await user.dblClick(await screen.findByText(items[0]!.name));
    await screen.findByRole('heading', { name: 'Umumiy' });

    expect(screen.queryByText('Tasdiqlash eʼloni')).toBeNull();
    await user.click(screen.getByText('Qoʻngʻiroqni tasdiqlash'));
    expect(await screen.findByText('Tasdiqlash eʼloni')).toBeTruthy();
  });

  it('"Band aʼzoni oʻtkazib yuborish"ni yoqib saqlash — fake API orqali haqiqatan saqlanadi', async () => {
    const user = userEvent.setup();
    const { items } = await client.listRingGroups();
    const group = items[0]!;
    expect(group.skip_busy_agent).toBe(false);

    renderPage(<RingGroupsPage />);
    await user.dblClick(await screen.findByText(group.name));
    await screen.findByRole('heading', { name: 'Umumiy' });
    await user.click(screen.getByText('Band aʼzoni oʻtkazib yuborish'));
    await user.click(screen.getByRole('button', { name: 'Saqlash' }));

    const { items: after } = await client.listRingGroups();
    expect(after.find((g) => g.id === group.id)?.skip_busy_agent).toBe(true);
  });
});
