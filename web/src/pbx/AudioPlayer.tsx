import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type RefObject } from 'react';
import { Download, FileWarning, LoaderCircle, Pause, Play } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';
import { Button } from '@/ui/Button';

/** Manzil (ochiq fayl) yoki token bilan faylni oluvchi funksiya — `<audio src>` Authorization yubora olmaydi. */
type AudioFetcher = { (): Promise<Blob> };
export type AudioSource = string | AudioFetcher;
type Variant = 'inline' | 'full';
type PlayState = 'idle' | 'loading' | 'playing' | 'paused' | 'error';

type Props = {
  src: AudioSource | null;
  title?: string;
  meta?: string;
  /** inline — jadval qatori ichida; full — audio kutubxona / ovozli pochta. */
  variant?: Variant;
  /** To'lqin shakli uchun barqaror urug' (fayl id). */
  seed?: number;
};

const RATES = [1, 1.5, 2] as const;
const PLAY_BUTTON = { full: { variant: 'primary', size: 'lg' }, inline: { variant: 'secondary', size: 'sm' } } as const;
const SEEK_KEYS: Record<string, (t: number, dur: number, step: number) => number> = {
  ArrowRight: (t, _d, step) => t + step,
  ArrowLeft: (t, _d, step) => t - step,
  Home: () => 0,
  End: (_t, dur) => dur,
};

export const fmt = (s: number) => {
  if (!Number.isFinite(s)) return '0:00';
  const m = Math.floor(s / 60);
  return `${m}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
};

function bars(seed: number, n: number): number[] {
  let x = seed || 1;
  return Array.from({ length: n }, (_, i) => {
    x = (x * 16807) % 2147483647;
    const env = Math.sin((i / n) * Math.PI) * 0.6 + 0.4;
    return 0.18 + env * 0.82 * ((x % 1000) / 1000);
  });
}

type MediaEvent = { currentTarget: HTMLAudioElement };

function mediaEvents(setState: (s: PlayState) => void, setT: (n: number) => void, setDur: (n: number) => void) {
  return {
    onLoadedMetadata: (e: MediaEvent) => setDur(e.currentTarget.duration),
    onTimeUpdate: (e: MediaEvent) => setT(e.currentTarget.currentTime),
    onPlaying: () => setState('playing'),
    onPause: () => setState('paused'),
    onWaiting: () => setState('loading'),
    onEnded: () => setState('paused'),
    onError: () => setState('error'),
  };
}

const clamp = (s: number, dur: number) => Math.min(dur, Math.max(0, s));

/** Funksiya manba — birinchi «Tinglash»da bir marta olinadi (sahifa ochilganda o'nlab fayl yuklanmaydi). */
function useLazySource(src: AudioSource | null) {
  const objectUrl = useRef<string | null>(null);
  useEffect(() => () => { if (objectUrl.current) URL.revokeObjectURL(objectUrl.current); }, []);
  return async (a: HTMLAudioElement) => {
    if (typeof src !== 'function' || objectUrl.current) return;
    objectUrl.current = URL.createObjectURL(await src());
    a.src = objectUrl.current;
  };
}

// `src` oʻrnatilganda brauzer `playbackRate`ni `defaultPlaybackRate`ga qaytaradi — ikkalasi ham shart,
// aks holda ijrodan oldin tanlangan 2× birinchi «Tinglash»da yoʻqoladi.
function applyRate(a: HTMLAudioElement, rate: number) {
  a.defaultPlaybackRate = rate;
  a.playbackRate = rate;
}

/** Ijro paytida oddiy bosish — pauza; chiziqdan joy tanlash (`startAt`) esa ijroni toʻxtatmaydi. */
const isPauseClick = (a: HTMLAudioElement, startAt?: number) => !a.paused && startAt === undefined;

function seekAudio(a: HTMLAudioElement | null, s: number, dur: number) {
  if (a && dur) a.currentTime = clamp(s, dur);
}

const nextRateOf = (r: number) => RATES[(RATES.indexOf(r as (typeof RATES)[number]) + 1) % RATES.length]!;

async function startPlayback(a: HTMLAudioElement, prepare: ReturnType<typeof useLazySource>, startAt?: number) {
  await prepare(a);
  if (startAt !== undefined) a.currentTime = Math.max(0, startAt);
  await a.play();
}

/** Ijro holati — `<audio>` hodisalari va funksiya manbani birinchi «Tinglash»da bir marta olish. */
export function usePlayback(src: AudioSource | null) {
  const audio = useRef<HTMLAudioElement>(null);
  const prepare = useLazySource(src);
  const [state, setState] = useState<PlayState>(src ? 'idle' : 'error');
  const [t, setT] = useState(0);
  const [dur, setDur] = useState(0);
  const [rate, setRate] = useState<number>(1);

  useEffect(() => { if (audio.current) applyRate(audio.current, rate); }, [rate]);

  /** `startAt` — hali ijro boshlanmagan yozuvni chiziqning istalgan joyidan boshlash. */
  const toggle = async (startAt?: number) => {
    const a = audio.current;
    if (!a || state === 'error') return;
    if (isPauseClick(a, startAt)) return a.pause();
    setState('loading');
    await startPlayback(a, prepare, startAt).catch(() => setState('error'));
  };

  const seek = (s: number) => seekAudio(audio.current, s, dur);
  const nextRate = () => setRate(nextRateOf);

  const events = mediaEvents(setState, setT, setDur);
  return { audio, state, t, dur, rate, toggle, seek, nextRate, events };
}

export function playIcon(state: PlayState) {
  if (state === 'loading') return <LoaderCircle className="animate-spin" />;
  if (state === 'error') return <FileWarning />;
  return state === 'playing' ? <Pause /> : <Play className="translate-x-px" />;
}

function usePlayLabel(state: PlayState) {
  const { t } = useTranslation('common');
  if (state === 'error') return t('audioPlayer.unplayable');
  return state === 'playing' ? t('audioPlayer.pause') : t('audioPlayer.listen');
}

type WaveProps = { title?: string; variant: Variant; seed: number; t: number; dur: number; seek: (s: number) => void };

function Waveform({ title, variant, seed, t: pos, dur, seek }: WaveProps) {
  const { t } = useTranslation('common');
  const wave = useMemo(() => bars(seed, variant === 'inline' ? 120 : 80), [seed, variant]);
  const progress = dur ? pos / dur : 0;
  const onKey = (e: KeyboardEvent) => {
    const to = SEEK_KEYS[e.key];
    if (!to) return;
    e.preventDefault();
    seek(to(pos, dur, e.shiftKey ? 15 : 5));
  };
  return (
    <div
      role="slider"
      tabIndex={0}
      aria-label={title ? t('audioPlayer.positionWithTitle', { title }) : t('audioPlayer.positionDefault')}
      aria-valuemin={0}
      aria-valuemax={Math.round(dur)}
      aria-valuenow={Math.round(pos)}
      aria-valuetext={`${fmt(pos)} / ${fmt(dur)}`}
      onKeyDown={onKey}
      onPointerDown={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        seek(((e.clientX - r.left) / r.width) * dur);
      }}
      className={cn('group flex cursor-pointer items-center justify-between gap-px rounded-sm', variant === 'inline' ? 'h-6' : 'h-9')}
    >
      {wave.map((v, i) => (
        <span
          key={i}
          aria-hidden
          style={{ height: `${Math.round(v * 100)}%` }}
          className={cn('w-[2px] min-h-[2px] shrink-0 rounded-full transition-colors duration-fast', i / wave.length < progress ? 'bg-brand' : 'bg-line-strong group-hover:bg-input/60')}
        />
      ))}
    </div>
  );
}

/** Tezlik tugmasi: 1× → 1.5× → 2× → 1× (toʻliq pleer va jadvaldagi yozuv qatori uchun bitta). */
export function RateButton({ rate, nextRate }: { rate: number; nextRate: () => void }) {
  const { t } = useTranslation('common');
  return (
    <button
      type="button"
      onClick={nextRate}
      aria-label={t('audioPlayer.rateChange', { rate })}
      className={cn('num h-ctl-sm min-w-[2.25rem] shrink-0 rounded-sm border px-1.5 text-xs hover:bg-surface-2', rate === 1 ? 'border-line text-fg' : 'border-brand/40 bg-accent-soft text-on-accent-soft')}
    >
      {rate}×
    </button>
  );
}

function ExtraControls({ rate, nextRate, href }: { rate: number; nextRate: () => void; href: string | null }) {
  const { t } = useTranslation('common');
  return (
    <>
      <RateButton rate={rate} nextRate={nextRate} />
      {href && (
        <a href={href} download className="grid size-ctl-sm place-items-center rounded-sm text-muted hover:bg-surface-2 hover:text-fg" aria-label={t('audioPlayer.download')}>
          <Download aria-hidden className="size-4" />
        </a>
      )}
    </>
  );
}

function TitleRow({ title, meta }: { title?: string; meta?: string }) {
  if (!title && !meta) return null;
  return (
    <div className="mb-1.5 flex items-baseline justify-between gap-3">
      <p className="truncate text-base font-medium text-fg">{title}</p>
      {meta && <p className="num shrink-0 text-xs text-muted">{meta}</p>}
    </div>
  );
}

type AudioElementProps = {
  src: AudioSource;
  audio: RefObject<HTMLAudioElement>;
  events: ReturnType<typeof mediaEvents>;
};

function AudioElement({ src, audio, events }: AudioElementProps) {
  const open = typeof src === 'string';
  return <audio ref={audio} src={open ? src : undefined} preload={open ? 'metadata' : 'none'} {...events} />;
}

export function AudioPlayer({ src, title, meta, variant = 'full', seed = 7 }: Props) {
  const { t } = useTranslation('common');
  const p = usePlayback(src);
  const full = variant === 'full';
  const failed = p.state === 'error';
  const playLabel = usePlayLabel(p.state);

  return (
    <div className={cn('flex items-center gap-3', full && 'rounded-lg border border-line bg-surface p-3 shadow-card')}>
      {src && <AudioElement src={src} audio={p.audio} events={p.events} />}
      <Button
        {...PLAY_BUTTON[variant]}
        iconOnly
        className="rounded-full"
        aria-label={playLabel}
        disabled={failed}
        icon={playIcon(p.state)}
        onClick={() => void p.toggle()}
      />
      <div className="min-w-0 flex-1">
        {full && <TitleRow title={title} meta={meta} />}
        {failed ? (
          <p className="text-sm text-danger">{t('audioPlayer.notFound')}</p>
        ) : (
          <Waveform title={title} variant={variant} seed={seed} t={p.t} dur={p.dur} seek={p.seek} />
        )}
      </div>
      <span className="num w-[84px] shrink-0 text-right text-xs text-muted" aria-hidden>{fmt(p.t)} / {fmt(p.dur)}</span>
      {full && !failed && <ExtraControls rate={p.rate} nextRate={p.nextRate} href={typeof src === 'string' ? src : null} />}
    </div>
  );
}
