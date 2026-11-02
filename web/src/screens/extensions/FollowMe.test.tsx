// M5b — Follow Me bo'limi va «Telefonga ulash» (QR) oynasi: fake API bilan xatti-harakat testi.
import { afterEach, describe, expect, it, vi } from 'vitest';
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
// jsdom'da canvas yo'q — QR rasmini yasash o'rniga havolani data URL ichiga qo'yamiz.
vi.mock('qrcode', () => ({ default: { toDataURL: (url: string) => Promise.resolve(`data:image/png;base64,${btoa(url)}`) } }));

const { FollowMeSection, describeSaveError } = await import('./FollowMeSection');
const { QrConnectModal, formatCountdown } = await import('./QrConnectModal');

const qrUrl = (img: HTMLElement) => atob(img.getAttribute('src')!.split(',')[1] ?? '');

describe('FollowMeSection', () => {
  afterEach(() => useSession.getState().clear());

  it('raqam qo‘shib, yoqib saqlaydi; onSaved yangi updated_at oladi', async () => {
    await loginAs(client, 'admin');
    const user = userEvent.setup();
    const onSaved = vi.fn();
    renderPage(<FollowMeSection target="e-103" onSaved={onSaved} />);

    const save = await screen.findByTestId('fm-save');
    expect(save).toBeDisabled();
    await user.type(screen.getByTestId('fm-add-input'), '+998 (90) 123-45-67{Enter}');
    await user.type(screen.getByTestId('fm-add-input'), '104');
    await user.click(screen.getByTestId('fm-add'));
    expect(within(screen.getByTestId('fm-number-0')).getByText('998901234567')).toBeTruthy();
    expect(within(screen.getByTestId('fm-number-0')).getByText('tashqi')).toBeTruthy();
    expect(within(screen.getByTestId('fm-number-1')).getByText('ichki')).toBeTruthy();

    await user.click(screen.getByRole('button', { name: '104ni yuqoriga' }));
    expect(within(screen.getByTestId('fm-number-0')).getByText('104')).toBeTruthy();

    await user.click(screen.getByRole('switch', { name: 'Javob boʻlmasa boshqa raqamlarga jiringlash' }));
    await user.click(save);

    await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
    const saved = await client.followMe('e-103');
    expect(saved.follow_me).toMatchObject({ enabled: true, numbers: ['104', '998901234567'] });
    expect(onSaved).toHaveBeenCalledWith(saved.updated_at);
  });

  it('noto‘g‘ri, o‘z va takror raqamni darhol rad etadi', async () => {
    await loginAs(client, 'admin');
    const user = userEvent.setup();
    renderPage(<FollowMeSection target="e-104" />);

    const input = await screen.findByTestId('fm-add-input');
    await user.type(input, '1{Enter}');
    expect(screen.getByRole('alert').textContent).toContain('Raqam notoʻgʻri');
    await user.clear(input);
    await user.type(input, '104{Enter}');
    expect(screen.getByRole('alert').textContent).toContain('Oʻz raqamingiz');
    await user.clear(input);
    await user.type(input, '103{Enter}');
    await user.type(input, '103{Enter}');
    expect(screen.getByRole('alert').textContent).toContain('roʻyxatda bor');
  });

  it('server xatosi tegishli qatorni belgilaydi (mavjud bo‘lmagan ichki raqam)', async () => {
    await loginAs(client, 'admin');
    const user = userEvent.setup();
    renderPage(<FollowMeSection target="e-104" />);

    await user.type(await screen.findByTestId('fm-add-input'), '103{Enter}');
    await user.type(screen.getByTestId('fm-add-input'), '999{Enter}');
    await user.click(screen.getByTestId('fm-save'));

    await waitFor(() => expect(screen.getByTestId('fm-number-1').className).toContain('border-danger'));
    expect(screen.getByTestId('fm-number-0').className).not.toContain('border-danger');
  });

  it('yoqilgan, lekin raqamsiz — saqlab bo‘lmaydi; compact rejimda vaqt maydoni yo‘q', async () => {
    await loginAs(client, 'operator');
    const user = userEvent.setup();
    renderPage(<FollowMeSection target={null} compact />);

    await user.click(await screen.findByRole('switch', { name: 'Javob boʻlmasa boshqa raqamlarga jiringlash' }));
    expect(screen.getByTestId('fm-save')).toBeDisabled();
    expect(screen.queryByTestId('fm-ring-seconds')).toBeNull();
    expect(screen.queryByRole('switch', { name: 'Ichki raqam ham jiringlasin' })).toBeNull();
  });

  it('readOnly — tahrir boshqaruvlari yo‘q', async () => {
    await loginAs(client, 'admin');
    renderPage(<FollowMeSection target="e-103" readOnly />);
    expect(await screen.findByRole('switch', { name: 'Javob boʻlmasa boshqa raqamlarga jiringlash' })).toBeDisabled();
    expect(screen.queryByTestId('fm-save')).toBeNull();
    expect(screen.queryByTestId('fm-add-input')).toBeNull();
  });
});

describe('QrConnectModal', () => {
  afterEach(() => useSession.getState().clear());

  it('tashqi manzil sozlanmagan — xato va admin uchun sozlamalar havolasi', async () => {
    await loginAs(client, 'admin');
    renderPage(<QrConnectModal target="e-103" number="103" open onOpenChange={() => {}} />);
    const box = await screen.findByTestId('qr-error');
    expect(within(box).getByRole('link', { name: 'Sozlamalarni ochish' })).toHaveAttribute('href', '/settings/integrations');
  });

  it('WebRTC raqam — QR berilmaydi (operator /me)', async () => {
    await loginAs(client, 'operator'); // 102 — faqat brauzer softfoni
    renderPage(<QrConnectModal target={null} number="102" open onOpenChange={() => {}} />);
    const box = await screen.findByTestId('qr-error');
    expect(within(box).queryByRole('link')).toBeNull();
  });

  it('QR, qolgan vaqt va bir martalik havola; «Yangi QR» yangi token oladi', async () => {
    await loginAs(client, 'admin');
    const current = await client.integrationsSettings();
    await client.updateIntegrationsSettings({ public_base_url: 'https://pbx.example.uz/', updated_at: current.updated_at });
    const user = userEvent.setup();
    renderPage(<QrConnectModal target="e-103" number="103" open onOpenChange={() => {}} />);

    const img = await screen.findByTestId('qr-image');
    const first = qrUrl(img);
    expect(first).toMatch(/^https:\/\/pbx\.example\.uz\/prov\/qr\/[^/]+\/linphone\.xml$/);
    expect(screen.getByTestId('qr-countdown').textContent).toMatch(/1[45]:\d\d/);

    await user.click(screen.getByTestId('qr-refresh'));
    await waitFor(() => expect(qrUrl(screen.getByTestId('qr-image'))).not.toBe(first));
  });
});

describe('formatCountdown', () => {
  it.each([[0, '0:00'], [9, '0:09'], [61, '1:01'], [900, '15:00']])('%i → %s', (s, out) => {
    expect(formatCountdown(s)).toBe(out);
  });
});

describe('describeSaveError', () => {
  it('xato yoʻq — hech narsa koʻrsatilmaydi', () => {
    expect(describeSaveError(null)).toEqual({ stale: false, index: null });
  });
  it('stale — alohida blok', () => {
    expect(describeSaveError(new ApiError(409, { code: 'stale', message: 'x' }))).toMatchObject({ stale: true, index: null });
  });
  it('numbers.{i} — qator indeksi', () => {
    expect(describeSaveError(new ApiError(422, { code: 'bad_number', message: 'x', field: 'numbers.3' }))).toMatchObject({ stale: false, index: 3 });
  });
  it('field yoʻq yoki boshqa — umumiy xabar', () => {
    expect(describeSaveError(new ApiError(422, { code: 'follow_me_empty', message: 'x', field: 'numbers' }))).toMatchObject({ index: null });
    expect(describeSaveError(new Error('tarmoq'))).toMatchObject({ stale: false, index: null, message: expect.any(String) });
  });
});
