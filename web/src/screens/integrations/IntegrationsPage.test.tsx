// Xatti-harakat testi — API kalitlari, vebhuklar (validatsiya/sinov/yetkazishlar), CRM ulanish sinovi.
// Qarang ../../../replica/m3b-contract.md §3-5.
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

const { IntegrationsPage } = await import('./IntegrationsPage');
const { bitrixHookUrl } = await import('./CrmTab');

describe('IntegrationsPage', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('API kalit yaratish — sir bir martalik koʻrsatiladi, keyin bekor qilinadi', async () => {
    const user = userEvent.setup();
    renderPage(<IntegrationsPage />);

    await user.click(await screen.findByRole('tab', { name: 'API kalitlari' }));
    await user.click(screen.getByTestId('apikey-create'));
    await user.type(screen.getByRole('textbox', { name: 'Nomi' }), 'Test kaliti');
    await user.click(screen.getByRole('checkbox', { name: 'Qoʻngʻiroqlarni oʻqish' }));
    await user.click(screen.getByRole('button', { name: 'Kalit yaratish' }));

    const secret = await screen.findByTestId('apikey-secret');
    expect(secret.textContent).toMatch(/^ipk_/);
    const closeButtons = screen.getAllByRole('button', { name: 'Yopish' });
    await user.click(closeButtons.at(-1)!);

    await user.click(screen.getByTestId('apikey-revoke-ak-1c'));
    await user.click(screen.getByRole('button', { name: 'Ha, bekor qilish' }));
    await waitFor(async () => expect((await client.listApiKeys()).items.find((k) => k.id === 'ak-1c')?.revoked_at).not.toBeNull());
  });

  it('API kalit yaratish — nom va ruxsatlar boʻlmasa xato koʻrsatadi', async () => {
    const user = userEvent.setup();
    renderPage(<IntegrationsPage />);

    await user.click(await screen.findByRole('tab', { name: 'API kalitlari' }));
    await user.click(screen.getByTestId('apikey-create'));
    await user.click(screen.getByRole('button', { name: 'Kalit yaratish' }));

    expect(await screen.findByText('Nom kiritilishi shart.')).toBeTruthy();

    await user.type(screen.getByRole('textbox', { name: 'Nomi' }), 'Boʻsh ruxsatli kalit');
    await user.click(screen.getByRole('button', { name: 'Kalit yaratish' }));
    expect(await screen.findByText('Kamida bitta ruxsat tanlang.')).toBeTruthy();
  });

  it('vebhuk yaratish — taqiqlangan manzil 422 xatosini koʻrsatadi, toʻgʻri manzil sirni koʻrsatadi', async () => {
    const user = userEvent.setup();
    renderPage(<IntegrationsPage />);

    await user.click(await screen.findByRole('tab', { name: 'Vebhuklar' }));
    await user.click(screen.getByTestId('webhook-create'));
    await user.type(screen.getByRole('textbox', { name: 'Nomi' }), 'Test vebhuk');
    await user.type(screen.getByRole('textbox', { name: 'Manzil (URL)' }), 'http://localhost/hook');
    await user.click(screen.getByRole('checkbox', { name: 'Tugadi' }));
    await user.click(screen.getByRole('button', { name: 'Vebhuk qoʻshish' }));

    expect(await screen.findByText('Bu manzilga vebhuk yuborish taqiqlangan (loopback/tizim xosti).')).toBeTruthy();

    const urlField = screen.getByRole('textbox', { name: 'Manzil (URL)' });
    await user.clear(urlField);
    await user.type(urlField, 'https://crm.example.com/hook');
    await user.click(screen.getByRole('button', { name: 'Vebhuk qoʻshish' }));

    expect(await screen.findByTestId('webhook-secret')).toBeTruthy();
  });

  it('yetkazishlar jurnali — oʻchirilgan vebhukning xato yetkazishlarini qayta yuborish mumkin', async () => {
    const user = userEvent.setup();
    renderPage(<ToastProvider><IntegrationsPage /></ToastProvider>);

    await user.click(await screen.findByRole('tab', { name: 'Vebhuklar' }));
    await user.click(await screen.findByTestId('webhook-deliveries-wh-broken'));

    const replay = await screen.findByTestId('delivery-replay-dl-1');
    await user.click(replay);
    expect(await screen.findByText('Qayta navbatga qoʻyildi.')).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Sirni almashtirish' }));
    expect(await screen.findByTestId('webhook-secret')).toBeTruthy();
  });

  it('vebhuk yaratish — hodisa tanlanmasa xato koʻrsatadi', async () => {
    const user = userEvent.setup();
    renderPage(<IntegrationsPage />);

    await user.click(await screen.findByRole('tab', { name: 'Vebhuklar' }));
    await user.click(screen.getByTestId('webhook-create'));
    await user.type(screen.getByRole('textbox', { name: 'Nomi' }), 'Hodisasiz vebhuk');
    await user.type(screen.getByRole('textbox', { name: 'Manzil (URL)' }), 'https://crm.example.com/hook');
    await user.click(screen.getByRole('button', { name: 'Vebhuk qoʻshish' }));

    expect(await screen.findByText('Kamida bitta hodisa tanlang.')).toBeTruthy();
  });

  it('Bitrix24 — sozlanmagan holatda ulanish sinovi muvaffaqiyatsiz boʻladi', async () => {
    const user = userEvent.setup();
    renderPage(<ToastProvider><IntegrationsPage /></ToastProvider>);

    await user.click(await screen.findByRole('tab', { name: 'Bitrix24' }));
    const form = await screen.findByTestId('crm-bitrix24-form');
    expect(within(form).getByText('Bitrix24 integratsiyasi yoqilgan')).toBeTruthy();
    const hook = within(form).getByDisplayValue(/\/api\/public\/v1\/crm\/bitrix24\/.+\/call$/) as HTMLInputElement;
    expect(hook.value.startsWith(`${window.location.origin}/api/`)).toBe(true);

    await user.click(screen.getByTestId('crm-test'));
    expect(await screen.findByText('Ulanish muvaffaqiyatsiz.')).toBeTruthy();
  });

  it('Bitrix24 — notoʻgʻri vebhuk manzili xato koʻrsatadi, toʻgʻri manzil saqlanadi', async () => {
    const user = userEvent.setup();
    renderPage(<ToastProvider><IntegrationsPage /></ToastProvider>);

    await user.click(await screen.findByRole('tab', { name: 'Bitrix24' }));
    const form = await screen.findByTestId('crm-bitrix24-form');
    const urlField = within(form).getByRole('textbox', { name: 'Kiruvchi vebhuk manzili' });
    await user.type(urlField, 'https://notogri-manzil');
    await user.click(within(form).getByRole('button', { name: 'Saqlash' }));
    expect(await screen.findByText(/Bitrix24 kiruvchi vebhuk manzili notoʻgʻri/)).toBeTruthy();

    await user.clear(urlField);
    await user.type(urlField, 'https://portal.bitrix24.ru/rest/1/abcdef12345/');
    await user.click(within(form).getByRole('button', { name: 'Saqlash' }));
    expect(await screen.findByText('Saqlandi.')).toBeTruthy();
  });

  it('Umumiy — kartalar holati koʻrinadi, "Sozlash" tegishli tabga olib boradi', async () => {
    const user = userEvent.setup();
    renderPage(<IntegrationsPage />);

    const restCard = (await screen.findByRole('heading', { name: 'REST API' })).closest('div')!.parentElement!;
    expect(await within(restCard).findByText('Ishlayapti')).toBeTruthy();

    const webhooksCard = screen.getByRole('heading', { name: 'Vebhuklar' }).closest('div')!.parentElement!;
    await user.click(within(webhooksCard).getByRole('button', { name: 'Sozlash' }));
    await screen.findByTestId('webhook-create');
  });

  it('amoCRM — forma koʻrinadi, sozlamalarni saqlash muvaffaqiyatli boʻladi', async () => {
    const user = userEvent.setup();
    renderPage(<ToastProvider><IntegrationsPage /></ToastProvider>);

    await user.click(await screen.findByRole('tab', { name: 'amoCRM' }));
    const form = await screen.findByTestId('crm-amocrm-form');
    expect(within(form).getByText('amoCRM integratsiyasi yoqilgan')).toBeTruthy();

    await user.click(within(form).getByRole('button', { name: 'Saqlash' }));
    expect(await screen.findByText('Saqlandi.')).toBeTruthy();
  });

  it('amoCRM — notoʻgʻri portal manzili xato koʻrsatadi', async () => {
    const user = userEvent.setup();
    renderPage(<ToastProvider><IntegrationsPage /></ToastProvider>);

    await user.click(await screen.findByRole('tab', { name: 'amoCRM' }));
    const form = await screen.findByTestId('crm-amocrm-form');
    const urlField = within(form).getByRole('textbox', { name: 'Portal manzili' });
    await user.clear(urlField);
    await user.type(urlField, 'https://notogri.example.com');
    await user.click(within(form).getByRole('button', { name: 'Saqlash' }));
    expect(await screen.findByText(/Manzil notoʻgʻri/)).toBeTruthy();
  });

  it('vebhukni tahrirlash — mavjud qiymatlar bilan ochiladi va saqlanadi', async () => {
    const user = userEvent.setup();
    renderPage(<ToastProvider><IntegrationsPage /></ToastProvider>);

    await user.click(await screen.findByRole('tab', { name: 'Vebhuklar' }));
    const row = await screen.findByRole('row', { name: /amoCRM — eski integratsiya/ });
    await user.click(within(row).getByRole('button', { name: 'Tahrirlash' }));

    const urlField = await screen.findByRole('textbox', { name: 'Manzil (URL)' });
    expect((urlField as HTMLInputElement).value).not.toBe('');
    await user.click(screen.getByRole('button', { name: 'Saqlash' }));
    expect(await screen.findByText('Saqlandi.')).toBeTruthy();
  });

  it('vebhukni tahrirlash — boshqa joyda oʻzgartirilgan boʻlsa 409 xato koʻrsatadi', async () => {
    const user = userEvent.setup();
    renderPage(<ToastProvider><IntegrationsPage /></ToastProvider>);

    await user.click(await screen.findByRole('tab', { name: 'Vebhuklar' }));
    const row = await screen.findByRole('row', { name: /amoCRM — eski integratsiya/ });
    await user.click(within(row).getByRole('button', { name: 'Tahrirlash' }));
    await screen.findByRole('textbox', { name: 'Manzil (URL)' });

    const current = (await client.listWebhooks()).items.find((w) => w.id === 'wh-amo')!;
    await client.updateWebhook('wh-amo', { name: current.name, updated_at: current.updated_at });

    await user.click(screen.getByRole('button', { name: 'Saqlash' }));
    expect(await screen.findByText(/boshqa joyda oʻzgartirilgan/)).toBeTruthy();
  });

  it('Sozlamalar — public_base_url saqlanadi', async () => {
    const user = userEvent.setup();
    renderPage(<ToastProvider><IntegrationsPage /></ToastProvider>);

    await user.click(await screen.findByRole('tab', { name: 'Sozlamalar' }));
    const urlField = await screen.findByRole('textbox', { name: 'Ochiq (public) manzil' });
    await user.clear(urlField);
    await user.type(urlField, 'https://pbx.sinov.uz');
    await user.click(screen.getAllByRole('button', { name: 'Saqlash' }).at(0)!);
    expect(await screen.findAllByText('Saqlandi.')).not.toHaveLength(0);
  });

  it('Sozlamalar — boshqa joyda oʻzgartirilgan (409 stale) banner koʻrsatadi', async () => {
    const user = userEvent.setup();
    renderPage(<ToastProvider><IntegrationsPage /></ToastProvider>);

    await user.click(await screen.findByRole('tab', { name: 'Sozlamalar' }));
    const before = await client.integrationsSettings();
    await client.updateIntegrationsSettings({ public_base_url: 'https://boshqa-joyda.uz', updated_at: before.updated_at });

    await user.click(screen.getAllByRole('button', { name: 'Saqlash' }).at(0)!);
    expect(await screen.findByText(/boshqa joyda/i)).toBeTruthy();

    const beforeRec = await client.recordingSettings();
    await client.updateRecordingSettings({ retention_days: 30, updated_at: beforeRec.updated_at });

    await user.click(screen.getAllByRole('button', { name: 'Saqlash' }).at(1)!);
    await waitFor(() => expect(screen.getAllByText(/boshqa joyda/i).length).toBeGreaterThan(1));
  });

  it('1C — namunalar roʻyxati koʻrinadi, yuklab olish faylni oladi', async () => {
    const user = userEvent.setup();
    renderPage(<IntegrationsPage />);

    await user.click(await screen.findByRole('tab', { name: '1C' }));
    const downloadButtons = await screen.findAllByRole('button', { name: 'Yuklab olish' });
    expect(downloadButtons.length).toBeGreaterThan(0);
  });

  // Diqqat: bu test modul darajasidagi ulashiladigan `client`dan 'wh-amo'ni butunlay o'chiradi —
  // shuning uchun 'wh-amo'ga tayanadigan boshqa testlardan KEYIN turishi kerak.
  it('vebhukni oʻchirish — tasdiqlash oynasi orqali oʻchiriladi', async () => {
    const user = userEvent.setup();
    renderPage(<IntegrationsPage />);

    await user.click(await screen.findByRole('tab', { name: 'Vebhuklar' }));
    const row = await screen.findByRole('row', { name: /amoCRM — eski integratsiya/ });
    await user.click(within(row).getByRole('button', { name: 'Oʻchirish' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Oʻchirish' }));

    await waitFor(async () => expect((await client.listWebhooks()).items.find((w) => w.id === 'wh-amo')).toBeUndefined());
  });

  it('Sozlamalar — Yandex SpeechKit (yangi oʻrnatish, updated_at=null) tanlab API kalit/katalog/ovoz kiritiladi va sinaladi', async () => {
    const user = userEvent.setup();
    renderPage(<ToastProvider><IntegrationsPage /></ToastProvider>);

    await user.click(await screen.findByRole('tab', { name: 'Sozlamalar' }));
    await user.click(await screen.findByRole('combobox', { name: 'Provayder' }));
    await user.click(await screen.findByRole('option', { name: 'Yandex SpeechKit' }));

    await user.type(screen.getByLabelText('API kalit'), 'AQVN-sinov-kaliti');
    await user.type(screen.getByRole('textbox', { name: 'Katalog ID (folder_id)' }), 'b1g...sinov');
    await user.click(screen.getAllByRole('button', { name: 'Saqlash' }).at(2)!);
    expect(await screen.findAllByText('Saqlandi.')).not.toHaveLength(0);

    await user.click(screen.getByRole('button', { name: 'Sinash' }));
    expect(await screen.findByText('Ulanish muvaffaqiyatli.')).toBeTruthy();

    const settings = await client.getTtsSettings();
    expect(settings.provider).toBe('yandex');
    expect(settings.has_api_key).toBe(true);
  });

  it('API kalitlari — WebSocket ulanish namunasi koʻrsatiladi, nusxalash tugmasi ishlaydi', async () => {
    const user = userEvent.setup();
    renderPage(<ToastProvider><IntegrationsPage /></ToastProvider>);

    await user.click(await screen.findByRole('tab', { name: 'API kalitlari' }));
    expect(await screen.findByText('WebSocket ulanish namunasi')).toBeTruthy();
    expect(screen.getByText(/new WebSocket/)).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Nusxalash' }));
    expect(await screen.findByText('Nusxalandi')).toBeTruthy();
  });

  it('oʻqish huquqisiz (operator) — faqat koʻrish banneri chiqadi, "Kalit yaratish" tugmasi yoʻq', async () => {
    await useSession.getState().clear();
    await loginAs(client, 'operator');
    renderPage(<IntegrationsPage />);

    expect(await screen.findByText(/Faqat koʻrish/)).toBeTruthy();
    await userEvent.setup().click(screen.getByRole('tab', { name: 'API kalitlari' }));
    expect(screen.queryByTestId('apikey-create')).toBeNull();
  });
});

describe('bitrixHookUrl', () => {
  it.each([
    ['https://pbx.firma.uz/', 'https://pbx.firma.uz/api/public/v1/crm/bitrix24/tok/call'],
    [null, 'http://10.0.0.5:8080/api/public/v1/crm/bitrix24/tok/call'],
    ['', 'http://10.0.0.5:8080/api/public/v1/crm/bitrix24/tok/call'],
  ])('%j → %s', (base, out) => expect(bitrixHookUrl('tok', base, 'http://10.0.0.5:8080')).toBe(out));
});
