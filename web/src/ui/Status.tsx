import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';
import { useEnumText } from '@/lib/useEnumText';

export type Status = 'online' | 'offline' | 'error' | 'disabled';
const STATUS_KEYS: Status[] = ['online', 'offline', 'error', 'disabled'];

/** Status matnlari uchun `common.status.*` kalitlaridan foydalaning (useStatusText). */
export function useStatusText(): Record<Status, string> {
  return useEnumText('common', 'status', STATUS_KEYS);
}

/**
 * Holat shakli rangdan mustaqil: onlayn — to'la doira, oflayn — halqa, xato — romb, o'chirilgan — chiziq.
 * Rang ko'rmaydigan admin ham farqlaydi.
 */
function StatusGlyph({ status }: { status: Status }) {
  const base = 'inline-block shrink-0';
  if (status === 'online') return <span aria-hidden className={cn(base, 'size-2 rounded-full bg-status-online')} />;
  if (status === 'offline') return <span aria-hidden className={cn(base, 'size-2 rounded-full border-[1.5px] border-status-offline')} />;
  if (status === 'error') return <span aria-hidden className={cn(base, 'size-[7px] rotate-45 rounded-[1px] bg-status-error')} />;
  return <span aria-hidden className={cn(base, 'h-[2px] w-2 rounded-full bg-status-disabled')} />;
}

export function StatusPill({ status, children, live, className }: { status: Status; children?: ReactNode; live?: boolean; className?: string }) {
  const { t } = useTranslation('common');
  const statusText = useStatusText();
  return (
    <span
      className={cn(
        'inline-flex h-5 items-center gap-1.5 whitespace-nowrap rounded-sm border px-1.5 text-xs font-medium',
        status === 'online' && 'border-success/25 bg-success-soft text-on-success-soft',
        status === 'offline' && 'border-line-strong bg-surface-2 text-muted',
        status === 'error' && 'border-danger/25 bg-danger-soft text-on-danger-soft',
        status === 'disabled' && 'border-dashed border-line-strong bg-transparent text-muted',
        className,
      )}
    >
      <StatusGlyph status={status} />
      {children ?? statusText[status]}
      {live && <LiveDot className="ml-0.5" label={t('status.liveUpdating')} />}
    </span>
  );
}

/** Oltin «jonli» belgisi. Ogohlantirish emas — faqat ma'lumot real vaqtda kelayotganini bildiradi. */
export function LiveDot({ className, label }: { className?: string; label?: string }) {
  const { t } = useTranslation('common');
  return (
    <span className={cn('relative inline-flex size-2 shrink-0', className)}>
      <span aria-hidden className="absolute inset-0 animate-live-pulse rounded-full bg-live" />
      <span aria-hidden className="relative size-2 rounded-full bg-live ring-1 ring-fg/25" />
      <span className="sr-only">{label ?? t('status.live')}</span>
    </span>
  );
}

export function LiveTag() {
  const { t } = useTranslation('common');
  return (
    <span className="inline-flex h-5 items-center gap-1.5 rounded-sm bg-live px-1.5 text-2xs text-on-live">
      <span aria-hidden className="size-1.5 animate-pulse rounded-full bg-on-live" />
      {t('status.liveTag')}
    </span>
  );
}

export type Tone = 'neutral' | 'accent' | 'success' | 'warning' | 'danger' | 'info';
const TONE: Record<Tone, string> = {
  neutral: 'bg-surface-2 text-muted border-line',
  accent: 'bg-accent-soft text-on-accent-soft border-brand/25',
  success: 'bg-success-soft text-on-success-soft border-success/25',
  warning: 'bg-warning-soft text-on-warning-soft border-warning/30',
  danger: 'bg-danger-soft text-on-danger-soft border-danger/25',
  info: 'bg-info-soft text-on-info-soft border-info/25',
};

export function Badge({ tone = 'neutral', children, mono, className }: { tone?: Tone; children: ReactNode; mono?: boolean; className?: string }) {
  return (
    <span className={cn('inline-flex h-5 items-center gap-1 whitespace-nowrap rounded-sm border px-1.5 text-xs font-medium [&_svg]:size-3', TONE[tone], mono && 'num', className)}>
      {children}
    </span>
  );
}
