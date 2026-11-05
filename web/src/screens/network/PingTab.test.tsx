// Xatti-harakat testi — Tarmoq sahifasi «Ping» tabi: preset -> host, natija, 100% yo'qotish, API xatosi, netd yo'q.
import { describe, expect, it, afterEach, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApiError } from '@/api/errors';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { PingTab } = await import('./PingTab');

function hostInput(): HTMLInputElement {
  return screen.getByLabelText('Host') as HTMLInputElement;
}

describe('PingTab', () => {
  afterEach(() => {
    useSession.getState().clear();
    vi.restoreAllMocks();
  });

  it('shlyuz presetini bosish hostni toʻldiradi, ping natijasi koʻrinadi', async () => {
    const user = userEvent.setup();
    await loginAs(client, 'admin');
    renderPage(<PingTab gateway="192.168.10.1" helperAvailable />);

    await user.click(screen.getByRole('button', { name: /Shlyuz.*192\.168\.10\.1/ }));
    expect(hostInput().value).toBe('192.168.10.1');

    await user.click(screen.getByRole('button', { name: 'Ping' }));
    const result = await screen.findByRole('region', { name: 'Natija' });
    expect(within(result).getByText('Javob bor')).toBeTruthy();
    expect(within(result).getByText('0%')).toBeTruthy();
    expect(within(result).getByText(/packets transmitted/)).toBeTruthy();
  });

  it('SIP trunk hosti presetlar orasida (trunks soʻrovidan)', async () => {
    await loginAs(client, 'admin');
    renderPage(<PingTab gateway={null} helperAvailable />);
    await userEvent.setup().click(await screen.findByRole('button', { name: /sip\.uztelecom\.uz/ }));
    expect(hostInput().value).toBe('sip.uztelecom.uz');
  });

  it('javobsiz host — 100% yoʻqotish va xato belgisi', async () => {
    const user = userEvent.setup();
    await loginAs(client, 'admin');
    renderPage(<PingTab gateway={null} helperAvailable />);

    await user.type(hostInput(), '192.0.2.5');
    await user.click(screen.getByRole('button', { name: 'Ping' }));
    const result = await screen.findByRole('region', { name: 'Natija' });
    expect(within(result).getByText('Javob yoʻq')).toBeTruthy();
    expect(within(result).getByText('100%')).toBeTruthy();
  });

  it('paketlar soni 1–10 ga cheklanadi; nomaʼlum nom — 0 paket, chiqishda xato', async () => {
    const user = userEvent.setup();
    await loginAs(client, 'admin');
    const spy = vi.spyOn(client, 'pingHost');
    renderPage(<PingTab gateway={null} helperAvailable />);

    const count = screen.getByLabelText('Paketlar soni') as HTMLInputElement;
    await user.clear(count);
    await user.type(count, '25');
    await user.type(hostInput(), '  nosuch.invalid ');
    await user.click(screen.getByRole('button', { name: 'Ping' }));
    await waitFor(() => expect(spy).toHaveBeenCalledWith({ host: 'nosuch.invalid', count: 10 }));
    expect(count.value).toBe('10');
    const result = await screen.findByRole('region', { name: 'Natija' });
    expect(within(result).getByText('0 / 0')).toBeTruthy();
    expect(within(result).getByText(/Name or service not known/)).toBeTruthy();
    expect(within(result).getByText('— / — / —')).toBeTruthy();
  });

  it('yaroqsiz host — xato matni, Ping tugmasi oʻchiq', async () => {
    const user = userEvent.setup();
    await loginAs(client, 'admin');
    renderPage(<PingTab gateway={null} helperAvailable />);

    await user.type(hostInput(), '-oProxy');
    expect(screen.getByText(/IP manzil yoki domen nomi/)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Ping' })).toBeDisabled();
  });

  it('API xatosi (netd javob bermadi) — tushunarli xabar', async () => {
    const user = userEvent.setup();
    await loginAs(client, 'admin');
    vi.spyOn(client, 'pingHost').mockRejectedValueOnce(
      new ApiError(503, { code: 'helper_unavailable', message: 'netd bilan aloqa yoʻq' }),
    );
    renderPage(<PingTab gateway={null} helperAvailable />);

    await user.type(hostInput(), 'google.com');
    await user.click(screen.getByRole('button', { name: 'Ping' }));
    expect(await screen.findByText(/netd\) javob bermadi/)).toBeTruthy();
  });

  it('netd mavjud boʻlmasa — ogohlantirish, Ping oʻchiq', async () => {
    await loginAs(client, 'admin');
    renderPage(<PingTab gateway={null} helperAvailable={false} />);
    expect(screen.getByText(/Ping ishlamaydi/)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Ping' })).toBeDisabled();
  });
});
