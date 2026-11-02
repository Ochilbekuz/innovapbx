// Xatti-harakat testi — Ko'chirish (S36): sehrgar bosqichlari, SSH barmoq izi tasdiqlash, reja patch
// qoidasi, "KOCHIRISH" tasdiqlash, `plan_stale` 409 → qayta tahlil, operator uchun ko'rinmaslik.
// Eslatma: BIR fake klientga tayanadi, testlar ketma-ket ishlaydi (BackupPage.test.tsx'dagi uslub bilan bir xil).
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

const { MigrationPage } = await import('./MigrationPage');
const { ApplyStep } = await import('./ApplyStep');
const { RequireFullAccess } = await import('@/auth/guards');

describe('MigrationPage', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('seed holati — oxirgi ish (ok) uchun Natija bosqichi va tarix jadvali koʻrinadi', async () => {
    renderPage(<MigrationPage />);

    const resultStep = await screen.findByTestId('migration-result-step');
    expect(within(resultStep).getByText('5')).toBeTruthy(); // extension yaratildi
    expect(screen.getAllByRole('row')).toHaveLength(2); // sarlavha + 1 seed ish
  });

  it('operator — RequireFullAccess sahifani koʻrsatmaydi (/me ga yoʻnaltiradi)', async () => {
    await loginAs(client, 'operator');
    renderPage(<RequireFullAccess screenId="migration"><MigrationPage /></RequireFullAccess>);

    expect(screen.queryByTestId('migration-page')).toBeNull();
  });

  it(
    'toʻliq oqim: yangi import → yuklash → tahlil → koʻrib chiqish (toʻqnashuv replace boʻlmaganda bloklanadi) → ' +
      'qoʻllash "KOCHIRISH" bilan → muvaffaqiyatli natija',
    async () => {
      const user = userEvent.setup();
      renderPage(<ToastProvider><MigrationPage /></ToastProvider>);

      await user.click(await screen.findByRole('button', { name: 'Yangi import boshlash' }));
      expect(await screen.findByTestId('migration-source-step')).toBeTruthy();

      const file = new File(['x'], 'fpbx-export.tar.gz', { type: 'application/gzip' });
      const fileInput = screen.getByLabelText(/toʻplam fayli/i) as HTMLInputElement;
      await user.upload(fileInput, file);
      await user.click(screen.getByRole('button', { name: /Yuklash va tahlilga/i }));

      expect(await screen.findByTestId('migration-analyze-step')).toBeTruthy();
      await user.click(screen.getByRole('button', { name: 'Tahlilni boshlash' }));

      await waitFor(() => expect(screen.getByTestId('migration-analyze-step').textContent).not.toMatch(/Tahlilni boshlash/), { timeout: 3000 });
      await waitFor(() => expect(screen.queryByTestId('migration-review-step')).toBeTruthy(), { timeout: 4000 });

      // Toʻqnashuv (101 raqami) replaceable emas — faqat "oʻtkazib yuborish" tanlanishi mumkin, "almashtirish" yoʻq.
      const conflictRow = (await screen.findByText('Alisher Yusupov')).closest('tr')!;
      expect(within(conflictRow).getByText(/almashtirish boʻlmaydi|Almashtirib boʻlmaydi/i)).toBeTruthy();

      await user.click(screen.getByRole('button', { name: /Qoʻllashga oʻtish/i }));
      expect(await screen.findByTestId('migration-apply-step')).toBeTruthy();

      const applyButton = screen.getByRole('button', { name: /^Qoʻllash$/ });
      expect(applyButton).toBeDisabled();
      const confirmInput = screen.getByLabelText(/Tasdiqlash/i);
      await user.type(confirmInput, 'notogri');
      expect(applyButton).toBeDisabled();
      await user.clear(confirmInput);
      await user.type(confirmInput, 'KOCHIRISH');
      expect(applyButton).toBeEnabled();
      await user.click(applyButton);

      await waitFor(() => expect(screen.queryByTestId('migration-apply-step')?.textContent).not.toMatch(/^Qoʻllash$/), { timeout: 3000 });
      await waitFor(() => expect(screen.queryByTestId('migration-result-step')).toBeTruthy(), { timeout: 5000 });
      expect(screen.getByText('Koʻchirish yakunlandi')).toBeTruthy();
    },
    15_000,
  );

  it(
    'SSH orqali olib kelish — sinov muvaffaqiyatli boʻlsa barmoq izini tasdiqlash oynasi chiqadi, ' +
      'tasdiqlanmaguncha olib kelish ishga tushmaydi',
    async () => {
      const user = userEvent.setup();
      renderPage(<ToastProvider><MigrationPage /></ToastProvider>);

      await user.click(await screen.findByRole('button', { name: 'Yangi import boshlash' }));
      await screen.findByTestId('migration-source-step');
      await user.click(screen.getByRole('tab', { name: /SSH/i }));

      await user.type(screen.getByLabelText(/^Host$/i), '10.0.0.9');
      await user.type(screen.getByLabelText(/^Foydalanuvchi$/i), 'root');
      await user.type(screen.getByLabelText(/^Parol$/i), 'sekret-parol');

      await user.click(screen.getByRole('button', { name: /Ulanishni tekshirish/i }));
      const dialog = await screen.findByRole('dialog');
      expect(within(dialog).getByText(/SHA256:/)).toBeTruthy();

      // Tasdiqlanmaguncha yangi ish yaratilmaydi — manba bosqichida qolinadi.
      expect(screen.queryByTestId('migration-analyze-step')).toBeNull();

      await user.click(within(dialog).getByRole('button', { name: /Tasdiqlab olib kelish/i }));
      await waitFor(() => expect(screen.queryByTestId('migration-analyze-step')).toBeTruthy(), { timeout: 3000 });

      // Keyingi testlar yangi boshlanish nuqtasiga tayanadi — shu ishni oxirigacha yakunlaymiz
      // (aks holda u "eng soʻnggi ish" sifatida keyingi testlarni Natija bosqichidan boshqa joyga olib boradi).
      await user.click(screen.getByRole('button', { name: 'Tahlilni boshlash' }));
      await waitFor(() => expect(screen.queryByTestId('migration-review-step')).toBeTruthy(), { timeout: 4000 });
      await user.click(screen.getByRole('button', { name: /Qoʻllashga oʻtish/i }));
      await screen.findByTestId('migration-apply-step');
      await user.type(screen.getByLabelText(/Tasdiqlash/i), 'KOCHIRISH');
      await user.click(screen.getByRole('button', { name: /^Qoʻllash$/ }));
      await waitFor(() => expect(screen.queryByTestId('migration-result-step')).toBeTruthy(), { timeout: 5000 });
      await user.click(screen.getByRole('button', { name: 'Yangi import boshlash' }));
    },
    15_000,
  );

  it(
    '"plan_stale" 409 — qoʻllashda eskirgan reja banneri chiqadi, qayta tahlildan keyin qoʻllash davom etadi',
    async () => {
      const user = userEvent.setup();
      renderPage(<ToastProvider><MigrationPage /></ToastProvider>);

      await user.click(await screen.findByRole('button', { name: 'Yangi import boshlash' }));
      await screen.findByTestId('migration-source-step');
      const file = new File(['x'], 'fpbx-export-stale.tar.gz', { type: 'application/gzip' });
      await user.upload(screen.getByLabelText(/toʻplam fayli/i) as HTMLInputElement, file);
      await user.click(screen.getByRole('button', { name: /Yuklash va tahlilga/i }));

      await screen.findByTestId('migration-analyze-step');
      await user.click(screen.getByRole('button', { name: 'Tahlilni boshlash' }));
      await waitFor(() => expect(screen.queryByTestId('migration-review-step')).toBeTruthy(), { timeout: 4000 });
      await user.click(screen.getByRole('button', { name: /Qoʻllashga oʻtish/i }));

      await screen.findByTestId('migration-apply-step');
      await user.type(screen.getByLabelText(/Tasdiqlash/i), 'KOCHIRISH');
      await user.click(screen.getByRole('button', { name: /^Qoʻllash$/ }));

      const applyStep = await screen.findByTestId('migration-apply-step');
      await waitFor(() => expect(within(applyStep).queryByText(/qayta tahlil qilish kerak/i)).toBeTruthy(), { timeout: 3000 });
      const reanalyzeBtn = within(applyStep).getByRole('button', { name: /qayta tahlil/i });
      await user.click(reanalyzeBtn);

      // Qayta tahlil darhol "analyzing" holatini keshga yozadi (queries.ts: useAnalyzeMigrationJob) —
      // shu sabab bu safar "Tahlilni boshlash" tugmasi yoʻq, toʻgʻridan-toʻgʻri tahlil bosqichida kutamiz.
      await waitFor(() => expect(screen.queryByTestId('migration-review-step')).toBeTruthy(), { timeout: 4000 });
      await user.click(screen.getByRole('button', { name: /Qoʻllashga oʻtish/i }));
      await screen.findByTestId('migration-apply-step');
      await user.type(screen.getByLabelText(/Tasdiqlash/i), 'KOCHIRISH');
      await user.click(screen.getByRole('button', { name: /^Qoʻllash$/ }));
      await waitFor(() => expect(screen.queryByTestId('migration-result-step')).toBeTruthy(), { timeout: 5000 });
    },
    20_000,
  );
});

describe('ApplyStep — backup_ready=false', () => {
  afterEach(() => useSession.getState().clear());

  it('zaxira paroli yoʻq boʻlsa — ogohlantirish va havola koʻrinadi, qoʻllash tugmasi bloklanadi', async () => {
    await loginAs(client, 'admin');
    const job = {
      id: 'mjob-test', source: 'upload' as const, status: 'analyzed' as const, step: null, progress: 100,
      source_meta: null,
      summary: { by_kind: {}, warnings: 0, ignored: 0, weak_secrets: 0 },
      options: { rotate_weak_secrets: false }, result: null, error: null,
      pre_import_backup_id: null, backup_ready: false, created_by: null,
      created_at: '2026-01-01T00:00:00Z', finished_at: null,
    };
    renderPage(
      <ApplyStep job={job} canManage confirmText="KOCHIRISH" onConfirmTextChange={() => {}} onReanalyze={() => {}} rotateWeakSecrets={false} />,
    );

    expect(screen.getByText(/Zaxira paroli/)).toBeTruthy();
    expect(screen.getByRole('link', { name: /Zaxira/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /^Qoʻllash$/ })).toBeDisabled();
  });
});
