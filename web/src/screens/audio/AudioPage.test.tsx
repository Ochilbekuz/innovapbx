// Xatti-harakat testi — M10 C A3: "Matndan audio yaratish" (TTS) kartasi/dialogi.
// Qarang ../../../replica/m10-onlinepbx-contract.md §A3.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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

const { AudioPage } = await import('./AudioPage');

describe('AudioPage — TTS (matndan audio)', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('sozlanmagan boʻlsa — admin uchun sozlash havolasi koʻrsatiladi, dialog ochilmaydi', async () => {
    renderPage(<AudioPage />);

    expect(await screen.findByText('Nutq sintezi sozlanmagan.')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Sozlashga oʻtish' })).toHaveAttribute('href', '/settings/integrations');
    expect(screen.queryByRole('button', { name: 'Boshlash' })).toBeNull();
  });

  it('sozlangan boʻlsa — matn kiritib tinglab koʻrish va saqlash audio kutubxonaga qoʻshadi', async () => {
    const before = await client.getTtsSettings();
    await client.updateTtsSettings({ provider: 'yandex', api_key: 'sinov-kalit', updated_at: before.updated_at });

    const user = userEvent.setup();
    renderPage(<ToastProvider><AudioPage /></ToastProvider>);

    await user.click(await screen.findByRole('button', { name: 'Boshlash' }));
    await screen.findByRole('dialog', { name: 'Matndan audio yaratish' });

    await user.type(screen.getByRole('textbox', { name: 'Audio nomi' }), 'Sinov salomlashuvi');
    await user.type(screen.getByRole('textbox', { name: 'Matn' }), 'Assalomu alaykum, bu sinov matni.');

    await user.click(screen.getByRole('button', { name: 'Tinglab koʻrish' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Tinglash' })).toBeEnabled());

    await user.click(screen.getByRole('button', { name: 'Saqlash' }));

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(await screen.findByText(/Sinov salomlashuvi/)).toBeTruthy();
    expect((await client.listAudio()).items.some((a) => a.name === 'Sinov salomlashuvi')).toBe(true);
  });

  it('MOH: "Asosiy qilish" — boshqa sinfni asosiy qiladi, eski asosiy belgisi koʻchadi, uni oʻchirib boʻlmaydi', async () => {
    const user = userEvent.setup();
    renderPage(<ToastProvider><AudioPage /></ToastProvider>);

    await user.click(await screen.findByRole('tab', { name: 'Kutish musiqasi' }));

    await user.click(await screen.findByRole('button', { name: 'testni asosiy qilish' }));
    await waitFor(async () => expect((await client.listMohClasses()).items.find((m) => m.id === 'moh-test')?.is_default).toBe(true));

    expect(await screen.findByText('«test» asosiy kutish musiqasi qilindi')).toBeTruthy();
    await waitFor(() => expect(screen.getByRole('button', { name: 'testni oʻchirish' })).toBeDisabled());
    expect(screen.queryByRole('button', { name: 'testni asosiy qilish' })).toBeNull();
    // Asosiylik "default"dan "test"ga koʻchdi — endi "default"ni qayta asosiy qilish mumkin, uni oʻchirish ham mumkin.
    expect(screen.getByRole('button', { name: 'defaultni asosiy qilish' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'defaultni oʻchirish' })).toBeEnabled();
  });

  it('boʻsh matn bilan saqlash/tinglab koʻrish tugmalari oʻchiq boʻladi', async () => {
    const before = await client.getTtsSettings();
    await client.updateTtsSettings({ provider: 'yandex', api_key: 'sinov-kalit-2', updated_at: before.updated_at });

    const user = userEvent.setup();
    renderPage(<AudioPage />);

    await user.click(await screen.findByRole('button', { name: 'Boshlash' }));
    await screen.findByRole('dialog', { name: 'Matndan audio yaratish' });

    expect(screen.getByRole('button', { name: 'Tinglab koʻrish' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Saqlash' })).toBeDisabled();
  });
});

// i18n'da noto'g'ri yo'l bilan chaqirilgan kalit yoki tarjimasiz enum qiymat ishlab chiqarishda
// xomligicha ko'rinadi — shuni ushlab oladigan regex (queues/ringgroups'dagi bilan bir xil naqsh,
// "nameHint" kabi bitta-do'ngli kalitlarni ham, \b chegarasiz qo'shilib ketgan DOM matnini ham ushlaydi).
const RAW_KEY_RE = /[a-z](Label|Desc|Hint|Title|Option)(?![a-z])/;
const RAW_SECTION_RE = /section\./i;
const RAW_ENUM_VALUES = new Set(['none', 'once', 'strict', 'loose', 'limit', 'more']);

describe('AudioPage — dialoglarda xom i18n kalit yoki tarjimasiz enum yo‘q', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('"Matndan audio yaratish" dialogida xom kalit yoki tarjimasiz enum ko‘rinmaydi', async () => {
    const before = await client.getTtsSettings();
    await client.updateTtsSettings({ provider: 'yandex', api_key: 'sinov-kalit-3', updated_at: before.updated_at });

    const user = userEvent.setup();
    renderPage(<ToastProvider><AudioPage /></ToastProvider>);

    await user.click(await screen.findByRole('button', { name: 'Boshlash' }));
    const dialog = await screen.findByRole('dialog', { name: 'Matndan audio yaratish' });
    const text = dialog.textContent ?? '';
    expect(text).not.toMatch(RAW_KEY_RE);
    expect(text).not.toMatch(RAW_SECTION_RE);

    for (const combobox of within(dialog).queryAllByRole('combobox')) {
      const shown = (combobox.textContent ?? '').trim().toLowerCase();
      expect(RAW_ENUM_VALUES.has(shown)).toBe(false);
    }
  });

  it('kutish musiqasi "Yangi sinf" drawer\'ida xom kalit yoki tarjimasiz enum ko‘rinmaydi', async () => {
    const user = userEvent.setup();
    renderPage(<ToastProvider><AudioPage /></ToastProvider>);

    await user.click(await screen.findByRole('tab', { name: 'Kutish musiqasi' }));
    await user.click(await screen.findByRole('button', { name: 'Yangi sinf' }));

    const dialog = await screen.findByRole('dialog');
    const text = dialog.textContent ?? '';
    expect(text).not.toMatch(RAW_KEY_RE);
    expect(text).not.toMatch(RAW_SECTION_RE);

    for (const combobox of within(dialog).queryAllByRole('combobox')) {
      const shown = (combobox.textContent ?? '').trim().toLowerCase();
      expect(RAW_ENUM_VALUES.has(shown)).toBe(false);
    }
  });
});
