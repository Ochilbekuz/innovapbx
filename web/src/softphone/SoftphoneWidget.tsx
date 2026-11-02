// M3a §4 — AppShell headeridagi haqiqiy softfon: chip + popover panel. Dizayn `pbx/Softphone.tsx`
// (demo) bilan bir xil uslubda, lekin holatni `useSoftphoneStore`dan oladi (SIP.js bilan ulangan).
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import * as Popover from '@radix-ui/react-popover';
import {
  ArrowRightLeft, Delete, LoaderCircle, Mic, MicOff, Pause, Phone, PhoneIncoming, PhoneOff, Play, TriangleAlert,
} from 'lucide-react';
import { cn } from '@/lib/cn';
import { Button } from '@/ui/Button';
import { LiveDot } from '@/ui/Status';
import { useSoftphoneStore } from './store';
import type { ActiveCall, CallPhase, ConnectionState } from './types';

const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '0', '#'];

function useElapsed(startedAt: number | null): string {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (startedAt == null) {
      setSeconds(0);
      return;
    }
    const tick = () => setSeconds(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startedAt]);
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}

function dotClass(connection: ConnectionState, phase: CallPhase | undefined): string {
  if (phase === 'incoming') return 'bg-brand animate-pulse';
  if (phase === 'talking' || phase === 'outgoing') return 'bg-live';
  if (phase === 'hold') return 'bg-status-warning';
  if (connection === 'registered') return 'bg-status-online';
  if (connection === 'error') return 'bg-status-error';
  return 'bg-status-offline';
}

/** Chip'ning chap tomondagi belgisi — kiruvchi/ulanmoqda/holat nuqtasi. */
function ChipIndicator({ connection, phase }: { connection: ConnectionState; phase: CallPhase | undefined }) {
  if (phase === 'incoming') return <PhoneIncoming aria-hidden className="size-4 animate-pulse" />;
  if (connection === 'connecting') return <LoaderCircle aria-hidden className="size-4 animate-spin" />;
  return <span aria-hidden className={cn('size-2 rounded-full', dotClass(connection, phase))} />;
}

/** Header'dagi ixcham ko'rinish — raqam yo'q/webrtc emasda umuman render qilinmaydi (chaqiruvchi tekshiradi). */
const ACTIVE_PHASES: ReadonlySet<CallPhase> = new Set(['talking', 'hold']);

function isActivePhase(phase: CallPhase | undefined): boolean {
  return phase !== undefined && ACTIVE_PHASES.has(phase);
}

function SoftphoneChip({ number }: { number: string }) {
  const { t } = useTranslation('common');
  const connection = useSoftphoneStore((s) => s.connection);
  const call = useSoftphoneStore((s) => s.call);
  const phase = call?.phase;
  const incoming = phase === 'incoming';
  const stateText = t(call ? `softphone.state.${phase}` : `softphone.connection.${connection}`);
  return (
    <Popover.Trigger asChild>
      <button
        type="button"
        data-testid="softphone-chip"
        aria-label={t('softphone.chipAriaLabel', { state: stateText })}
        className={cn(
          'inline-flex h-ctl-md items-center gap-2 rounded-md border px-2.5 text-sm font-medium transition-colors duration-fast',
          incoming ? 'border-brand bg-accent-soft text-on-accent-soft' : 'border-line bg-surface text-fg hover:bg-surface-2',
        )}
      >
        <ChipIndicator connection={connection} phase={phase} />
        <span className="num">{number}</span>
        {isActivePhase(phase) && <LiveDot label={t('softphone.activeCallLabel')} />}
        <span key={phase ?? connection} className="sr-only" data-testid="softphone-state">{stateText}</span>
      </button>
    </Popover.Trigger>
  );
}

function DialPad({ onDigit }: { onDigit: (d: string) => void }) {
  return (
    <div className="mt-2 grid grid-cols-3 gap-1.5">
      {KEYS.map((k) => (
        <button
          key={k}
          type="button"
          onClick={() => onDigit(k)}
          aria-label={k}
          className="flex h-11 items-center justify-center rounded-md border border-line bg-surface text-fg transition-colors duration-fast hover:bg-surface-2 active:translate-y-px"
        >
          <span className="num text-md">{k}</span>
        </button>
      ))}
    </div>
  );
}

function IdleScreen() {
  const { t } = useTranslation('common');
  const micDenied = useSoftphoneStore((s) => s.micDenied);
  const [num, setNum] = useState('');
  const startCall = useSoftphoneStore((s) => s.startCall);
  const call = () => num.trim() && startCall(num.trim());

  return (
    <div className="p-3">
      {micDenied && (
        <p className="mb-2 flex items-start gap-1.5 rounded-md border border-danger/30 bg-danger-soft px-2.5 py-2 text-xs text-on-danger-soft">
          <TriangleAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />
          <span><strong className="font-medium">{t('softphone.micDeniedTitle')}</strong> {t('softphone.micDeniedBody')}</span>
        </p>
      )}
      <div className="flex h-12 items-center gap-1 rounded-md border border-line bg-surface-2 px-3">
        <input
          data-testid="softphone-dial-input"
          aria-label={t('softphone.dialInputAriaLabel')}
          value={num}
          onChange={(e) => setNum(e.target.value.replace(/[^\d*#+]/g, ''))}
          onKeyDown={(e) => e.key === 'Enter' && call()}
          placeholder={t('softphone.dialPlaceholder')}
          inputMode="tel"
          className="num min-w-0 flex-1 bg-transparent text-lg text-fg placeholder:font-sans placeholder:text-base placeholder:text-muted focus-visible:outline-none"
        />
        {num && <Button variant="ghost" size="sm" iconOnly aria-label={t('softphone.backspaceAriaLabel')} icon={<Delete />} onClick={() => setNum((n) => n.slice(0, -1))} />}
      </div>
      <DialPad onDigit={(d) => setNum((n) => n + d)} />
      <Button data-testid="softphone-call" variant="primary" size="lg" className="mt-2 w-full" icon={<Phone />} disabled={!num || micDenied} onClick={call}>
        {t('softphone.call')}
      </Button>
    </div>
  );
}

/** Qo'ng'iroq avatari — ism/raqamning bosh harflari. Tashqi va kiruvchi ekranlar bir xil shaklni ishlatadi. */
function CallAvatar({ label, testId, accent }: { label: string; testId?: string; accent?: boolean }) {
  return (
    <>
      <div
        aria-hidden
        className={cn(
          'mx-auto grid size-14 place-items-center rounded-full font-display text-lg font-semibold',
          accent ? 'bg-accent-soft text-on-accent-soft' : 'bg-surface-2 text-fg',
        )}
      >
        {label.slice(0, 2).toUpperCase()}
      </div>
      <p className="mt-3 text-md font-semibold text-fg" data-testid={testId}>{label}</p>
    </>
  );
}

function InCallControls({ call, onToggleTransfer }: { call: ActiveCall; onToggleTransfer: () => void }) {
  const { t } = useTranslation('common');
  const toggleMute = useSoftphoneStore((s) => s.toggleMute);
  const toggleHold = useSoftphoneStore((s) => s.toggleHold);
  const hangup = useSoftphoneStore((s) => s.hangup);
  const connected = call.phase === 'talking' || call.phase === 'hold';
  return (
    <div className="mt-5 grid grid-cols-4 gap-1.5">
      <Button
        data-testid="softphone-mute" variant="secondary" iconOnly
        aria-label={call.muted ? t('softphone.muteOff') : t('softphone.muteOn')} aria-pressed={call.muted}
        icon={call.muted ? <MicOff /> : <Mic />} onClick={toggleMute} disabled={!connected}
      />
      <Button
        data-testid="softphone-hold" variant="secondary" iconOnly
        aria-label={call.phase === 'hold' ? t('softphone.holdOff') : t('softphone.holdOn')} aria-pressed={call.phase === 'hold'}
        icon={call.phase === 'hold' ? <Play /> : <Pause />} onClick={toggleHold} disabled={!connected}
      />
      <Button data-testid="softphone-transfer-toggle" variant="secondary" iconOnly aria-label={t('softphone.transfer')} icon={<ArrowRightLeft />} disabled={!connected} onClick={onToggleTransfer} />
      <Button data-testid="softphone-hangup" variant="danger" iconOnly aria-label={t('softphone.hangup')} icon={<PhoneOff />} onClick={hangup} />
    </div>
  );
}

function TransferPanel({ onSend }: { onSend: (number: string) => void }) {
  const { t } = useTranslation('common');
  const [value, setValue] = useState('');
  const send = () => {
    if (!value.trim()) return;
    onSend(value.trim());
    setValue('');
  };
  return (
    <div className="mt-3 flex items-center gap-1.5 rounded-md border border-line bg-surface-2 px-2 py-1.5">
      <input
        data-testid="softphone-transfer-input"
        aria-label={t('softphone.transferTitle')}
        value={value}
        onChange={(e) => setValue(e.target.value.replace(/[^\d*#+]/g, ''))}
        onKeyDown={(e) => e.key === 'Enter' && send()}
        placeholder={t('softphone.transferPlaceholder')}
        inputMode="tel"
        className="num min-w-0 flex-1 bg-transparent text-sm text-fg placeholder:font-sans placeholder:text-muted focus-visible:outline-none"
      />
      <Button data-testid="softphone-transfer" size="sm" variant="primary" disabled={!value.trim()} onClick={send}>
        {t('softphone.transferSend')}
      </Button>
    </div>
  );
}

/** Avatar, raqam, taymer/holat matni va kutish musiqasi eslatmasi — qo'ng'iroq boshida bir marta hisoblanadi. */
function InCallHeader({ call, connected, clock }: { call: ActiveCall; connected: boolean; clock: string }) {
  const { t } = useTranslation('common');
  const label = call.remoteName || call.remoteNumber;
  return (
    <>
      <CallAvatar label={label} />
      {call.remoteName && <p className="num text-sm text-muted">{call.remoteNumber}</p>}
      <p className="num mt-1 h-5 text-sm text-fg" role="timer" aria-live="off">
        {connected ? <span data-testid="softphone-timer">{clock}</span> : t(`softphone.state.${call.phase}`)}
      </p>
      {call.phase === 'hold' && <p className="mt-2 rounded-sm bg-warning-soft px-2 py-1 text-xs text-on-warning-soft">{t('softphone.holdMusic')}</p>}
    </>
  );
}

function InCallScreen() {
  const call = useSoftphoneStore((s) => s.call);
  const sendDigit = useSoftphoneStore((s) => s.sendDigit);
  const transfer = useSoftphoneStore((s) => s.transfer);
  const [transferOpen, setTransferOpen] = useState(false);
  const clock = useElapsed(call?.startedAt ?? null);
  if (!call) return null;
  const connected = call.phase === 'talking' || call.phase === 'hold';

  return (
    <div className="px-4 pb-4 pt-5 text-center">
      <InCallHeader call={call} connected={connected} clock={clock} />
      <InCallControls call={call} onToggleTransfer={() => setTransferOpen((v) => !v)} />
      {transferOpen && connected && <TransferPanel onSend={(n) => { transfer(n); setTransferOpen(false); }} />}
      {connected && <DialPad onDigit={sendDigit} />}
    </div>
  );
}

function IncomingScreen() {
  const { t } = useTranslation('common');
  const call = useSoftphoneStore((s) => s.call);
  const answer = useSoftphoneStore((s) => s.answer);
  const reject = useSoftphoneStore((s) => s.reject);
  if (!call) return null;
  const label = call.remoteName || call.remoteNumber;
  return (
    <div className="px-4 pb-4 pt-5 text-center">
      <CallAvatar label={label} testId="softphone-incoming-from" accent />
      {call.remoteName && <p className="num text-sm text-muted">{call.remoteNumber}</p>}
      <div className="mt-5 grid grid-cols-2 gap-2">
        <Button data-testid="softphone-reject" variant="danger" icon={<PhoneOff />} onClick={reject}>{t('softphone.decline')}</Button>
        <Button data-testid="softphone-answer" variant="primary" icon={<Phone />} onClick={answer}>{t('softphone.answer')}</Button>
      </div>
    </div>
  );
}

function StatusScreen({ connection, errorReason }: { connection: ConnectionState; errorReason: string | null }) {
  const { t } = useTranslation('common');
  return (
    <div className="px-4 py-6 text-center text-sm text-muted">
      {connection === 'connecting' && <LoaderCircle aria-hidden className="mx-auto mb-2 size-5 animate-spin text-muted" />}
      <p className="font-medium text-fg">{t(`softphone.connection.${connection}`)}</p>
      {connection === 'other_tab' && <p className="mt-1">{t('softphone.connection.otherTabBody')}</p>}
      {connection === 'error' && errorReason && <p className="mt-1 num">{errorReason}</p>}
    </div>
  );
}

function SoftphonePanel({ number }: { number: string }) {
  const { t } = useTranslation('common');
  const connection = useSoftphoneStore((s) => s.connection);
  const errorReason = useSoftphoneStore((s) => s.errorReason);
  const call = useSoftphoneStore((s) => s.call);
  const headerText = call ? t(`softphone.state.${call.phase}`) : t(`softphone.connection.${connection}`);

  return (
    <Popover.Portal>
      <Popover.Content align="end" sideOffset={8} className="z-popover w-[300px] overflow-hidden rounded-lg border border-line bg-raised shadow-pop data-[state=open]:animate-pop-in">
        <section aria-label={t('softphone.panelAriaLabel')}>
          <header className="flex items-center justify-between border-b border-line px-3 py-2">
            <span className="inline-flex items-center gap-2 text-sm font-medium">
              <span aria-hidden className={cn('size-2 rounded-full', dotClass(connection, call?.phase))} />
              <span data-testid="softphone-state">{headerText}</span>
            </span>
            <span className="num text-xs text-muted">{t('softphone.extensionLine', { ext: number })}</span>
          </header>
          {connection === 'registered' && call?.phase === 'incoming' ? (
            <IncomingScreen />
          ) : connection === 'registered' && call ? (
            <InCallScreen />
          ) : connection === 'registered' ? (
            <IdleScreen />
          ) : (
            <StatusScreen connection={connection} errorReason={errorReason} />
          )}
        </section>
      </Popover.Content>
    </Popover.Portal>
  );
}

/** AppShell header'ida joylashadigan haqiqiy softfon — webrtc yoqilgan ichki raqam bo'lmasa, umuman ko'rinmaydi. */
export function SoftphoneWidget({ number }: { number: string }) {
  const connection = useSoftphoneStore((s) => s.connection);
  const panelOpen = useSoftphoneStore((s) => s.panelOpen);
  const openPanel = useSoftphoneStore((s) => s.openPanel);
  const closePanel = useSoftphoneStore((s) => s.closePanel);
  const attachAudio = useSoftphoneStore((s) => s.attachAudio);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const visible = connection !== 'unavailable';

  // Masofaviy ovoz popover'dan TASHQARIDA: panel yopilganda (Radix Content unmount) gaplashuv ovozi uzilmasin.
  useEffect(() => {
    attachAudio(visible ? audioRef.current : null);
    return () => attachAudio(null);
  }, [attachAudio, visible]);

  // §4: "raqam yo'q/webrtc emas — chip ko'rinmaydi" — bu holat backend javobidan (`/me/softphone`) keladi.
  if (!visible) return null;

  return (
    <Popover.Root open={panelOpen} onOpenChange={(v) => (v ? openPanel() : closePanel())}>
      <SoftphoneChip number={number} />
      <SoftphonePanel number={number} />
      <audio ref={audioRef} autoPlay hidden data-testid="softphone-remote-audio" />
    </Popover.Root>
  );
}
