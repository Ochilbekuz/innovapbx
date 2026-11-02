// Xatti-harakat testi — S18 to'liq oqim: yaratish → CSV import → boshlash/pauza/to'xtatish, kontaktlar, tahrir, o'chirish.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import type { CampaignContact } from '@/api/types';
import { loginAs, renderPage } from '@/test-pages';
import { ToastProvider } from '@/ui/Toast';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { CampaignsPage } = await import('./CampaignsPage');
const { contactDetails } = await import('./ContactsPanel');
const { splitFormError } = await import('./CampaignForm');
const { ApiError } = await import('@/api/errors');

const NAME = 'Noyabr eslatmasi';
/** 30 ta yaroqli raqam + takror + yaroqsiz qator. */
const CSV = ['raqam,ism', ...Array.from({ length: 30 }, (_, i) => `9011122${String(i).padStart(2, '0')},Mijoz ${i}`), '901112200', 'xx'].join('\n');

async function openRowAction(label: string) {
  fireEvent.click(await screen.findByRole('button', { name: label }));
  return screen.findByRole('dialog');
}

describe('kampaniya oqimi', () => {
  afterEach(() => useSession.getState().clear());

  it('yaratish → import → boshlash → pauza → to\'xtatish', async () => {
    const user = userEvent.setup();
    await loginAs(client, 'admin');
    renderPage(<ToastProvider><CampaignsPage /></ToastProvider>);

    const form = await openRowAction('Yangi kampaniya');
    fireEvent.change(within(form).getByLabelText(/Nomi/), { target: { value: NAME } });
    await user.click(within(form).getByRole('combobox', { name: /Audio xabar/ }));
    await user.click(await screen.findByRole('option', { name: /Standart salomlashuv/ }));
    await user.click(within(form).getByRole('switch', { name: /«1» — operatorga ulash/ }));
    fireEvent.change(within(form).getByLabelText(/Kimga ulanadi/), { target: { value: ' 600 ' } });
    await user.click(within(form).getByRole('button', { name: 'Ya' }));
    expect(within(form).getByRole('button', { name: 'Ya' }).getAttribute('aria-pressed')).toBe('true');
    fireEvent.change(within(form).getByLabelText(/Bir vaqtda/), { target: { value: '5x' } });
    fireEvent.change(within(form).getByLabelText(/Oraliq, daqiqa/), { target: { value: '20' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Yaratish' }));

    expect(await screen.findByText('Kampaniya yaratildi — endi raqamlarni yuklang')).toBeTruthy();
    const card = await screen.findByRole('dialog', { name: NAME });
    expect((within(card).getByRole('button', { name: 'Boshlash' }) as HTMLButtonElement).disabled).toBe(true);

    fireEvent.change(within(card).getByRole('textbox', { name: 'Raqamlarni yuklash' }), { target: { value: CSV } });
    expect(within(card).getByText('30 ta yangi raqam · 1 takror · 1 yaroqsiz')).toBeTruthy();
    expect(within(card).getByText('33-qator: «xx»')).toBeTruthy();
    fireEvent.click(within(card).getByRole('button', { name: 'Yuklash' }));
    expect(await within(card).findByText('30 ta qoʻshildi · 0 oʻtkazildi · 1 takror · 1 yaroqsiz')).toBeTruthy();
    expect(await within(card).findByText('1–25 / 30')).toBeTruthy();

    fireEvent.click(within(card).getByRole('button', { name: 'Keyingi sahifa' }));
    expect(await within(card).findByText('26–30 / 30')).toBeTruthy();
    fireEvent.change(within(card).getByLabelText('Raqam yoki ism'), { target: { value: 'Mijoz 7' } });
    expect(await within(card).findByText('901112207')).toBeTruthy();
    await waitFor(() => expect(within(card).queryByText('901112208')).toBeNull());

    fireEvent.click(await within(card).findByRole('button', { name: 'Boshlash' }));
    expect(await screen.findByText(`«${NAME}» boshlandi`)).toBeTruthy();
    fireEvent.click(await within(card).findByRole('button', { name: 'Pauza' }));
    expect(await screen.findByText(`«${NAME}» pauzaga qoʻyildi`)).toBeTruthy();
    expect(await within(card).findByRole('button', { name: 'Davom ettirish' })).toBeTruthy();

    fireEvent.click(within(card).getByRole('button', { name: 'Toʻxtatish' }));
    const confirm = await screen.findByRole('dialog', { name: `«${NAME}» toʻxtatilsinmi?` });
    fireEvent.click(within(confirm).getByRole('button', { name: 'Toʻxtatish' }));
    expect(await screen.findByText(`«${NAME}» toʻxtatildi`)).toBeTruthy();
    expect(await within(card).findByText('Tugagan kampaniyaga raqam qoʻshilmaydi — yangisini yarating.')).toBeTruthy();
    expect(within(card).queryAllByText('Navbatda', { selector: 'span' }).filter((el) => el.closest('li'))).toHaveLength(0);
    expect(within(card).getAllByText(/Kampaniya toʻxtatildi/).length).toBeGreaterThan(0);
  }, 15_000); // to'liq oqim ~4 s — yuklamada 5 s sukut yetmaydi

  it('holat filtri va CSV eksport', async () => {
    const user = userEvent.setup();
    const createObjectURL = vi.fn(() => 'blob:x');
    Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    await loginAs(client, 'admin');
    renderPage(<ToastProvider><CampaignsPage /></ToastProvider>);

    fireEvent.click(await screen.findByRole('button', { name: 'Qarzdorlik eslatmasi — oktyabr' }));
    const card = await screen.findByRole('dialog');
    await user.click(within(card).getByRole('combobox', { name: 'Holat boʻyicha' }));
    await user.click(await screen.findByRole('option', { name: 'Oʻtkazib yuborildi' }));
    expect(await within(card).findByText('998998887766')).toBeTruthy();
    fireEvent.click(within(card).getByRole('button', { name: 'CSV yuklab olish' }));
    await waitFor(() => expect(createObjectURL).toHaveBeenCalledOnce());
  });

  it('tahrirlash: server xatosi maydon ostida, to\'g\'ri qiymat saqlanadi', async () => {
    await loginAs(client, 'admin');
    renderPage(<ToastProvider><CampaignsPage /></ToastProvider>);

    const form = await openRowAction('«Yangi tarif — sodiq mijozlar» ni tahrirlash');
    expect(within(form).getAllByText('«Yangi tarif — sodiq mijozlar» — tahrirlash').length).toBeGreaterThan(0);
    const target = within(form).getByLabelText(/Kimga ulanadi/);
    fireEvent.change(target, { target: { value: '6' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Saqlash' }));
    await waitFor(() => expect(target.getAttribute('aria-invalid')).toBe('true'));
    fireEvent.change(target, { target: { value: '600' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Saqlash' }));
    expect(await screen.findByText('Oʻzgarishlar saqlandi')).toBeTruthy();
  });

  it('o\'chirish tasdiq bilan', async () => {
    await loginAs(client, 'admin');
    renderPage(<ToastProvider><CampaignsPage /></ToastProvider>);

    const confirm = await openRowAction(`«${NAME}» ni oʻchirish`);
    fireEvent.click(within(confirm).getByRole('button', { name: 'Oʻchirish' }));
    expect(await screen.findByText(`«${NAME}» oʻchirildi`)).toBeTruthy();
    await waitFor(() => expect(screen.queryByRole('button', { name: NAME })).toBeNull());
  });

  it('ruxsatsiz foydalanuvchi — faqat ko\'rish', async () => {
    await loginAs(client, 'operator');
    renderPage(<ToastProvider><CampaignsPage /></ToastProvider>);
    expect(await screen.findByText(/faqat koʻrish mumkin/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Yangi kampaniya' })).toBeNull();
  });
});

describe('yordamchilar', () => {
  const t = (key: string, o?: Record<string, unknown>) => (o ? `${key}:${Object.values(o).join('/')}` : key);
  const contact = (p: Partial<CampaignContact>): CampaignContact => ({
    id: 1, number: '101', name: null, status: 'done', attempts: 0, result: null, key: null, billsec: null,
    last_attempt_at: null, next_attempt_at: null, ...p,
  });

  it('contactDetails bo\'shlarni tashlab yuboradi', () => {
    expect(contactDetails(contact({}), t)).toBe('');
    expect(contactDetails(contact({ result: 'ANSWER', key: '1', billsec: 12, attempts: 2 }), t))
      .toBe('result.ANSWER:ANSWER · detail.pressed:1 · detail.billsec:12 · detail.attempts:2');
  });

  it('splitFormError: maydonli xato maydonga, qolgani umumiy', () => {
    const field = new ApiError(422, { code: 'campaign_window', message: 'oyna', field: 'window_end' });
    expect(splitFormError(field).fieldError('window_end')).toBeTruthy();
    expect(splitFormError(field).general).toBeNull();
    expect(splitFormError(new ApiError(409, { code: 'stale', message: 'eski' })).general).toBeTruthy();
    expect(splitFormError(null).general).toBeNull();
  });
});
