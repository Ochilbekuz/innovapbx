// Xatti-harakat testi — Sana va vaqt: zona qidirib tanlash → saqlash (PBX zonasi ham), mintaqaviy pool maslahati,
// «Hozir sinxronlash», NTP o'chiq bo'lsa sinxronlash yopiq.
import { describe, expect, it, afterEach, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';
import { ToastProvider } from '@/ui/Toast';
import { ApiError } from '@/api/errors';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { TimeSettingsPage } = await import('./TimeSettingsPage');

async function openPage() {
  await loginAs(client, 'admin');
  await client.applyTime({ timezone: 'Asia/Tashkent', ntp_servers: ['0.uz.pool.ntp.org'], ntp_enabled: true });
  renderPage(<ToastProvider><TimeSettingsPage /></ToastProvider>);
  return screen.findByText('Server vaqti');
}

describe('TimeSettingsPage', () => {
  afterEach(() => { vi.restoreAllMocks(); useSession.getState().clear(); });

  it('server zonasidagi vaqtni, UTC siljishini va vaqt manbaini koʻrsatadi', async () => {
    await openPage();
    expect(screen.getByText(/Asia\/Tashkent \(UTC\+05:00\)/)).toBeTruthy();
    expect(screen.getByText(/Vaqt manbai/).textContent).toContain('0.uz.pool.ntp.org');
  });

  it('server holatni bera olmasa — sababini va «Qayta urinish»ni koʻrsatadi', async () => {
    await loginAs(client, 'admin');
    vi.spyOn(client, 'systemTime').mockRejectedValue(
      new ApiError(504, { code: 'command_timeout', message: 'x' }),
    );
    renderPage(<ToastProvider><TimeSettingsPage /></ToastProvider>);
    expect(await screen.findByText(/javob bermadi/, {}, { timeout: 5000 })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Qayta/ })).toBeTruthy();
  });

  it('zonani qidirib tanlab saqlasa — server va PBX zonasi yangilanadi', async () => {
    const user = userEvent.setup();
    await openPage();
    await user.click(screen.getByRole('button', { name: /Vaqt zonasi/ }));
    await user.type(screen.getByRole('textbox', { name: /UTC\+05 boʻyicha qidirish/ }), 'moscow');
    await user.click(screen.getByRole('button', { name: /Europe\/Moscow|Europe Moscow/ }));
    await user.click(screen.getByRole('button', { name: 'Saqlash' }));

    await screen.findByText('PBX vaqt zonasi yangilandi');
    expect((await client.systemTime()).timezone).toBe('Europe/Moscow');
  }, 10_000);

  it("ro'yxat bo'shatilsa — tanlangan zonaning pool serverlari maslahatda koʻrinadi", async () => {
    const user = userEvent.setup();
    await openPage();
    const servers = screen.getByRole('textbox', { name: 'NTP serverlar' });
    await user.clear(servers);
    expect(servers.getAttribute('placeholder')).toContain('0.asia.pool.ntp.org');
  });

  it('«Hozir sinxronlash» — muvaffaqiyat xabari va manba', async () => {
    const user = userEvent.setup();
    await openPage();
    await user.click(screen.getByRole('button', { name: 'Hozir sinxronlash' }));
    await screen.findByText('Vaqt internet bilan sinxronlandi');
    expect(screen.getByText('Manba: 0.uz.pool.ntp.org')).toBeTruthy();
  });

  it("NTP o'chirib saqlansa — sinxronlash tugmasi yopiladi", async () => {
    const user = userEvent.setup();
    await openPage();
    await user.click(screen.getByRole('switch', { name: 'NTP yoqilgan' }));
    await user.click(screen.getByRole('button', { name: 'Saqlash' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Hozir sinxronlash' })).toHaveProperty('disabled', true));
  });

  it("konteynerda (LXC) NTP'ni yoqib bo'lmasa — sababi koʻrinadi va tugma yopiq", async () => {
    await loginAs(client, 'admin');
    await client.applyTime({ timezone: 'Asia/Tashkent', ntp_servers: [], ntp_enabled: false });
    const real = await client.systemTime();
    vi.spyOn(client, 'systemTime').mockResolvedValue({
      ...real, ntp_unavailable_reason: 'Server konteyner ichida (lxc) ishlayapti — soatni host boshqaradi',
    });
    renderPage(<ToastProvider><TimeSettingsPage /></ToastProvider>);
    expect(await screen.findByText(/konteyner ichida \(lxc\)/)).toBeTruthy();
    expect(screen.getByRole('switch', { name: 'NTP yoqilgan' })).toHaveProperty('disabled', true);
  });

  it("server NTP'ni yoqa olmasa — jim «Saqlandi» emas, sababi bilan xato", async () => {
    const user = userEvent.setup();
    await openPage();
    vi.spyOn(client, 'applyTime').mockRejectedValue(
      new ApiError(502, { code: 'ntp_not_started', message: 'NTP yoqilmadi: xizmat ishga tushmadi' }),
    );
    await user.click(screen.getByRole('button', { name: 'Saqlash' }));
    expect(await screen.findByText(/NTP yoqilmadi/)).toBeTruthy();
    expect(screen.queryByText('Saqlandi')).toBeNull();
  });
});
