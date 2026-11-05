// Xatti-harakat testi — DND saqlanishi (optimistik konkurentlik), navbat pauzasi sababi bilan saqlanishi,
// ichki raqam bogʻlanmagan foydalanuvchi uchun boʻsh holat (M2b §4). Qarang ../../../replica/m2b-contract.md §4.
import { describe, expect, it, afterEach, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';
import { SEED_ADMIN, SEED_ADMIN_PASSWORD } from '@/api/fakeSeed';
import { ToastProvider } from '@/ui/Toast';
import { currentTotpCode } from '@/domain/totp';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { MePage } = await import('./MePage');

describe('MePage', () => {
  afterEach(() => useSession.getState().clear());

  it('ichki raqam bogʻlanmagan foydalanuvchida ham hisob boʻlimi (parol, 2FA) koʻrinadi', async () => {
    await loginAs(client, 'admin'); // SEED_ADMIN hech qaysi ichki raqamga bogʻlanmagan.
    renderPage(<MePage />);
    const main = within(await screen.findByRole('main'));

    expect(await main.findByText('Ichki raqam bogʻlanmagan')).toBeTruthy();
    expect(main.queryByText('Band qilmaslik (DND)')).toBeNull();
    expect(main.getByRole('heading', { name: 'Ikki bosqichli tasdiqlash (2FA)' })).toBeTruthy();
    expect(main.getByRole('button', { name: 'Yoqish' })).toBeTruthy();
    expect(main.getByLabelText(/Joriy parol/)).toBeTruthy();
  });

  it('kabinetdan parolni oʻzgartirish: notoʻgʻri joriy parol — maydon xatosi, toʻgʻrisi — muvaffaqiyat va maydonlar tozalanadi', async () => {
    const user = userEvent.setup();
    await loginAs(client, 'admin');
    renderPage(<ToastProvider><MePage /></ToastProvider>);
    const main = within(await screen.findByRole('main'));

    const current = await main.findByLabelText(/Joriy parol/);
    const next = main.getByLabelText(/Yangi parol/);
    const submit = main.getByRole('button', { name: 'Parolni saqlash' });
    expect(submit).toBeDisabled();

    await user.type(current, 'notogri-parol');
    await user.type(next, 'YangiParol-2026');
    await user.click(submit);
    expect(await main.findByText('Joriy parol notoʻgʻri.')).toBeTruthy();

    await user.clear(current);
    await user.type(current, SEED_ADMIN_PASSWORD);
    await user.click(submit);
    expect(await screen.findByText('Parol oʻzgartirildi')).toBeTruthy();
    await waitFor(() => expect(current).toHaveValue(''));
    expect(next).toHaveValue('');
    // Yangi parol bilan kirish ishlaydi (keyingi testlar uchun qaytaramiz).
    expect((await client.login(SEED_ADMIN.login, 'YangiParol-2026')).status).toBe('ok');
    await client.changePassword({ current: 'YangiParol-2026', new: SEED_ADMIN_PASSWORD });
  });

  it('2FA: yoqish (ilova kodi) → zaxira kodlar, zaxira kod bilan qayta yaratish, keyin oʻchirish', async () => {
    const user = userEvent.setup();
    await loginAs(client, 'admin');
    const setupSpy = vi.spyOn(client, 'setupTotp');
    const enableSpy = vi.spyOn(client, 'enableTotp');
    const regenSpy = vi.spyOn(client, 'regenerateTotpRecoveryCodes');
    try {
      renderPage(<ToastProvider><MePage /></ToastProvider>);
      const main = within(await screen.findByRole('main'));

      await user.click(await main.findByRole('button', { name: 'Yoqish' }));
      const codeInput = await main.findByLabelText(/Ilovadan 6 xonali kod/);
      const { secret } = await setupSpy.mock.results[0]!.value;
      await user.type(codeInput, await currentTotpCode(secret));
      await user.click(main.getByRole('button', { name: 'Yoqish' }));

      const { recovery_codes } = await enableSpy.mock.results[0]!.value;
      expect(await main.findByText(recovery_codes[0])).toBeTruthy();
      expect(main.getByText('Yoqilgan')).toBeTruthy();
      await user.click(main.getByRole('button', { name: 'Tayyor' }));

      await user.click(main.getByRole('button', { name: 'Zaxira kodlarni qayta yaratish' }));
      let dialog = within(await screen.findByRole('dialog'));
      await user.type(dialog.getByLabelText(/Tasdiqlash kodi/), recovery_codes[0]);
      await user.click(dialog.getByRole('button', { name: 'Zaxira kodlarni qayta yaratish' }));
      const { recovery_codes: fresh } = await regenSpy.mock.results[0]!.value;
      expect(await main.findByText(fresh[0])).toBeTruthy();
      await user.click(main.getByRole('button', { name: 'Tayyor' }));

      await user.click(main.getByRole('button', { name: 'Oʻchirish' }));
      dialog = within(await screen.findByRole('dialog'));
      expect(dialog.getByLabelText(/Tasdiqlash kodi/)).toHaveValue(''); // oldingi oynadagi kod qolmagan
      await user.type(dialog.getByLabelText(/Tasdiqlash kodi/), fresh[0]);
      await user.click(dialog.getByRole('button', { name: 'Oʻchirish' }));
      expect(await screen.findByText('2FA oʻchirildi')).toBeTruthy();
      expect(main.getByText('Oʻchirilgan')).toBeTruthy();
      expect(main.getByRole('button', { name: 'Yoqish' })).toBeTruthy();
    } finally {
      setupSpy.mockRestore(); enableSpy.mockRestore(); regenSpy.mockRestore();
    }
  });

  it('2FA: notoʻgʻri kod bilan oʻchirishda modal xatoni koʻrsatadi', async () => {
    const user = userEvent.setup();
    await loginAs(client, 'admin');
    useSession.setState((st) => ({ user: st.user && { ...st.user, totp_enabled: true } }));
    renderPage(<ToastProvider><MePage /></ToastProvider>);
    const main = within(await screen.findByRole('main'));

    await user.click(await main.findByRole('button', { name: 'Oʻchirish' }));
    const dialog = within(await screen.findByRole('dialog'));
    await user.type(dialog.getByLabelText(/Tasdiqlash kodi/), '000000');
    await user.click(dialog.getByRole('button', { name: 'Oʻchirish' }));
    expect(await dialog.findByText('Kod notoʻgʻri.')).toBeTruthy();
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
