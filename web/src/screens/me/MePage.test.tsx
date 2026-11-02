// Xatti-harakat testi — DND saqlanishi (optimistik konkurentlik), navbat pauzasi sababi bilan saqlanishi,
// ichki raqam bogʻlanmagan foydalanuvchi uchun boʻsh holat (M2b §4). Qarang ../../../replica/m2b-contract.md §4.
import { describe, expect, it, afterEach, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { MePage } = await import('./MePage');

describe('MePage', () => {
  afterEach(() => useSession.getState().clear());

  it('ichki raqam bogʻlanmagan foydalanuvchi uchun boʻsh holat koʻrsatiladi', async () => {
    await loginAs(client, 'admin'); // SEED_ADMIN hech qaysi ichki raqamga bogʻlanmagan.
    renderPage(<MePage />);

    expect(await screen.findByText('Ichki raqam bogʻlanmagan')).toBeTruthy();
    expect(screen.queryByText('Band qilmaslik (DND)')).toBeNull();
  });

  it('DND yoqilgandan keyin saqlanadi (optimistik konkurentlik)', async () => {
    await loginAs(client, 'operator'); // SEED_OPERATOR — 102 (Sherzod Yusupov)ga bogʻlangan.
    const user = userEvent.setup();
    renderPage(<MePage />);

    const dndSwitch = await screen.findByRole('switch', { name: 'Band qilmaslik (DND)' });
    // Follow Me kartasida ham «Saqlash» bor — DND kartasi bilan cheklaymiz.
    const card = within(dndSwitch.closest('.shadow-card') as HTMLElement);
    expect(dndSwitch).toHaveAttribute('aria-checked', 'false');
    await user.click(dndSwitch);
    await user.click(card.getByRole('button', { name: 'Saqlash' }));

    // Saqlangandan keyin serverdagi qiymat bilan tenglashadi — "Saqlash" tugmasi yana oʻchirilgan holatga qaytadi.
    await waitFor(() => expect(card.getByRole('button', { name: 'Saqlash' })).toBeDisabled());
    expect(screen.getByRole('switch', { name: 'Band qilmaslik (DND)' })).toHaveAttribute('aria-checked', 'true');
    const ext = (await client.listExtensions({})).items.find((e) => e.id === 'e-102');
    expect(ext?.dnd).toBe(true);
  });

  it('navbatda pauza sababi bilan saqlanadi va roʻyxatda koʻrinadi', async () => {
    await loginAs(client, 'operator');
    const user = userEvent.setup();
    renderPage(<MePage />);

    const row = (await screen.findByText('Sotuv boʻlimi')).closest('li')!;
    await user.click(within(row).getByRole('button', { name: 'Pauza' }));

    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByLabelText('Sabab'), 'tushlik');
    await user.click(within(dialog).getByRole('button', { name: 'Pauza' }));

    expect(await within(row).findByText('Pauzada')).toBeTruthy();
    expect(within(row).getByText('(tushlik)')).toBeTruthy();

    const { items } = await client.listQueues();
    const member = items[0]!.members.find((m) => m.extension.id === 'e-102');
    expect(member?.paused).toBe(true);
    expect(member?.pause_reason).toBe('tushlik');
  });

  it('Follow Me va «Telefonga ulash» kartalari koʻrinadi; WebRTC raqamga QR berilmaydi', async () => {
    await loginAs(client, 'operator');
    const user = userEvent.setup();
    renderPage(<MePage />);

    expect(await screen.findByTestId('follow-me')).toBeTruthy();
    expect(await screen.findByTestId('fm-save')).toBeDisabled();
    await user.click(screen.getByTestId('me-qr-open'));
    expect(await screen.findByTestId('qr-error')).toBeTruthy();
  });
});
