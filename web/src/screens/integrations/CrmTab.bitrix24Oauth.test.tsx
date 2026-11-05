// Bitrix24 OAuth "Ulash" oqimi: ulash (popup+poll), xato kodlari, vaqt tugashi, uzish, litsenziya
// belgisi (CrmTab) va Litsenziya sahifasi (LicensePage). Qarang ../../../bitrix-oauth-shartnoma.md §2.
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { IntegrationsPage } = await import('./IntegrationsPage');
const { LicensePage } = await import('@/screens/license/LicensePage');

const NET = { timeout: 4000 };

/** Popup bloklovchisi ishga tushmasin — har chaqiriqda yangi soxta oyna obyekti qaytaradi. */
function stubPopup() {
  const popup = { location: { href: '' }, close: vi.fn() } as unknown as Window;
  vi.spyOn(window, 'open').mockReturnValue(popup);
  return popup;
}

async function openBitrixTab() {
  renderPage(<IntegrationsPage />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole('tab', { name: 'Bitrix24' }));
  // Tab tarkibi oʻzining soʻrovini (`useBitrix24Config`) yuklaguncha "…" koʻrsatadi — ulash kartasi
  // chiqishini kutamiz, aks holda domen maydoni/"Ulash" tugmasi hali DOM'da yoʻq boʻladi.
  await screen.findByTestId('crm-bitrix24-connect');
  return user;
}

describe('Bitrix24 OAuth — ulash', () => {
  beforeEach(async () => {
    vi.restoreAllMocks();
    await loginAs(client, 'admin');
    // Testlar bitta umumiy soxta backend holatini ulashadi (`test-pages.tsx` konvensiyasi bitta
    // faylga bitta mustaqil klient beradi, lekin testlar o'rtasida emas) — har biri "ulanmagan"dan boshlansin.
    await client.disconnectBitrix24();
  });
  afterEach(() => useSession.getState().clear());

  it('notoʻgʻri domen — mijoz tomonida xato koʻrsatiladi, tarmoqqa chiqmaydi', async () => {
    const openSpy = vi.spyOn(window, 'open');
    const user = await openBitrixTab();
    await user.click(screen.getByRole('button', { name: 'Ulash' }));
    expect(await screen.findByText('Portal domenini kiriting.')).toBeTruthy();

    await user.type(screen.getByRole('textbox', { name: 'Portal domeni' }), 'notadomain');
    await user.click(screen.getByRole('button', { name: 'Ulash' }));
    expect(await screen.findByText('Domen notoʻgʻri — masalan kompaniya.bitrix24.kz.')).toBeTruthy();
    expect(openSpy).not.toHaveBeenCalled();
  });

  it("'app_not_installed' — broker xatosi koʻrsatiladi", async () => {
    stubPopup();
    const user = await openBitrixTab();
    await user.type(screen.getByRole('textbox', { name: 'Portal domeni' }), 'firma.notinstalled.bitrix24.kz');
    await user.click(screen.getByRole('button', { name: 'Ulash' }));
    expect(await screen.findByText('Bu portalda Innova PBX ilovasi oʻrnatilmagan — avval Bitrix24 ilovalar doʻkonidan oʻrnating.', {}, NET)).toBeTruthy();
  });

  it("'broker_unreachable' — ulanish serveri xatosi koʻrsatiladi", async () => {
    stubPopup();
    const user = await openBitrixTab();
    await user.type(screen.getByRole('textbox', { name: 'Portal domeni' }), 'firma.offline.bitrix24.kz');
    await user.click(screen.getByRole('button', { name: 'Ulash' }));
    expect(await screen.findByText('Ulanish serveriga yetib boʻlmadi — birozdan keyin qayta urinib koʻring.', {}, NET)).toBeTruthy();
  });

  it('toʻliq oqim — popup ochiladi, 2 soʻrovdan keyin "ulandi" holatiga oʻtadi, sozlash natijasi koʻrinadi', async () => {
    const popup = stubPopup();
    const user = await openBitrixTab();
    await user.type(screen.getByRole('textbox', { name: 'Portal domeni' }), 'firma.bitrix24.kz');
    await user.click(screen.getByRole('button', { name: 'Ulash' }));

    expect(await screen.findByText('Bitrix oynasida tizimga kiring…', {}, NET)).toBeTruthy();
    await waitFor(() => expect(popup.location.href).toMatch(/^https:\/\/firma\.bitrix24\.kz\/oauth\/authorize/), { timeout: 8000 });

    await waitFor(() => expect(screen.getByTestId('crm-bitrix24-connected')).toBeTruthy(), { timeout: 8000 });
    expect(popup.close).toHaveBeenCalled();
    const connected = screen.getByTestId('crm-bitrix24-connected');
    expect(within(connected).getByText('firma.bitrix24.kz')).toBeTruthy();
    // Litsenziya belgisi alohida soʻrov (`useBitrix24License`) orqali keladi — "ulandi" kartasidan
    // keyin birozdan soʻng chiqadi, shuning uchun `findByText` (kutish bilan), `getByText` emas.
    expect(await within(connected).findByText('Sinov — 14 kun qoldi', {}, NET)).toBeTruthy();
    await waitFor(() => expect(screen.getByTestId('crm-bitrix24-setup')).toBeTruthy());
  }, 15000);

  it('150 urinishdan keyin javob kelmasa — "vaqt tugadi" xabari koʻrsatiladi, popup yopiladi', async () => {
    vi.spyOn(client, 'connectBitrix24').mockResolvedValue({ authorize_url: 'https://firma.bitrix24.kz/oauth/authorize/?demo=1' });
    vi.spyOn(client, 'pollBitrix24Connect').mockResolvedValue({ status: 'pending' });
    const popup = stubPopup();

    // Avval haqiqiy taymerlar bilan yuklanishini kutamiz (`useBitrix24Config`ning ~260ms kechikishi) —
    // soxta taymerlarni faqat "Ulash"ni bosishdan oldin yoqamiz, aks holda React/soʻrov kechikishlari
    // bilan aralashib ketib card hech qachon chiqmaydi. Tabni `userEvent` orqali bosamiz — Radix
    // Tabs `activationMode="automatic"` fokusga asoslangan, xom `.click()` fokus bermaydi va
    // tabni almashtirmaydi (`element.click()` userEvent'dan farqli, pointerdown/focus ketma-ketligisiz).
    renderPage(<IntegrationsPage />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole('tab', { name: 'Bitrix24' }));
    await screen.findByTestId('crm-bitrix24-connect');
    fireEvent.change(screen.getByRole('textbox', { name: 'Portal domeni' }), { target: { value: 'firma.bitrix24.kz' } });

    vi.useFakeTimers({ shouldAdvanceTime: true });
    act(() => screen.getByRole('button', { name: 'Ulash' }).click());

    // Ulash soʻrovi tasdiqlansin (poll taymeri shundan keyin ishga tushadi), soʻng 151 ta soʻrov — bittasi
    // limitdan (150) oshib "vaqt tugadi" holatiga olib boradi (qarang `tick()` — `CrmTab.tsx`).
    await act(async () => { await vi.advanceTimersByTimeAsync(50); });
    await act(async () => { await vi.advanceTimersByTimeAsync(151 * 2000 + 100); });

    expect(screen.getByText('Vaqt tugadi — qayta urining.')).toBeTruthy();
    expect(popup.close).toHaveBeenCalled();
    vi.useRealTimers();
  }, 20000);

  it('uzish — tasdiqlash oynasi orqali bajariladi, forma "ulanmagan" holatiga qaytadi', async () => {
    const popup = stubPopup();
    const user = await openBitrixTab();
    await user.type(screen.getByRole('textbox', { name: 'Portal domeni' }), 'firma.bitrix24.kz');
    await user.click(screen.getByRole('button', { name: 'Ulash' }));
    await waitFor(() => expect(screen.getByTestId('crm-bitrix24-connected')).toBeTruthy(), { timeout: 8000 });
    void popup;

    await user.click(screen.getByRole('button', { name: 'Uzish' }));
    await user.click(screen.getByRole('button', { name: 'Ha, uzish' }));

    await waitFor(() => expect(screen.getByTestId('crm-bitrix24-connect')).toBeTruthy());
    expect(screen.queryByTestId('crm-bitrix24-connected')).toBeNull();
  }, 15000);
});

describe('Litsenziya sahifasi (/settings/license)', () => {
  beforeEach(async () => {
    vi.restoreAllMocks();
    await loginAs(client, 'admin');
    await client.disconnectBitrix24();
  });
  afterEach(() => useSession.getState().clear());

  it('Bitrix24 ulanmagan boʻlsa — "ulanmagan" karta va Integratsiyalarga havola koʻrinadi', async () => {
    renderPage(<LicensePage />);
    expect(await screen.findByTestId('license-not-connected')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Integratsiyalarga oʻtish' })).toHaveAttribute('href', '/settings/integrations');
  });

  it('ulangandan keyin — litsenziya kartasi holat belgisi, sanalar va tariflar bilan koʻrinadi', async () => {
    const popup = stubPopup();
    const user = await openBitrixTab();
    await user.type(screen.getByRole('textbox', { name: 'Portal domeni' }), 'firma.bitrix24.kz');
    await user.click(screen.getByRole('button', { name: 'Ulash' }));
    await waitFor(() => expect(screen.getByTestId('crm-bitrix24-connected')).toBeTruthy(), { timeout: 8000 });
    void popup;

    renderPage(<LicensePage />);
    const card = await screen.findByTestId('license-card');
    expect(within(card).getByText('Sinov — 14 kun qoldi')).toBeTruthy();
    expect(within(card).getByText('Portal: firma.bitrix24.kz')).toBeTruthy();
    expect(within(card).getByText('14 kun bepul sinov')).toBeTruthy();
    expect(within(card).getByText('1 oy')).toBeTruthy();
  }, 15000);
});
