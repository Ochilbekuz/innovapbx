import { useEffect, useState } from 'react';
import { ArrowRightLeft, Delete, Grip, Mic, MicOff, Pause, Phone, PhoneIncoming, PhoneOff, Play } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';
import { useEnumText } from '@/lib/useEnumText';
import { Button } from '@/ui/Button';
import { LiveDot } from '@/ui/Status';

export type CallState = 'idle' | 'incoming' | 'connecting' | 'talking' | 'hold';
const CALL_STATE_KEYS: CallState[] = ['idle', 'incoming', 'connecting', 'talking', 'hold'];

const KEYS: [string, string][] = [
  ['1', ''], ['2', 'ABC'], ['3', 'DEF'], ['4', 'GHI'], ['5', 'JKL'], ['6', 'MNO'],
  ['7', 'PQRS'], ['8', 'TUV'], ['9', 'WXYZ'], ['*', ''], ['0', '+'], ['#', ''],
];

/** Demo chaqiruvchi ismidan avatar harflarini hisoblaydi — ism tarjima qilinsa ham to'g'ri ishlaydi. */
const initialsOf = (name: string) => name.split(' ').map((w) => w[0] ?? '').join('').slice(0, 2).toUpperCase();

function useStateText(): Record<CallState, string> {
  return useEnumText('common', 'softphone.state', CALL_STATE_KEYS);
}

function useTimer(running: boolean) {
  const [s, setS] = useState(0);
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setS((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, [running]);
  useEffect(() => { if (!running) setS(0); }, [running]);
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

/** Header'dagi ixcham ko'rinish. */
export function SoftphoneChip({ state, number = '101', onClick }: { state: CallState; number?: string; onClick?: () => void }) {
  const { t } = useTranslation('common');
  const stateText = useStateText();
  const active = state === 'talking' || state === 'hold';
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={t('softphone.chipAriaLabel', { state: stateText[state] })}
      className={cn(
        'inline-flex h-ctl-md items-center gap-2 rounded-md border px-2.5 text-sm font-medium transition-colors duration-fast',
        state === 'incoming' ? 'border-brand bg-accent-soft text-on-accent-soft' : 'border-line bg-surface text-fg hover:bg-surface-2',
      )}
    >
      {state === 'incoming' ? <PhoneIncoming aria-hidden className="size-4 animate-pulse" /> : <Phone aria-hidden className="size-4" />}
      <span className="num">{number}</span>
      {active && <LiveDot label={t('softphone.activeCallLabel')} />}
    </button>
  );
}

/** Kengaytirilgan panel: tergich + qo'ng'iroq boshqaruvi. Demo holatni tashqaridan boshqaradi. */
export function SoftphonePanel({ state, onState }: { state: CallState; onState: (s: CallState) => void }) {
  const { t } = useTranslation('common');
  const stateText = useStateText();
  const [num, setNum] = useState('');
  const [muted, setMuted] = useState(false);
  const clock = useTimer(state === 'talking' || state === 'hold');
  const inCall = state === 'talking' || state === 'hold';
  const callerName = t('softphone.demoCallerName');

  return (
    <section aria-label={t('softphone.panelAriaLabel')} className="w-[300px] overflow-hidden rounded-lg border border-line bg-raised shadow-pop">
      <header className="flex items-center justify-between border-b border-line px-3 py-2">
        <span className="inline-flex items-center gap-2 text-sm font-medium">
          <span aria-hidden className={cn('size-2 rounded-full', state === 'idle' ? 'bg-status-online' : state === 'hold' ? 'bg-status-warning' : 'bg-brand')} />
          {stateText[state]}
        </span>
        <span className="num text-xs text-muted">{t('softphone.extensionLine', { ext: '101' })}</span>
      </header>

      {state === 'incoming' || inCall || state === 'connecting' ? (
        <div className="px-4 pb-4 pt-5 text-center">
          <div aria-hidden className="mx-auto grid size-14 place-items-center rounded-full bg-surface-2 font-display text-lg font-semibold text-fg">{initialsOf(callerName)}</div>
          <p className="mt-3 text-md font-semibold text-fg">{callerName}</p>
          <p className="num text-sm text-muted">+998 90 318 42 07</p>
          <p className="num mt-1 h-5 text-sm text-fg" role="timer" aria-live="off">
            {inCall ? clock : state === 'incoming' ? t('softphone.waitingQueue') : ''}
          </p>
          {state === 'hold' && <p className="mt-2 rounded-sm bg-warning-soft px-2 py-1 text-xs text-on-warning-soft">{t('softphone.holdMusic')}</p>}
          {state === 'incoming' ? (
            <div className="mt-5 grid grid-cols-2 gap-2">
              <Button variant="danger" icon={<PhoneOff />} onClick={() => onState('idle')}>{t('softphone.decline')}</Button>
              <Button variant="primary" icon={<Phone />} onClick={() => onState('talking')}>{t('softphone.answer')}</Button>
            </div>
          ) : (
            <>
              <div className="mt-5 grid grid-cols-4 gap-1.5">
                <Button variant="secondary" iconOnly aria-label={muted ? t('softphone.muteOff') : t('softphone.muteOn')} aria-pressed={muted} icon={muted ? <MicOff /> : <Mic />} onClick={() => setMuted((m) => !m)} disabled={!inCall} />
                <Button variant="secondary" iconOnly aria-label={state === 'hold' ? t('softphone.holdOff') : t('softphone.holdOn')} aria-pressed={state === 'hold'} icon={state === 'hold' ? <Play /> : <Pause />} onClick={() => onState(state === 'hold' ? 'talking' : 'hold')} disabled={!inCall} />
                <Button variant="secondary" iconOnly aria-label={t('softphone.transfer')} icon={<ArrowRightLeft />} disabled={!inCall} />
                <Button variant="secondary" iconOnly aria-label={t('softphone.keypad')} icon={<Grip />} disabled={!inCall} />
              </div>
              <Button variant="danger" className="mt-2 w-full" icon={<PhoneOff />} onClick={() => onState('idle')}>{t('softphone.hangup')}</Button>
            </>
          )}
        </div>
      ) : (
        <div className="p-3">
          <div className="flex h-12 items-center gap-1 rounded-md border border-line bg-surface-2 px-3">
            <input
              aria-label={t('softphone.dialInputAriaLabel')}
              value={num}
              onChange={(e) => setNum(e.target.value.replace(/[^\d*#+]/g, ''))}
              onKeyDown={(e) => e.key === 'Enter' && num && onState('connecting')}
              placeholder={t('softphone.dialPlaceholder')}
              inputMode="tel"
              className="num min-w-0 flex-1 bg-transparent text-lg text-fg placeholder:font-sans placeholder:text-base placeholder:text-muted focus-visible:outline-none"
            />
            {num && <Button variant="ghost" size="sm" iconOnly aria-label={t('softphone.backspaceAriaLabel')} icon={<Delete />} onClick={() => setNum((n) => n.slice(0, -1))} />}
          </div>
          <div className="mt-2 grid grid-cols-3 gap-1.5">
            {KEYS.map(([k, sub]) => (
              <button
                key={k}
                type="button"
                onClick={() => setNum((n) => n + k)}
                aria-label={k}
                className="flex h-11 flex-col items-center justify-center rounded-md border border-line bg-surface text-fg transition-colors duration-fast hover:bg-surface-2 active:translate-y-px"
              >
                <span className="num text-md leading-5">{k}</span>
                <span aria-hidden className="h-3 text-[9px] font-semibold tracking-[0.12em] text-muted">{sub}</span>
              </button>
            ))}
          </div>
          <Button variant="primary" size="lg" className="mt-2 w-full" icon={<Phone />} disabled={!num} onClick={() => onState('connecting')}>
            {t('softphone.call')}
          </Button>
        </div>
      )}
    </section>
  );
}
