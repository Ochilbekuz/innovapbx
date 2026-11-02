// Xatti-harakat testi — Zaxira (S34): holat, zaxiralar jadvali, "Hozir zaxiralash", oʻchirish, roʻyxatdan
// tiklash, sozlamalar (jadval/lokal/S3/SFTP/parol) va "Fayldan tiklash" oqimi. Qarang ../../../replica/m4b-contract.md §3.
// Eslatma: testlar BIR fake klientga tayanadi va ketma-ket ishlaydi (DevicesPage.test.tsx'dagi uslub) —
// tartib ataylab saqlangan (masalan oʻchirish tiklashdan oldin, chunki tiklash «pre_restore» qator qoʻshadi).
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';
import { ToastProvider } from '@/ui/Toast';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { BackupPage } = await import('./BackupPage');

function section(heading: string): HTMLElement {
  return screen.getByRole('heading', { name: heading }).closest('section') as HTMLElement;
}

describe('BackupPage', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('holat kartasi va zaxiralar jadvali seed maʼlumotlariga mos koʻrinadi', async () => {
    renderPage(<BackupPage />);

    expect(await screen.findByText('26/10/26, 10:00 — 26 MB')).toBeTruthy();
    expect(screen.queryByText(/paroli oʻrnatilmagan/)).toBeNull();

    const rows = (await screen.findAllByRole('row')).slice(1);
    expect(rows).toHaveLength(3);
    expect(within(rows[0]!).getByText('Qoʻlda')).toBeTruthy();
    expect(within(rows[0]!).getByText('Tayyor')).toBeTruthy();
    expect(within(rows[1]!).getByText('Jadval boʻyicha')).toBeTruthy();
    expect(within(rows[1]!).getByText('Qisman')).toBeTruthy();
    expect(within(rows[2]!).getByText('Tiklashdan oldin')).toBeTruthy();

    await userEvent.setup().hover(within(rows[1]!).getByText('SFTP'));
  });

  it('operator — faqat koʻrish banneri chiqadi, boshqarish tugmalari yoʻq (shartnoma: operator → 403)', async () => {
    await loginAs(client, 'operator');
    renderPage(<BackupPage />);

    expect(await screen.findByText(/Faqat koʻrish/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Hozir zaxiralash' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Oʻchirish' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Tiklash' })).toBeNull();
  });

  it(
    '«Hozir zaxiralash» — progress koʻrsatadi va muvaffaqiyatli yakunlanib jadvalga qoʻshadi',
    async () => {
      const user = userEvent.setup();
      renderPage(<ToastProvider><BackupPage /></ToastProvider>);

      await user.click(screen.getByRole('button', { name: 'Hozir zaxiralash' }));
      const dialog = screen.getByRole('dialog', { name: 'Zaxira yaratish' });
      await user.click(within(dialog).getByRole('button', { name: 'Boshlash' }));

      expect(await screen.findByText('Zaxiralash boshlandi.')).toBeTruthy();
      expect(await screen.findByText('Zaxiralanmoqda…')).toBeTruthy();

      await waitFor(() => expect(screen.queryByText('Zaxiralanmoqda…')).toBeNull(), { timeout: 6000 });
      expect(await screen.findByText('Zaxira muvaffaqiyatli yaratildi.')).toBeTruthy();

      const rows = (await screen.findAllByRole('row')).slice(1);
      expect(rows).toHaveLength(4);
    },
    10_000,
  );

  it('zaxirani oʻchirish — tasdiqdan keyin jadvaldan yoʻqoladi', async () => {
    const user = userEvent.setup();
    renderPage(<ToastProvider><BackupPage /></ToastProvider>);

    const row = (await screen.findByText('Tiklashdan oldin')).closest('tr')!;
    await user.click(within(row).getByRole('button', { name: 'Oʻchirish' }));

    const dialog = screen.getByRole('dialog', { name: 'Zaxirani oʻchirasizmi?' });
    await user.click(within(dialog).getByRole('button', { name: 'Oʻchirish' }));

    await waitFor(() => expect(screen.queryByText('Tiklashdan oldin')).toBeNull());
    expect(await screen.findByText('Zaxira oʻchirildi.')).toBeTruthy();
  });

  it(
    'roʻyxatdan tiklash — TIKLASH tasdiqlash, faol qoʻngʻiroq ogohlantirishi, progress va seansni tugatish',
    async () => {
      const user = userEvent.setup();
      renderPage(<ToastProvider><BackupPage /></ToastProvider>);

      const row = (await screen.findAllByText('Qoʻlda'))[0]!.closest('tr')!;
      await user.click(within(row).getByRole('button', { name: 'Tiklash' }));

      const confirmDialog = screen.getByRole('dialog', { name: 'Tiklashni tasdiqlaysizmi?' });
      await user.type(within(confirmDialog).getByPlaceholderText('TIKLASH'), 'TIKLASH');
      await user.click(within(confirmDialog).getByRole('button', { name: 'Tiklash' }));

      const activeCallsDialog = await screen.findByRole('dialog', { name: 'Hozir faol qoʻngʻiroqlar bor' });
      expect(within(activeCallsDialog).getByText(/2 ta faol qoʻngʻiroq/)).toBeTruthy();
      await user.click(within(activeCallsDialog).getByRole('button', { name: 'Baribir tiklash' }));

      expect(await screen.findByRole('dialog', { name: 'Tiklanmoqda…' })).toBeTruthy();
      await waitFor(() => expect(useSession.getState().user).toBeNull(), { timeout: 6000 });
    },
    10_000,
  );

  it('sozlamalar — jadval qismlari boʻsh boʻlsa Saqlash oʻchadi, S3 ulanishi muvaffaqiyatli tekshiriladi', async () => {
    const user = userEvent.setup();
    renderPage(<ToastProvider><BackupPage /></ToastProvider>);

    await user.click(screen.getByRole('tab', { name: 'Jadval va saqlash joylari' }));
    const saveBtn = await screen.findByRole('button', { name: 'Saqlash' });
    const scheduleSection = section('Avtomatik zaxira jadvali');

    for (const label of ['Konfiguratsiya', 'Chaqiruvlar tarixi', 'Ovoz fayllari', 'Ovozli xabarlar', 'Sertifikatlar']) {
      await user.click(within(scheduleSection).getByRole('checkbox', { name: label }));
    }
    expect(saveBtn).toBeDisabled();

    await user.click(within(scheduleSection).getByRole('checkbox', { name: 'Konfiguratsiya' }));
    expect(saveBtn).not.toBeDisabled();

    const s3Section = section('S3 (yoki mos API)');
    await user.click(within(s3Section).getByRole('button', { name: 'Ulanishni tekshirish' }));
    expect(await within(s3Section).findByText('Ulanish muvaffaqiyatli.')).toBeTruthy();

    await user.click(saveBtn);
    expect(await screen.findByText('Saqlandi.')).toBeTruthy();
  });

  it('sozlamalar — SFTP yoqish, saqlash, server barmoq izini birinchi marta tasdiqlash', async () => {
    const user = userEvent.setup();
    renderPage(<ToastProvider><BackupPage /></ToastProvider>);

    await user.click(screen.getByRole('tab', { name: 'Jadval va saqlash joylari' }));
    await screen.findByRole('heading', { name: 'SFTP' });
    const sftpSection = section('SFTP');
    await user.click(within(sftpSection).getByRole('switch', { name: 'Yoqilgan' }));
    await user.type(within(sftpSection).getByRole('textbox', { name: 'Server' }), 'sftp.example.com');
    await user.type(within(sftpSection).getByRole('textbox', { name: 'Foydalanuvchi' }), 'backup');
    await user.type(within(sftpSection).getByLabelText('Parol'), 'sftp-secret-1');

    await user.click(screen.getByRole('button', { name: 'Saqlash' }));
    expect(await screen.findByText('Saqlandi.')).toBeTruthy();

    await user.click(within(section('SFTP')).getByRole('button', { name: 'Ulanishni tekshirish' }));
    const trustDialog = await screen.findByRole('dialog', { name: 'Server barmoq izini tasdiqlaysizmi?' });
    expect(within(trustDialog).getByText(/Barmoq izi:/)).toBeTruthy();
    await user.click(within(trustDialog).getByRole('button', { name: 'Ha, ishonaman' }));

    expect(await screen.findByText('Server barmoq izi tasdiqlandi.')).toBeTruthy();
  });

  it('sozlamalar — zaxira parolini almashtirish, kuch koʻrsatkichi va "Saqlash" validatsiyasi', async () => {
    const user = userEvent.setup();
    renderPage(<ToastProvider><BackupPage /></ToastProvider>);

    await user.click(screen.getByRole('tab', { name: 'Jadval va saqlash joylari' }));
    await screen.findByRole('heading', { name: 'Zaxira paroli' });
    const passphraseSection = section('Zaxira paroli');
    expect(within(passphraseSection).getByText('Oʻrnatilgan')).toBeTruthy();

    const submitBtn = within(passphraseSection).getByRole('button', { name: 'Parolni saqlash' });
    expect(submitBtn).toBeDisabled();

    await user.type(within(passphraseSection).getByLabelText('Joriy parol'), 'DemoZaxiraParoli12345!');
    await user.type(within(passphraseSection).getByLabelText(/Yangi parol/), 'YangiKuchliParol123!@#$');
    expect(within(passphraseSection).getByText('Kuchli')).toBeTruthy();

    await user.click(submitBtn);
    expect(await screen.findByText('Zaxira paroli saqlandi.')).toBeTruthy();
  });

  it('fayldan tiklash — buzilgan fayl inspect bosqichida xato beradi', async () => {
    const user = userEvent.setup();
    renderPage(<ToastProvider><BackupPage /></ToastProvider>);

    await user.click(screen.getByRole('tab', { name: 'Fayldan tiklash' }));
    await user.upload(screen.getByTestId('restore-upload-input'), new File(['x'], 'demo-corrupt.ibk'));
    await user.click(await screen.findByRole('button', { name: 'Yuklash' }));
    expect(await screen.findByText('Fayl yuklandi.')).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Tekshirish' }));
    expect(await screen.findByText('Zaxira fayli buzilgan — qism yetishmaydi yoki oʻzgartirilgan.')).toBeTruthy();
  });

  it(
    'fayldan tiklash — yuklash→tekshirish→tiklash oqimi toʻliq ishlaydi va tarix koʻrsatiladi',
    async () => {
      const user = userEvent.setup();
      renderPage(<ToastProvider><BackupPage /></ToastProvider>);

      await user.click(screen.getByRole('tab', { name: 'Fayldan tiklash' }));
      expect(await screen.findByRole('heading', { name: 'Tiklash tarixi' })).toBeTruthy();
      expect((await screen.findAllByText('Muvaffaqiyatli')).length).toBeGreaterThan(0);
      expect(screen.getAllByText('Roʻyxatdagi zaxiradan').length).toBeGreaterThan(0);
      expect(screen.getAllByRole('button', { name: 'Tiklashdan oldingi zaxira' }).length).toBeGreaterThan(0);

      await user.upload(screen.getByTestId('restore-upload-input'), new File(['x'], 'demo-ok.ibk'));
      await user.click(await screen.findByRole('button', { name: 'Yuklash' }));
      await screen.findByText('Fayl yuklandi.');

      await user.click(screen.getByRole('button', { name: 'Tekshirish' }));
      expect(await screen.findByText('Joriy tizim bilan mos')).toBeTruthy();
      expect(screen.getByText('Ovoz yozuvlari zaxirada yoʻq.')).toBeTruthy();

      await user.click(screen.getByRole('button', { name: 'Tiklashga oʻtish' }));
      const confirmDialog = screen.getByRole('dialog', { name: 'Tiklashni tasdiqlaysizmi?' });
      await user.type(within(confirmDialog).getByPlaceholderText('TIKLASH'), 'TIKLASH');
      await user.click(within(confirmDialog).getByRole('button', { name: 'Tiklash' }));

      const activeCallsDialog = await screen.findByRole('dialog', { name: 'Hozir faol qoʻngʻiroqlar bor' });
      await user.click(within(activeCallsDialog).getByRole('button', { name: 'Baribir tiklash' }));

      expect(await screen.findByRole('dialog', { name: 'Tiklanmoqda…' })).toBeTruthy();
      await waitFor(() => expect(useSession.getState().user).toBeNull(), { timeout: 6000 });
    },
    10_000,
  );
});
