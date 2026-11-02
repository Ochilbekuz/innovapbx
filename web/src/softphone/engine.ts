// M3a §4 — SIP.js (0.21) o'rami. UI/store SIP.js'ni bevosita bilmaydi — faqat shu interfeys orqali
// (testda `vi.mock('@/softphone/engine')` bilan osongina almashtiriladi).
import { Inviter, Invitation, Registerer, RegistererState, Session, SessionState, UserAgent, Web } from 'sip.js';
import type { NameAddrHeader } from 'sip.js';
import type { SoftphoneInfo } from '@/api/types';
import type { SoftphoneDiagStats } from './types';

export type IncomingCallInfo = { remoteNumber: string; remoteName?: string };

export type SoftphoneEngineEvents = {
  onRegistered: () => void;
  onUnregistered: () => void;
  onRegistrationFailed: (reason: string) => void;
  /** Transport uzildi (WS yopildi) — ticket eskirgan yoki tarmoq xato bo'lishi mumkin. */
  onDisconnected: () => void;
  onIncoming: (call: IncomingCallInfo) => void;
  onOutgoingProgress: () => void;
  onEstablished: () => void;
  onEnded: (reason?: string) => void;
  onFailed: (reason: string) => void;
};

export interface SoftphoneEngine {
  connect(info: SoftphoneInfo): Promise<void>;
  disconnect(): Promise<void>;
  call(number: string): void;
  answer(): void;
  reject(): void;
  hangup(): void;
  mute(muted: boolean): void;
  hold(held: boolean): void;
  sendDtmf(digit: string): void;
  transfer(number: string): void;
  attachRemoteAudio(el: HTMLAudioElement | null): void;
  getStats(): Promise<SoftphoneDiagStats | null>;
}

/** Shartnoma §0: brauzer SIP'ni faqat `/sip-ws` orqali ko'radi — WS manzili shundan tuziladi. */
export function softphoneWsUrl(wsPath: string, ticket: string): string {
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${scheme}://${location.host}${wsPath}?t=${encodeURIComponent(ticket)}`;
}

function identityOf(id: NameAddrHeader): IncomingCallInfo {
  return { remoteNumber: id.uri.user ?? id.uri.toString(), remoteName: id.displayName || undefined };
}

function webSdh(session: Session | null): Web.SessionDescriptionHandler | undefined {
  return session?.sessionDescriptionHandler as Web.SessionDescriptionHandler | undefined;
}

class SipSoftphoneEngine implements SoftphoneEngine {
  private userAgent: UserAgent | null = null;
  private registerer: Registerer | null = null;
  private session: Inviter | Invitation | null = null;
  private audioEl: HTMLAudioElement | null = null;

  constructor(private readonly events: SoftphoneEngineEvents) {}

  async connect(info: SoftphoneInfo): Promise<void> {
    await this.disconnect();
    const uri = UserAgent.makeURI(info.sip.uri);
    if (!uri) throw new Error('SIP URI notoʻgʻri');
    const userAgent = new UserAgent({
      uri,
      authorizationUsername: info.sip.auth_user,
      authorizationPassword: info.sip.password,
      transportOptions: { server: softphoneWsUrl(info.ws_path, info.ticket) },
      sessionDescriptionHandlerFactoryOptions: info.ice_servers.length > 0 ? { peerConnectionConfiguration: { iceServers: info.ice_servers } } : {},
      delegate: {
        onInvite: (invitation) => this.handleInvite(invitation),
        onDisconnect: () => this.events.onDisconnected(),
      },
      logLevel: 'error',
    });
    this.userAgent = userAgent;
    await userAgent.start();

    const registerer = new Registerer(userAgent, { expires: 300 });
    this.registerer = registerer;
    registerer.stateChange.addListener((state) => {
      if (state === RegistererState.Registered) this.events.onRegistered();
      else if (state === RegistererState.Unregistered) this.events.onUnregistered();
    });
    await registerer.register().catch((e: unknown) => {
      this.events.onRegistrationFailed(e instanceof Error ? e.message : 'register_failed');
      throw e;
    });
  }

  async disconnect(): Promise<void> {
    this.session = null;
    const registerer = this.registerer;
    const userAgent = this.userAgent;
    this.registerer = null;
    this.userAgent = null;
    if (registerer) await registerer.unregister().catch(() => undefined);
    if (userAgent) await userAgent.stop().catch(() => undefined);
  }

  private handleInvite(invitation: Invitation): void {
    if (this.session) {
      void invitation.reject({ statusCode: 486 }); // band — ikkinchi chaqiruvni rad etamiz (M3a dan tashqari: "ikki qurilma")
      return;
    }
    this.session = invitation;
    this.bindSession(invitation);
    this.events.onIncoming(identityOf(invitation.remoteIdentity));
  }

  private bindSession(session: Inviter | Invitation): void {
    session.stateChange.addListener((state) => {
      if (state === SessionState.Established) {
        this.attachRemoteAudio(this.audioEl);
        this.events.onEstablished();
      } else if (state === SessionState.Terminated) {
        if (this.session === session) this.session = null;
        this.events.onEnded();
      }
    });
  }

  call(number: string): void {
    const userAgent = this.userAgent;
    if (!userAgent) return;
    const target = UserAgent.makeURI(`sip:${number}@${userAgent.configuration.uri.host}`);
    if (!target) {
      this.events.onFailed('bad_number');
      return;
    }
    const inviter = new Inviter(userAgent, target, { sessionDescriptionHandlerOptions: { constraints: { audio: true, video: false } } });
    this.session = inviter;
    this.bindSession(inviter);
    this.events.onOutgoingProgress();
    inviter.invite().catch((e: unknown) => this.events.onFailed(e instanceof Error ? e.message : 'invite_failed'));
  }

  answer(): void {
    if (!(this.session instanceof Invitation)) return;
    void this.session.accept({ sessionDescriptionHandlerOptions: { constraints: { audio: true, video: false } } })
      .catch((e: unknown) => this.events.onFailed(e instanceof Error ? e.message : 'accept_failed'));
  }

  reject(): void {
    if (this.session instanceof Invitation) void this.session.reject().catch(() => undefined);
    this.session = null;
  }

  hangup(): void {
    const session = this.session;
    if (!session) return;
    this.session = null;
    if (session.state === SessionState.Established) void session.bye().catch(() => undefined);
    else if (session instanceof Inviter) void session.cancel().catch(() => undefined);
    else if (session instanceof Invitation) void session.reject().catch(() => undefined);
  }

  mute(muted: boolean): void {
    webSdh(this.session)?.peerConnection?.getSenders().forEach((sender) => {
      if (sender.track) sender.track.enabled = !muted;
    });
  }

  /** Hold = re-INVITE bilan `sendonly`/`inactive` SDP (SIP.js `Web.holdModifier`); unhold — modifiersiz re-INVITE. */
  hold(held: boolean): void {
    const session = this.session;
    if (!session) return;
    void session.invite({ sessionDescriptionHandlerModifiers: held ? [Web.holdModifier] : [] }).catch(() => undefined);
  }

  sendDtmf(digit: string): void {
    webSdh(this.session)?.sendDtmf(digit);
  }

  transfer(number: string): void {
    const session = this.session;
    const userAgent = this.userAgent;
    if (!session || !userAgent) return;
    const target = UserAgent.makeURI(`sip:${number}@${userAgent.configuration.uri.host}`);
    if (!target) return;
    // Blind transfer: Asterisk REFER natijasini NOTIFY (sipfrag) bilan bildiradi, lekin o'tkazuvchi
    // tomonni o'zi UZMAYDI — 2xx kelganda BYE bizdan (aks holda B "gaplashmoqda"da osilib qoladi).
    void session.refer(target, {
      onNotify: (notification) => {
        void notification.accept().catch(() => undefined);
        if (this.session === session && transferSucceeded(notification.request.body)) this.hangup();
      },
    }).catch(() => undefined);
  }

  attachRemoteAudio(el: HTMLAudioElement | null): void {
    this.audioEl = el;
    const stream = webSdh(this.session)?.remoteMediaStream;
    if (el && stream) el.srcObject = stream;
  }

  async getStats(): Promise<SoftphoneDiagStats | null> {
    const pc = webSdh(this.session)?.peerConnection;
    if (!pc) return null;
    return summarizeStats(await pc.getStats(), pc.getSenders());
  }
}

/** REFER NOTIFY tanasi (message/sipfrag, masalan `SIP/2.0 200 OK`) — transfer muvaffaqiyatlimi. */
export function transferSucceeded(sipfrag: string | undefined): boolean {
  return /^SIP\/2\.0 2\d\d/.test((sipfrag ?? '').trim());
}

type StatEntry = RTCStats & Record<string, unknown>;

const num = (v: unknown): number => Number(v ?? 0);
const codecName = (mime: unknown): string | null => (typeof mime === 'string' ? (mime.split('/')[1] ?? null) : null);

/** getStats yozuv turi -> xulosaga qo'shish (boshqa turlar e'tiborsiz). */
const COLLECTORS: Record<string, (out: SoftphoneDiagStats, r: StatEntry) => void> = {
  'outbound-rtp': (out, r) => { out.packetsSent += num(r.packetsSent); },
  'inbound-rtp': (out, r) => {
    out.packetsReceived += num(r.packetsReceived);
    out.audioEnergy += num(r.totalAudioEnergy);
  },
  codec: (out, r) => { out.codec ??= codecName(r.mimeType); },
};

/** RTCStatsReport -> isbot uchun qisqa xulosa (sof funksiya — unit test qilinadi). */
export function summarizeStats(report: { forEach: (cb: (r: StatEntry) => void) => void }, senders: RTCRtpSender[]): SoftphoneDiagStats {
  const out: SoftphoneDiagStats = { packetsSent: 0, packetsReceived: 0, codec: null, micEnabled: false, audioEnergy: 0 };
  report.forEach((r) => COLLECTORS[r.type]?.(out, r));
  out.micEnabled = senders.some((s) => s.track?.kind === 'audio' && s.track.enabled);
  return out;
}

export function createSoftphoneEngine(events: SoftphoneEngineEvents): SoftphoneEngine {
  return new SipSoftphoneEngine(events);
}
