// M3a §4 — softphoneStore holat o'tishlari. Engine (SIP.js) va ringtone to'liq mock — WebRTC/WebAudio
// jsdomda yo'q, testda ularga ehtiyoj ham yo'q (SoftphoneEngine interfeysi orqali ajratilgan).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/api/errors';
import type { SoftphoneEngineEvents } from './engine';

const meSoftphone = vi.fn();
const meSoftphoneStatus = vi.fn();
vi.mock('@/api', () => ({ apiClient: { meSoftphone, meSoftphoneStatus } }));

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
  getStats: vi.fn(() => Promise.resolve({ packetsSent: 10, packetsReceived: 20, codec: 'opus', micEnabled: true, audioEnergy: 0 })),
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
  await Promise.resolve();
  await Promise.resolve();
}

describe('useSoftphoneStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    meSoftphone.mockResolvedValue({ ...SOFTPHONE_INFO });
    meSoftphoneStatus.mockResolvedValue(undefined);
  });

  afterEach(async () => {
    const { useSoftphoneStore } = await import('./store');
    await useSoftphoneStore.getState().teardown();
    vi.restoreAllMocks();
  });

  it('init() dan keyin registrator muvaffaqiyatli bo\'lsa "registered" holatiga o\'tadi', async () => {
    const { useSoftphoneStore } = await import('./store');
    useSoftphoneStore.getState().init();
    await flush();
    expect(meSoftphone).toHaveBeenCalledTimes(1);
    events.onRegistered();
    expect(useSoftphoneStore.getState().connection).toBe('registered');
  });

  it('kiruvchi qo\'ng\'iroq → javob → gaplashmoqda → yakunlandi', async () => {
    const { useSoftphoneStore } = await import('./store');
    useSoftphoneStore.getState().init();
    await flush();
    events.onRegistered();

    events.onIncoming({ remoteNumber: '202', remoteName: 'Mijoz' });
    expect(useSoftphoneStore.getState().call).toMatchObject({ phase: 'incoming', remoteNumber: '202' });
    expect(useSoftphoneStore.getState().panelOpen).toBe(true);

    useSoftphoneStore.getState().answer();
    expect(engineApi.answer).toHaveBeenCalledTimes(1);

    events.onEstablished();
    expect(useSoftphoneStore.getState().call?.phase).toBe('talking');
    expect(useSoftphoneStore.getState().call?.startedAt).not.toBeNull();

    events.onEnded();
    expect(useSoftphoneStore.getState().call).toBeNull();
  });

  it('mikrofonga ruxsat berilmasa — micDenied, chaqiruv yo\'qoladi', async () => {
    const { useSoftphoneStore } = await import('./store');
    useSoftphoneStore.getState().init();
    await flush();
    events.onRegistered();
    useSoftphoneStore.getState().startCall('202');
    events.onFailed('NotAllowedError');
    expect(useSoftphoneStore.getState().micDenied).toBe(true);
    expect(useSoftphoneStore.getState().call).toBeNull();
  });

  it('raqam webrtc uchun yoqilmagan bo\'lsa — "unavailable"', async () => {
    meSoftphone.mockRejectedValue(new ApiError(409, { code: 'webrtc_disabled', message: 'x' }));
    const { useSoftphoneStore } = await import('./store');
    useSoftphoneStore.getState().init();
    await flush();
    expect(useSoftphoneStore.getState().connection).toBe('unavailable');
    expect(engineApi.connect).not.toHaveBeenCalled();
  });

  it('boshqa tabda allaqachon ochiq bo\'lsa — "other_tab", engine ulanmaydi', async () => {
    const realLocks = navigator.locks;
    Object.defineProperty(navigator, 'locks', {
      configurable: true,
      value: { request: (_name: string, _opts: unknown, cb: (lock: unknown) => Promise<void>) => Promise.resolve(cb(null)) },
    });
    const { useSoftphoneStore } = await import('./store');
    useSoftphoneStore.getState().init();
    await flush();
    expect(useSoftphoneStore.getState().connection).toBe('other_tab');
    expect(meSoftphone).not.toHaveBeenCalled();
    Object.defineProperty(navigator, 'locks', { configurable: true, value: realLocks });
  });

  it('qulf (Web Locks) haqiqatan berilsa — "registered"gacha davom etadi (lock ushlab turiladi)', async () => {
    const realLocks = navigator.locks;
    Object.defineProperty(navigator, 'locks', {
      configurable: true,
      value: { request: (_name: string, _opts: unknown, cb: (lock: unknown) => Promise<void>) => Promise.resolve(cb({})) },
    });
    const { useSoftphoneStore } = await import('./store');
    useSoftphoneStore.getState().init();
    await flush();
    expect(meSoftphone).toHaveBeenCalledTimes(1);
    events.onRegistered();
    expect(useSoftphoneStore.getState().connection).toBe('registered');
    Object.defineProperty(navigator, 'locks', { configurable: true, value: realLocks });
  });

  it('ticket muddati tugasa ham ochiq ulanish QAYTA ULANMAYDI (faol qoʻngʻiroq uzilmasin)', async () => {
    vi.useFakeTimers();
    meSoftphone.mockResolvedValue({ ...SOFTPHONE_INFO, ticket_expires_at: new Date(Date.now() + 5_000).toISOString() });
    const { useSoftphoneStore } = await import('./store');
    useSoftphoneStore.getState().init();
    await vi.advanceTimersByTimeAsync(0);
    events.onRegistered();
    await vi.advanceTimersByTimeAsync(120_000);
    expect(meSoftphone).toHaveBeenCalledTimes(1);
    expect(engineApi.connect).toHaveBeenCalledTimes(1);
    expect(engineApi.disconnect).not.toHaveBeenCalled();
    expect(useSoftphoneStore.getState().connection).toBe('registered');
    vi.useRealTimers();
  });

  it('uzilishdan keyin qayta ulanish YANGI ticket oladi', async () => {
    vi.useFakeTimers();
    const { useSoftphoneStore } = await import('./store');
    useSoftphoneStore.getState().init();
    await vi.advanceTimersByTimeAsync(0);
    events.onRegistered();
    events.onDisconnected();
    expect(useSoftphoneStore.getState().connection).toBe('connecting');
    await vi.advanceTimersByTimeAsync(1_000);
    expect(meSoftphone).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });

  it('holat kuzatuvi: webrtc oʻchirilsa ≤ 60 s ichida ulanish yopiladi va chip yoʻqoladi', async () => {
    vi.useFakeTimers();
    const { useSoftphoneStore, STATUS_POLL_MS } = await import('./store');
    useSoftphoneStore.getState().init();
    await vi.advanceTimersByTimeAsync(0);
    events.onRegistered();
    await vi.advanceTimersByTimeAsync(STATUS_POLL_MS);
    expect(meSoftphoneStatus).toHaveBeenCalledTimes(1);
    expect(useSoftphoneStore.getState().connection).toBe('registered');

    meSoftphoneStatus.mockRejectedValue(new ApiError(409, { code: 'webrtc_disabled', message: 'x' }));
    await vi.advanceTimersByTimeAsync(STATUS_POLL_MS);
    expect(STATUS_POLL_MS * 2).toBeLessThanOrEqual(60_000);
    expect(useSoftphoneStore.getState().connection).toBe('unavailable');
    expect(engineApi.disconnect).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(STATUS_POLL_MS * 3);
    expect(meSoftphoneStatus).toHaveBeenCalledTimes(2); // to'xtagan
    vi.useRealTimers();
  });

  it('holat kuzatuvi: tarmoq xatosi ulanishni yopmaydi', async () => {
    vi.useFakeTimers();
    const { useSoftphoneStore, STATUS_POLL_MS } = await import('./store');
    useSoftphoneStore.getState().init();
    await vi.advanceTimersByTimeAsync(0);
    events.onRegistered();
    meSoftphoneStatus.mockRejectedValue(new Error('network'));
    await vi.advanceTimersByTimeAsync(STATUS_POLL_MS);
    expect(useSoftphoneStore.getState().connection).toBe('registered');
    vi.useRealTimers();
  });

  it('startCall faqat registered holatda ishlaydi', async () => {
    const { useSoftphoneStore } = await import('./store');
    expect(useSoftphoneStore.getState().connection).toBe('unavailable');
    useSoftphoneStore.getState().startCall('202');
    expect(engineApi.call).not.toHaveBeenCalled();
  });

  it('mute/hold/DTMF/transfer faol chaqiruvda engine metodlarini chaqiradi', async () => {
    const { useSoftphoneStore } = await import('./store');
    useSoftphoneStore.getState().init();
    await flush();
    events.onRegistered();
    useSoftphoneStore.getState().startCall('202');
    events.onEstablished();

    useSoftphoneStore.getState().toggleMute();
    expect(engineApi.mute).toHaveBeenCalledWith(true);
    expect(useSoftphoneStore.getState().call?.muted).toBe(true);

    useSoftphoneStore.getState().toggleHold();
    expect(engineApi.hold).toHaveBeenCalledWith(true);
    expect(useSoftphoneStore.getState().call?.phase).toBe('hold');

    useSoftphoneStore.getState().sendDigit('5');
    expect(engineApi.sendDtmf).toHaveBeenCalledWith('5');

    useSoftphoneStore.getState().transfer('303');
    expect(engineApi.transfer).toHaveBeenCalledWith('303');
  });
});
