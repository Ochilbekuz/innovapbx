// Xatti-harakat testi — ext drawer "Qo'ng'iroqlar" bo'limi: DND saqlanishi, bad_number maydon ostida.
// Qarang ../../../replica/m2a-contract.md §1.
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
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

const { ExtensionsPage } = await import('./ExtensionsPage');

describe('ExtensionsPage — Qoʻngʻiroqlar boʻlimi', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it("DND yoqilgandan keyin saqlanadi — roʻyxatda belgi chiqadi va drawer qayta ochilganda toggle yoqilgan turadi", async () => {
    const user = userEvent.setup();
    renderPage(<ExtensionsPage />);

    await user.click(await screen.findByRole('button', { name: '103ni tahrirlash' }));
    await user.click(screen.getByRole('switch', { name: 'Bezovta qilmang (DND)' }));
    await user.click(screen.getByRole('button', { name: 'Saqlash' }));

    // Drawer yopiladi — saqlash muvaffaqiyatli.
    await waitFor(() => expect(screen.queryByRole('switch', { name: 'Bezovta qilmang (DND)' })).toBeNull());

    // Ro'yxat invalidatsiyadan keyin qayta so'raladi — "DND" belgisi ko'rinishini kutamiz.
    await waitFor(() => {
      const row = screen.getByRole('row', { name: /^103 / });
      expect(within(row).getByText('DND')).toBeTruthy();
    });

    // Qayta ochilganda — holat saqlangan.
    await user.click(screen.getByRole('button', { name: '103ni tahrirlash' }));
    expect(screen.getByRole('switch', { name: 'Bezovta qilmang (DND)' })).toHaveAttribute('aria-checked', 'true');

    const item = (await client.listExtensions({})).items.find((e) => e.number === '103');
    expect(item?.dnd).toBe(true);
  });

  it("o'ziga yo'naltirish — 422 bad_number xabari forward_always maydoni ostida chiqadi", async () => {
    const user = userEvent.setup();
    renderPage(<ExtensionsPage />);

    await user.click(await screen.findByRole('button', { name: '102ni tahrirlash' }));
    await user.type(screen.getByRole('textbox', { name: 'Har doim yoʻnaltirish' }), '102');
    await user.click(screen.getByRole('button', { name: 'Saqlash' }));

    expect(await screen.findByText(/oʻz raqamiga yoʻnaltirib boʻlmaydi/i)).toBeTruthy();
    // Drawer ochiq qolgan — saqlanmagan.
    expect(screen.getByRole('textbox', { name: 'Har doim yoʻnaltirish' })).toHaveValue('102');
    const item = (await client.listExtensions({})).items.find((e) => e.number === '102');
    expect(item?.forward_always).toBeNull();
  });

  it('Brauzer softfoni (WebRTC) yoqilgandan keyin roʻyxatda WebRTC belgisi chiqadi', async () => {
    const user = userEvent.setup();
    renderPage(<ExtensionsPage />);

    await user.click(await screen.findByRole('button', { name: '104ni tahrirlash' }));
    await user.click(screen.getByRole('switch', { name: 'Brauzer softfoni (WebRTC)' }));
    await user.click(screen.getByRole('button', { name: 'Saqlash' }));

    await waitFor(() => expect(screen.queryByRole('switch', { name: 'Brauzer softfoni (WebRTC)' })).toBeNull());
    await waitFor(() => {
      const row = screen.getByRole('row', { name: /^104 / });
      expect(within(row).getByText('WebRTC')).toBeTruthy();
    });
    const item = (await client.listExtensions({})).items.find((e) => e.number === '104');
    expect(item?.webrtc).toBe(true);
  });

  it('M3a §2 — kodekssiz webrtc yoqish uchun fake backend 422 webrtc_codec qaytaradi (field=codecs)', async () => {
    // 105 — boshqa testlar tegmaydigan ichki raqam (stale updated_at bilan to'qnashmasin).
    const current = (await client.listExtensions({})).items.find((e) => e.number === '105');
    await expect(client.updateExtension('e-105', { updated_at: current!.updated_at, webrtc: true, codecs: [] })).rejects.toMatchObject({
      status: 422, code: 'webrtc_codec', field: 'codecs',
    });
  });

  it('Apparatlar boʻlimi — biriktirilgan apparat koʻrinadi, boʻsh holatda yangi apparat qoʻshish ichki raqamni oʻzgartirmasdan ishlaydi', async () => {
    const user = userEvent.setup();
    renderPage(<ExtensionsPage />);

    await user.click(await screen.findByRole('button', { name: '103ni tahrirlash' }));
    expect(await screen.findByText('805ec0aa0001')).toBeTruthy();
    expect(screen.getByText('Roʻyxatda')).toBeTruthy();

    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByText('805ec0aa0001')).toBeNull());

    await user.click(await screen.findByRole('button', { name: '107ni tahrirlash' }));
    expect(await screen.findByText('Ushbu ichki raqamga apparat biriktirilmagan')).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Apparat qoʻshish' }));
    const dialog = screen.getByRole('dialog', { name: 'Apparat qoʻshish' });
    expect(within(dialog).queryByRole('combobox', { name: 'Ichki raqam' })).toBeNull();

    await user.type(within(dialog).getByRole('textbox', { name: 'MAC manzil' }), '001122334455');
    await user.click(within(dialog).getByRole('combobox', { name: 'Model' }));
    await user.click(await screen.findByRole('option', { name: 'T46U (27)' }));
    await user.click(within(dialog).getByRole('button', { name: 'Saqlash' }));

    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Apparat qoʻshish' })).toBeNull());
    expect(await screen.findByText('001122334455')).toBeTruthy();

    const item = (await client.listDevices({})).items.find((d) => d.mac === '001122334455');
    expect(item?.extension?.number).toBe('107');
  });

  it("operator — tahrirlash tugmasi o'chirilgan", async () => {
    await loginAs(client, 'operator');
    renderPage(<ExtensionsPage />);

    expect(await screen.findByText(/ruxsati yo/)).toBeTruthy();
    expect(await screen.findByRole('button', { name: '103ni tahrirlash' })).toBeDisabled();
  });

  it('M5b: QR tugmasi WebRTC raqamda oʻchiq; drawer ichida Follow Me, saqlangach ichki raqam tahriri stale olmaydi', async () => {
    await loginAs(client, 'admin');
    const user = userEvent.setup();
    renderPage(<ExtensionsPage />);

    expect(await screen.findByTestId('qr-open-101')).toBeDisabled();
    expect(screen.getByTestId('qr-open-103')).toBeEnabled();

    await user.click(screen.getByRole('button', { name: '103ni tahrirlash' }));
    const drawer = await screen.findByRole('dialog');
    await user.type(await within(drawer).findByTestId('fm-add-input'), '104{Enter}');
    await user.click(within(drawer).getByTestId('fm-save'));
    await waitFor(() => expect(within(drawer).getByTestId('fm-save')).toBeDisabled(), { timeout: 3000 });
    expect((await client.followMe('e-103')).follow_me.numbers).toEqual(['104']);

    // Follow Me ichki raqam updated_at'ini oshirdi — asosiy forma yangi qiymat bilan saqlanishi kerak.
    // (Avvalgi testlar shu klientda 103 ni o'zgartirgan bo'lishi mumkin — nisbiy tekshiramiz.)
    const dndBefore = (await client.listExtensions({})).items.find((e) => e.id === 'e-103')?.dnd;
    await user.click(within(drawer).getByRole('switch', { name: 'Bezovta qilmang (DND)' }));
    await user.click(within(drawer).getByRole('button', { name: 'Saqlash' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull(), { timeout: 3000 });
    expect((await client.listExtensions({})).items.find((e) => e.id === 'e-103')?.dnd).toBe(!dndBefore);

    // Teskarisi: raqam saqlangach drawer qayta ochilsa, Follow Me keshi eski updated_at bilan qolmasin (409 stale).
    await user.click(screen.getByRole('button', { name: '103ni tahrirlash' }));
    const again = await screen.findByRole('dialog');
    await user.type(await within(again).findByTestId('fm-add-input'), '105{Enter}');
    await user.click(within(again).getByTestId('fm-save'));
    await waitFor(() => expect(within(again).getByTestId('fm-save')).toBeDisabled(), { timeout: 3000 });
    expect(within(again).queryByRole('button', { name: 'Qayta yuklash' })).toBeNull();
    expect((await client.followMe('e-103')).follow_me.numbers).toEqual(['104', '105']);
  });
});

describe('ExtensionsPage — yangi ichki raqam yaratish (SIP parol)', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it("o'z parolini kiritib yaratish — SIP oynasida login=raqam, kiritilgan parol koʻrsatiladi", async () => {
    const user = userEvent.setup();
    renderPage(<ExtensionsPage />);

    await user.click(await screen.findByRole('button', { name: 'Yangi ichki raqam' }));
    const modal = await screen.findByRole('dialog', { name: 'Yangi ichki raqam' });
    await user.type(within(modal).getByRole('textbox', { name: 'Nom' }), 'Test Foydalanuvchi');

    const passwordInput = within(modal).getByLabelText(/SIP paroli/);
    await user.clear(passwordInput);
    await user.type(passwordInput, 'MySecret123');

    await user.click(within(modal).getByRole('button', { name: 'Yaratish' }));

    const sipDialog = await screen.findByRole('dialog', { name: /SIP maʼlumotlari/ });
    const newNumber = (await client.listExtensions({})).items.find((e) => e.name === 'Test Foydalanuvchi')!.number;
    expect(within(sipDialog).getByText(newNumber)).toBeTruthy();
    expect(within(sipDialog).getByText('MySecret123')).toBeTruthy();
  });

  it('zaif parol — Yaratish tugmasi oʻchiq, maydon ostida xato koʻrinadi', async () => {
    const user = userEvent.setup();
    renderPage(<ExtensionsPage />);

    await user.click(await screen.findByRole('button', { name: 'Yangi ichki raqam' }));
    const modal = await screen.findByRole('dialog', { name: 'Yangi ichki raqam' });
    await user.type(within(modal).getByRole('textbox', { name: 'Nom' }), 'Zaif Parol');

    const passwordInput = within(modal).getByLabelText(/SIP paroli/);
    await user.clear(passwordInput);
    await user.type(passwordInput, '1234567');

    expect(await within(modal).findByText('Parol kamida 8 belgidan iborat boʻlsin.')).toBeTruthy();
    expect(within(modal).getByRole('button', { name: 'Yaratish' })).toBeDisabled();
  });

  it('qoʻshimcha sozlamalar — DND va «Har doim» yozib olish yaratishda saqlanadi', async () => {
    const user = userEvent.setup();
    renderPage(<ExtensionsPage />);

    await user.click(await screen.findByRole('button', { name: 'Yangi ichki raqam' }));
    const modal = await screen.findByRole('dialog', { name: 'Yangi ichki raqam' });
    await user.type(within(modal).getByRole('textbox', { name: 'Nom' }), 'Qoʻshimcha Sozlama');

    await user.click(within(modal).getByRole('button', { name: 'Qoʻshimcha sozlamalar' }));
    await user.click(within(modal).getByRole('switch', { name: 'Bezovta qilmang (DND)' }));
    await user.click(within(modal).getByRole('combobox', { name: 'Yozib olish' }));
    await user.click(await screen.findByRole('option', { name: 'Har doim' }));

    await user.click(within(modal).getByRole('button', { name: 'Yaratish' }));
    await screen.findByRole('dialog', { name: /SIP maʼlumotlari/ });

    const item = (await client.listExtensions({})).items.find((e) => e.name === 'Qoʻshimcha Sozlama');
    expect(item?.dnd).toBe(true);
    expect(item?.recording).toBe('always');
  });
});

describe('ExtensionsPage — SIP parolini almashtirish', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it("oʻz parolini kiritib almashtirish — muvaffaqiyat, yangi SIP oynasi koʻrinadi", async () => {
    const user = userEvent.setup();
    renderPage(<ExtensionsPage />);

    await user.click(await screen.findByRole('button', { name: '108ni tahrirlash' }));
    const drawer = await screen.findByRole('dialog');
    await user.click(within(drawer).getByRole('button', { name: 'Oʻz parolimni kiritaman' }));

    const newPasswordInput = within(drawer).getByLabelText(/Yangi parol/);
    await user.type(newPasswordInput, 'NewSecret123');
    await user.click(within(drawer).getByTestId('change-password-save'));

    const sipDialog = await screen.findByRole('dialog', { name: /yangi SIP maʼlumotlari/ });
    expect(within(sipDialog).getByText('NewSecret123')).toBeTruthy();
  });

  it('yangi tasodifiy parol generatsiya qilish — muvaffaqiyat', async () => {
    const user = userEvent.setup();
    renderPage(<ExtensionsPage />);

    await user.click(await screen.findByRole('button', { name: '106ni tahrirlash' }));
    const drawer = await screen.findByRole('dialog');
    await user.click(within(drawer).getByRole('button', { name: 'Yangi tasodifiy parol' }));

    await screen.findByRole('dialog', { name: /yangi SIP maʼlumotlari/ });
  });
});
