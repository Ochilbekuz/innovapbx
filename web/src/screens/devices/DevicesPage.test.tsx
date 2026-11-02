// Xatti-harakat testi — Qurilmalar (S35): jadval/holat badge, topilgan qurilmalar, BLF tahrirlovchi, forma validatsiyasi.
// Qarang ../../../replica/m4a-contract.md §3-4.
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

const { DevicesPage } = await import('./DevicesPage');

async function rowFor(mac: string): Promise<HTMLElement> {
  return (await screen.findByText(mac)).closest('tr')!;
}

describe('DevicesPage', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('jadval va holat badgeʼlari seed maʼlumotlariga mos koʻrinadi, provizioning URL koʻrsatiladi', async () => {
    renderPage(<DevicesPage />);

    expect(within(await rowFor('805ec0aa0001')).getByText('Roʻyxatda')).toBeTruthy();
    expect(within(await rowFor('805ec0aa0004')).getByText('Hech soʻramagan')).toBeTruthy();
    expect(within(await rowFor('0c383e55aa03')).getByText('Yangilanishi kerak')).toBeTruthy();

    expect(screen.getByDisplayValue('http://pbx.innova.local/prov/8f2c91a4b3d7e6f5a1c0b9d8e7f6a5b4/')).toBeTruthy();
  });

  it('topilgan qurilma — raqamga biriktirish jadvalga qoʻshadi, banner yoʻqoladi', async () => {
    const user = userEvent.setup();
    renderPage(<DevicesPage />);

    expect(await screen.findByText('Topilgan qurilmalar: 1 ta')).toBeTruthy();
    await screen.findByText('805ec0aabbcc');
    await user.click(screen.getByRole('button', { name: 'Raqamga biriktirish' }));

    const dialog = screen.getByRole('dialog', { name: 'Qurilmani ichki raqamga biriktirish' });
    await user.click(within(dialog).getByRole('combobox', { name: 'Ichki raqam' }));
    await user.click(await screen.findByRole('option', { name: '107 — Bekzod Aliyev' }));
    await user.click(within(dialog).getByRole('button', { name: 'Raqamga biriktirish' }));

    await waitFor(() => expect(screen.queryByText('Topilgan qurilmalar: 1 ta')).toBeNull());
    expect(within(await rowFor('805ec0aabbcc')).getByText('107 — Bekzod Aliyev')).toBeTruthy();
  });

  it("yangi apparat qoʻshish formasi — MAC/model/raqam toʻlmaguncha tugma oʻchirilgan, MAC band boʻlsa 409 maydon ostida chiqadi", async () => {
    const user = userEvent.setup();
    renderPage(<DevicesPage />);

    await user.click(await screen.findByTestId('device-create'));
    const dialog = screen.getByRole('dialog', { name: 'Apparat qoʻshish' });
    const saveBtn = within(dialog).getByRole('button', { name: 'Saqlash' });
    expect(saveBtn).toBeDisabled();

    await user.type(within(dialog).getByRole('textbox', { name: 'MAC manzil' }), '805ec0aa0001');
    await user.click(within(dialog).getByRole('combobox', { name: 'Model' }));
    await user.click(await screen.findByRole('option', { name: 'T46U (27)' }));
    await user.click(within(dialog).getByRole('combobox', { name: 'Ichki raqam' }));
    await user.click(await screen.findByRole('option', { name: '107 — Bekzod Aliyev' }));

    expect(saveBtn).not.toBeDisabled();
    await user.click(saveBtn);

    expect(await within(dialog).findByText('Bu MAC manzilli apparat allaqachon roʻyxatda bor.')).toBeTruthy();
  });

  it('WebRTC yoqilgan ichki raqamlar (101/102) formada tanlov sifatida koʻrsatilmaydi, backend ham 422 extension_webrtc qaytaradi', async () => {
    const user = userEvent.setup();
    renderPage(<DevicesPage />);

    await user.click(await screen.findByTestId('device-create'));
    const dialog = screen.getByRole('dialog', { name: 'Apparat qoʻshish' });
    await user.click(within(dialog).getByRole('combobox', { name: 'Ichki raqam' }));
    expect(screen.queryByRole('option', { name: '101 — Dilnoza Karimova' })).toBeNull();
    expect(screen.queryByRole('option', { name: '102 — Sherzod Yusupov' })).toBeNull();

    await expect(client.createDevice({ mac: '001122334455', vendor: 'yealink', model: 'T46U', extension_id: 'e-101' })).rejects.toMatchObject({
      status: 422, code: 'extension_webrtc', field: 'extension_id',
    });
  });

  it('BLF/tugmalar tahrirlovchisi — mavjud tugmalarni koʻrsatadi, qator oʻchiradi, notoʻgʻri BLF qiymati 422 chiqaradi', async () => {
    const user = userEvent.setup();
    renderPage(<DevicesPage />);

    const row103 = await rowFor('805ec0aa0001');
    await user.click(within(row103).getByRole('button', { name: 'Tugmalar' }));

    const dialog = screen.getByRole('dialog', { name: /Tugmalar/ });
    await within(dialog).findByDisplayValue('0712001122');
    const removeBtns = within(dialog).getAllByRole('button', { name: 'Oʻchirish' });
    expect(removeBtns).toHaveLength(2);

    await user.click(removeBtns[1]!);
    expect(within(dialog).queryByDisplayValue('0712001122')).toBeNull();

    const blfValue = within(dialog).getByDisplayValue('102');
    await user.clear(blfValue);
    await user.type(blfValue, '999');
    await user.click(within(dialog).getByRole('button', { name: 'Saqlash' }));

    expect(await within(dialog).findByText('Bu raqamga BLF ulab boʻlmaydi — ichki raqamlar roʻyxatida yoʻq.')).toBeTruthy();
  });

  it('apparatni tahrirlash — yorliqni oʻzgartirish saqlanadi va qayta ochilganda koʻrinadi', async () => {
    const user = userEvent.setup();
    renderPage(<DevicesPage />);

    const row = await rowFor('00156501aa02');
    await user.click(within(row).getByRole('button', { name: 'Tahrirlash' }));

    const dialog = screen.getByRole('dialog', { name: 'Apparatni tahrirlash' });
    const labelInput = within(dialog).getByRole('textbox', { name: 'Yorliq' });
    await user.clear(labelInput);
    await user.type(labelInput, 'Qabulxona — yangi yorliq');
    await user.click(within(dialog).getByRole('button', { name: 'Saqlash' }));

    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Apparatni tahrirlash' })).toBeNull());
    const item = (await client.listDevices({})).items.find((d) => d.id === 'dv-106');
    expect(item?.label).toBe('Qabulxona — yangi yorliq');

    await user.click(within(await rowFor('00156501aa02')).getByRole('button', { name: 'Tahrirlash' }));
    expect(screen.getByRole('textbox', { name: 'Yorliq' })).toHaveValue('Qabulxona — yangi yorliq');
  });

  it("konfiguratsiya koʻrish — parol har doim «***» bilan maskalangan, fayl nomi vendorga mos", async () => {
    const user = userEvent.setup();
    renderPage(<DevicesPage />);

    const row = await rowFor('805ec0aa0001');
    await user.click(within(row).getByRole('button', { name: 'Config' }));

    const dialog = await screen.findByRole('dialog', { name: 'Konfiguratsiya — 805ec0aa0001.boot' });
    expect(within(dialog).getByText(/account\.1\.password = \*\*\*/)).toBeTruthy();
  });

  it('qayta sozlash — registered apparatda muvaffaqiyatli, registered boʻlmaganda 409 toast', async () => {
    const user = userEvent.setup();
    renderPage(<ToastProvider><DevicesPage /></ToastProvider>);

    const row108 = await rowFor('0c383e55aa03');
    await user.click(within(row108).getByRole('button', { name: 'Qayta sozlash' }));
    expect(await screen.findByText('Qayta sozlash soʻrovi yuborildi.')).toBeTruthy();

    const row105 = await rowFor('805ec0aa0004');
    await user.click(within(row105).getByRole('button', { name: 'Qayta sozlash' }));
    expect(await screen.findByText('Qayta sozlab boʻlmadi.')).toBeTruthy();
  });

  it('apparatni oʻchirish — tasdiqdan keyin jadvaldan yoʻqoladi', async () => {
    const user = userEvent.setup();
    renderPage(<DevicesPage />);

    const row = await rowFor('805ec0aa0004');
    await user.click(within(row).getByRole('button', { name: 'Oʻchirish' }));

    const dialog = screen.getByRole('dialog', { name: 'Apparatni oʻchirasizmi?' });
    await user.click(within(dialog).getByRole('button', { name: 'Oʻchirish' }));

    await waitFor(() => expect(screen.queryByText('805ec0aa0004')).toBeNull());
  });

  it('provizioning tokenini almashtirish — tasdiq dialogi orqali yangi URL beradi', async () => {
    const user = userEvent.setup();
    renderPage(<ToastProvider><DevicesPage /></ToastProvider>);

    await user.click(await screen.findByRole('button', { name: 'Tokenni almashtirish' }));
    await user.click(screen.getByRole('button', { name: 'Ha, almashtirish' }));

    expect(await screen.findByText('Yangi token yaratildi — eski manzil endi ishlamaydi.')).toBeTruthy();
  });

  it('sozlamalar tabi — CIDR notoʻgʻri boʻlsa 422 maydon ostida chiqadi', async () => {
    const user = userEvent.setup();
    renderPage(<DevicesPage />);

    await user.click(screen.getByRole('tab', { name: 'Sozlamalar' }));
    const networks = await screen.findByLabelText('Ruxsat etilgan tarmoqlar (CIDR)');
    await user.clear(networks);
    await user.type(networks, 'not-a-cidr');
    await user.click(screen.getByRole('button', { name: 'Saqlash' }));

    expect(await screen.findByText('Ruxsat etilgan tarmoqlar roʻyxatida notoʻgʻri CIDR bor.')).toBeTruthy();
  });

  it('jurnal tabi — seed provizioning soʻrovlarini sabab bilan koʻrsatadi', async () => {
    const user = userEvent.setup();
    renderPage(<DevicesPage />);

    await user.click(screen.getByRole('tab', { name: 'Jurnal' }));
    expect(await screen.findByText('Muvaffaqiyatli')).toBeTruthy();
    expect(screen.getByText('Nomaʼlum MAC')).toBeTruthy();
  });

  it("operator — faqat koʻrish banneri chiqadi, boshqarish tugmalari yoʻq", async () => {
    await loginAs(client, 'operator');
    renderPage(<DevicesPage />);

    expect(await screen.findByText(/Faqat koʻrish/)).toBeTruthy();
    expect(screen.queryByTestId('device-create')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Tokenni almashtirish' })).toBeNull();
  });
});
