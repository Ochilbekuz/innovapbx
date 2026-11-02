// M3a §4 — SoftphoneWidget (chip + panel) render testlari. Store haqiqiy, lekin pastdagi SIP.js
// engine/ringtone to'liq mock (store.test.ts bilan bir xil naqsh).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import type { SoftphoneEngineEvents } from './engine';

const meSoftphone = vi.fn();
vi.mock('@/api', () => ({ apiClient: { meSoftphone, meSoftphoneStatus: vi.fn(() => Promise.resolve()) } }));

const engineApi = {
  connect: vi.fn(() => Promise.resolve()),
  disconnect: vi.fn(() => Promise.resolve()),
  call: vi.fn(),
  answer: vi.fn(),
  reject: vi.fn(),
  hangup: vi.fn(),
  mute: vi.fn(),
  hold: vi.fn(),
  sendDtmf: vi.fn(),
  transfer: vi.fn(),
  attachRemoteAudio: vi.fn(),
  getStats: vi.fn(() => Promise.resolve(null)),
};
let events: SoftphoneEngineEvents;
vi.mock('./engine', () => ({
  createSoftphoneEngine: (e: SoftphoneEngineEvents) => {
    events = e;
    return engineApi;
  },
}));
vi.mock('./ring', () => ({ startRingtone: () => ({ stop: vi.fn() }) }));

const SOFTPHONE_INFO = {
  number: '101', display_name: 'Dilnoza Karimova', ws_path: '/sip-ws', ticket: 't1',
  ticket_expires_at: new Date(Date.now() + 600_000).toISOString(),
  sip: { uri: 'sip:t1-101@innova', auth_user: 't1-101', password: 'x', realm: 'asterisk' },
  ice_servers: [],
};

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe('SoftphoneWidget', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    meSoftphone.mockResolvedValue({ ...SOFTPHONE_INFO });
  });

  afterEach(async () => {
    const { useSoftphoneStore } = await import('./store');
    await useSoftphoneStore.getState().teardown();
    cleanup();
  });

  it('ulanmagunicha chip koʻrinmaydi, "registered"dan keyin koʻrinadi', async () => {
    const { useSoftphoneStore } = await import('./store');
    const { SoftphoneWidget } = await import('./SoftphoneWidget');
    render(<SoftphoneWidget number="101" />);
    expect(screen.queryByTestId('softphone-chip')).toBeNull();

    act(() => useSoftphoneStore.getState().init());
    await flush();
    act(() => events.onRegistered());

    expect(screen.getByTestId('softphone-chip')).toBeTruthy();
  });

  it('chipni bosib panelni ochish, raqam terib qoʻngʻiroq qilish', async () => {
    const { useSoftphoneStore } = await import('./store');
    const { SoftphoneWidget } = await import('./SoftphoneWidget');
    render(<SoftphoneWidget number="101" />);
    act(() => useSoftphoneStore.getState().init());
    await flush();
    act(() => events.onRegistered());

    const user = userEvent.setup();
    await user.click(screen.getByTestId('softphone-chip'));
    const input = await screen.findByTestId('softphone-dial-input');
    await user.type(input, '202');
    await user.click(screen.getByTestId('softphone-call'));

    expect(engineApi.call).toHaveBeenCalledWith('202');
  });

  it('kiruvchi qoʻngʻiroq panelni avtomatik ochadi va javob/rad tugmalarini koʻrsatadi', async () => {
    const { useSoftphoneStore } = await import('./store');
    const { SoftphoneWidget } = await import('./SoftphoneWidget');
    render(<SoftphoneWidget number="101" />);
    act(() => useSoftphoneStore.getState().init());
    await flush();
    act(() => events.onRegistered());

    act(() => events.onIncoming({ remoteNumber: '202', remoteName: 'Mijoz' }));

    expect(screen.getByTestId('softphone-incoming-from')).toHaveTextContent('Mijoz');
    expect(screen.getByTestId('softphone-answer')).toBeTruthy();
    expect(screen.getByTestId('softphone-reject')).toBeTruthy();
  });

  it('gaplashmoqda ekranida taymer, mute, hold, hangup koʻrinadi', async () => {
    const { useSoftphoneStore } = await import('./store');
    const { SoftphoneWidget } = await import('./SoftphoneWidget');
    render(<SoftphoneWidget number="101" />);
    act(() => useSoftphoneStore.getState().init());
    await flush();
    act(() => events.onRegistered());
    act(() => useSoftphoneStore.getState().startCall('202'));
    act(() => events.onEstablished());

    expect(screen.getByTestId('softphone-timer')).toBeTruthy();
    const user = userEvent.setup();
    await user.click(screen.getByTestId('softphone-mute'));
    expect(engineApi.mute).toHaveBeenCalledWith(true);
    await user.click(screen.getByTestId('softphone-hold'));
    expect(engineApi.hold).toHaveBeenCalledWith(true);
    await user.click(screen.getByTestId('softphone-hangup'));
    expect(engineApi.hangup).toHaveBeenCalledTimes(1);
  });

  it('gaplashmoqdan ichidan uzatish (transfer) raqam terib yuboriladi', async () => {
    const { useSoftphoneStore } = await import('./store');
    const { SoftphoneWidget } = await import('./SoftphoneWidget');
    render(<SoftphoneWidget number="101" />);
    act(() => useSoftphoneStore.getState().init());
    await flush();
    act(() => events.onRegistered());
    act(() => useSoftphoneStore.getState().startCall('202'));
    act(() => events.onEstablished());

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Oʻtkazish' }));
    const input = screen.getByRole('textbox', { name: 'Boshqa raqamga oʻtkazish' });
    await user.type(input, '303');
    await user.click(screen.getByTestId('softphone-transfer'));

    expect(engineApi.transfer).toHaveBeenCalledWith('303');
  });

  it('kiruvchidan javob berilgan suhbatda chaqiruvchi raqami koʻrsatiladi', async () => {
    const { useSoftphoneStore } = await import('./store');
    const { SoftphoneWidget } = await import('./SoftphoneWidget');
    render(<SoftphoneWidget number="101" />);
    act(() => useSoftphoneStore.getState().init());
    await flush();
    act(() => events.onRegistered());
    act(() => events.onIncoming({ remoteNumber: '202', remoteName: 'Mijoz' }));
    act(() => useSoftphoneStore.getState().answer());
    act(() => events.onEstablished());

    expect(screen.getByText('202')).toBeTruthy();
  });

  it('chaqirilmoqda (outgoing) holatida taymer oʻrniga holat matni chiqadi', async () => {
    const { useSoftphoneStore } = await import('./store');
    const { SoftphoneWidget } = await import('./SoftphoneWidget');
    render(<SoftphoneWidget number="101" />);
    act(() => useSoftphoneStore.getState().init());
    await flush();
    act(() => events.onRegistered());
    act(() => useSoftphoneStore.getState().startCall('202'));

    expect(screen.queryByTestId('softphone-timer')).toBeNull();
    expect(screen.getAllByText('Chaqirilmoqda…').length).toBeGreaterThan(0);
  });

  it('mikrofonga ruxsat berilmaganda idle ekranida ogohlantirish chiqadi', async () => {
    const { useSoftphoneStore } = await import('./store');
    const { SoftphoneWidget } = await import('./SoftphoneWidget');
    render(<SoftphoneWidget number="101" />);
    act(() => useSoftphoneStore.getState().init());
    await flush();
    act(() => events.onRegistered());
    act(() => useSoftphoneStore.getState().startCall('202'));
    act(() => events.onFailed('NotAllowedError'));

    expect(screen.getByText('Mikrofonga ruxsat yoʻq')).toBeTruthy();
    expect(screen.getByTestId('softphone-call')).toBeDisabled();
  });

  it('roʻyxatdan oʻtish xato boʻlsa — sabab panelda koʻrsatiladi', async () => {
    const { useSoftphoneStore } = await import('./store');
    const { SoftphoneWidget } = await import('./SoftphoneWidget');
    render(<SoftphoneWidget number="101" />);
    act(() => useSoftphoneStore.getState().init());
    await flush();
    const user = userEvent.setup();
    await user.click(screen.getByTestId('softphone-chip'));

    act(() => events.onRegistrationFailed('network'));
    expect(screen.getAllByText('Xato').length).toBeGreaterThan(0);
    expect(screen.getByText('network')).toBeTruthy();
  });

  it('masofaviy <audio> panel YOPIQ boʻlganda ham DOMda qoladi (ovoz uzilmasin)', async () => {
    const { useSoftphoneStore } = await import('./store');
    const { SoftphoneWidget } = await import('./SoftphoneWidget');
    render(<SoftphoneWidget number="101" />);
    act(() => useSoftphoneStore.getState().init());
    await flush();
    act(() => events.onRegistered());
    expect(useSoftphoneStore.getState().panelOpen).toBe(false);
    const audio = screen.getByTestId('softphone-remote-audio');
    expect(audio.tagName).toBe('AUDIO');

    const user = userEvent.setup();
    await user.click(screen.getByTestId('softphone-chip'));
    act(() => useSoftphoneStore.getState().closePanel());
    act(() => events.onEstablished());
    expect(screen.getByTestId('softphone-remote-audio')).toBe(audio);
    expect(engineApi.attachRemoteAudio).toHaveBeenLastCalledWith(audio);
  });

  it('diagState() — tilga bogʻliq boʻlmagan holat (isbot uchun)', async () => {
    const { useSoftphoneStore } = await import('./store');
    const { diagState } = await import('./diag');
    expect(diagState()).toEqual({ connection: 'unavailable', errorReason: null, phase: null, remoteNumber: null, muted: false });
    act(() => useSoftphoneStore.getState().init());
    await flush();
    act(() => events.onRegistered());
    act(() => events.onIncoming({ remoteNumber: '103' }));
    expect(diagState()).toEqual({ connection: 'registered', errorReason: null, phase: 'incoming', remoteNumber: '103', muted: false });
  });
});
