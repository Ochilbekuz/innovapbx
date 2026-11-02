// Xatti-harakat testi — sozlamalar, chat ID boshqarish, sinov xabari, tarix.
// Qarang ../../../replica/m2c-contract.md §4.
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
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

const { AlertsPage } = await import('./AlertsPage');

describe('AlertsPage', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it('token sozlanmagan — ogohlantirish banneri va /settings/sip havolasi koʻrinadi', async () => {
    renderPage(<AlertsPage />);
    expect(await screen.findByText('Telegram bot tokeni sozlanmagan.')).toBeTruthy();
    const link = screen.getByRole('link', { name: 'SIP va tarmoq sahifasida sozlang' });
    expect(link.getAttribute('href')).toBe('/settings/sip');
  });

  it('chat ID qoʻshish/oʻchirish, hodisa toggle va dedup saqlash ishlaydi', async () => {
    const user = userEvent.setup();
    renderPage(<AlertsPage />);

    await screen.findByText('Chat IDʼlar');
    await user.type(screen.getByPlaceholderText('-1001234567890'), '-1009998887');
    await user.click(screen.getByRole('button', { name: 'Qoʻshish' }));
    expect(await screen.findByText('-1009998887')).toBeTruthy();

    await user.click(screen.getByRole('button', { name: '-1001234567890ni oʻchirish' }));
    await waitFor(() => expect(screen.queryByText('-1001234567890')).toBeNull());

    await user.click(screen.getByRole('switch', { name: 'Trunk ishdan chiqdi' }));

    const dedup = screen.getByRole('textbox', { name: 'Takrorlanishni bostirish (soniya)' });
    await user.clear(dedup);
    await user.type(dedup, '120');

    await user.click(screen.getByRole('button', { name: 'Saqlash' }));

    await waitFor(async () => expect((await client.alertSettings()).dedup_s).toBe(120));
    const saved = await client.alertSettings();
    expect(saved.chat_ids).toEqual(['-1009998887']);
    expect(saved.events.trunk_down).toBe(false);
  });

  it('stale (409) holatida ogohlantirish chiqadi', async () => {
    const user = userEvent.setup();
    renderPage(<AlertsPage />);
    await screen.findByText('Chat IDʼlar');

    const current = await client.alertSettings();
    await client.updateAlertSettings({ updated_at: current.updated_at, dedup_s: 900 });

    await user.click(screen.getByRole('button', { name: 'Saqlash' }));
    expect(await screen.findByText(/boshqa joyda oʻzgartirilgan/)).toBeTruthy();
  });

  it('sinov xabari — token yoʻqligida 422 xato, token qoʻyilgandan keyin muvaffaqiyatli yuboriladi', async () => {
    const user = userEvent.setup();
    renderPage(<ToastProvider><AlertsPage /></ToastProvider>);

    const sendBtn = await screen.findByRole('button', { name: 'Sinov xabari yuborish' });
    await user.click(sendBtn);
    expect(await screen.findByText('Yuborib boʻlmadi')).toBeTruthy();
    expect((await client.alertLog({})).items.some((e) => e.kind === 'test')).toBe(false);

    await client.updateNotifySettings({ telegram_token: 'seed-token-123' });
    await user.click(sendBtn);

    expect(await screen.findByText('Yuborildi')).toBeTruthy();
    expect((await client.alertLog({})).items.some((e) => e.kind === 'test')).toBe(true);
  });

  it('sinov xabari — 502 notify_failed sababli bilan koʻrsatiladi', async () => {
    const user = userEvent.setup();
    await client.updateNotifySettings({ telegram_token: 'seed-token-123' });
    await client.updateAlertSettings({ updated_at: (await client.alertSettings()).updated_at, chat_ids: ['0'] });
    renderPage(<ToastProvider><AlertsPage /></ToastProvider>);

    const sendBtn = await screen.findByRole('button', { name: 'Sinov xabari yuborish' });
    await user.click(sendBtn);
    expect(await screen.findByText('Yuborib boʻlmadi')).toBeTruthy();
  });

  it('tarix jadvali seed yozuvlarini koʻrsatadi', async () => {
    renderPage(<AlertsPage />);
    expect(await screen.findByText('Yuborilgan ogohlantirishlar tarixi')).toBeTruthy();
  });

  it("operator — faqat o'qiydi, saqlash/qoʻshish tugmalari bo'lmaydi", async () => {
    await loginAs(client, 'operator');
    renderPage(<AlertsPage />);

    expect(await screen.findByText(/ruxsati yo/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Saqlash' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Sinov xabari yuborish' })).toBeDisabled();
  });
});
