// M3a §4/§5 — diagnostika xulosasi (isbot shu raqamlarga tayanadi).
import { describe, expect, it } from 'vitest';
import { summarizeStats, transferSucceeded } from './engine';

function report(entries: Record<string, unknown>[]) {
  return { forEach: (cb: (r: RTCStats & Record<string, unknown>) => void) => entries.forEach((e) => cb(e as RTCStats & Record<string, unknown>)) };
}
const sender = (kind: string, enabled: boolean) => ({ track: { kind, enabled } }) as unknown as RTCRtpSender;

describe('summarizeStats', () => {
  it('outbound/inbound paketlar, energiya va birinchi kodek yigʻiladi', () => {
    const r = report([
      { type: 'outbound-rtp', packetsSent: 60 },
      { type: 'outbound-rtp', packetsSent: 2 },
      { type: 'inbound-rtp', packetsReceived: 70, totalAudioEnergy: 0.5 },
      { type: 'inbound-rtp', packetsReceived: 1, totalAudioEnergy: 0.25 },
      { type: 'codec', mimeType: 'audio/opus' },
      { type: 'codec', mimeType: 'audio/PCMU' },
      { type: 'transport', packetsSent: 999 },
    ]);
    expect(summarizeStats(r, [sender('audio', true)])).toEqual({
      packetsSent: 62, packetsReceived: 71, codec: 'opus', micEnabled: true, audioEnergy: 0.75,
    });
  });

  it('maydonlar yoʻq boʻlsa nol; mikrofon treki oʻchiq yoki yoʻq — micEnabled=false', () => {
    const r = report([{ type: 'outbound-rtp' }, { type: 'inbound-rtp' }, { type: 'codec', mimeType: 7 }]);
    expect(summarizeStats(r, [sender('audio', false)])).toEqual({
      packetsSent: 0, packetsReceived: 0, codec: null, micEnabled: false, audioEnergy: 0,
    });
    expect(summarizeStats(report([]), [sender('video', true), { track: null } as unknown as RTCRtpSender]).micEnabled).toBe(false);
  });

  it('kodek mimeType\'da "/" boʻlmasa null', () => {
    expect(summarizeStats(report([{ type: 'codec', mimeType: 'opus' }]), []).codec).toBeNull();
  });
});

describe('transferSucceeded (REFER NOTIFY sipfrag)', () => {
  it.each([
    ['SIP/2.0 200 OK', true],
    ['  SIP/2.0 202 Accepted\r\n', true],
    ['SIP/2.0 100 Trying', false],
    ['SIP/2.0 180 Ringing', false],
    ['SIP/2.0 503 Service Unavailable', false],
    ['SIP/2.0 2', false],
    ['xSIP/2.0 200 OK', false],
    ['', false],
    [undefined, false],
  ])('%j -> %s', (body, expected) => {
    expect(transferSucceeded(body)).toBe(expected);
  });
});
