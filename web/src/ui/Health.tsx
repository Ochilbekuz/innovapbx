import type { ReactNode } from 'react';
import { CircleCheck, OctagonX, TriangleAlert } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';

export type HealthLevel = 'ok' | 'warn' | 'crit';

export type HealthItem = {
  id: string;
  label: string;
  level: HealthLevel;
  /** Qisqa o'lchov: «2 / 2 kanal», «71%», «12 ms». */
  value?: string;
  /** Nima uchun sariq/qizil — doim yoziladi, rang yolg'iz qolmaydi. */
  reason?: string;
  icon?: ReactNode;
};

const LEVEL_ICON: Record<HealthLevel, ReactNode> = {
  ok: <CircleCheck />,
  warn: <TriangleAlert />,
  crit: <OctagonX />,
};
const LEVEL_CLS: Record<HealthLevel, { cls: string; bar: string }> = {
  ok: { cls: 'text-success', bar: 'bg-status-online' },
  warn: { cls: 'text-warning', bar: 'bg-status-warning' },
  crit: { cls: 'text-danger', bar: 'bg-status-error' },
};

/** Darajaga mos chiziq rangi — foiz bar (masalan disk toʻlganligi) uchun ham shu rang shkalasi ishlatiladi. */
export function healthLevelBarClass(level: HealthLevel): string {
  return LEVEL_CLS[level].bar;
}

export function worstLevel(items: readonly HealthItem[]): HealthLevel {
  return items.some((i) => i.level === 'crit') ? 'crit' : items.some((i) => i.level === 'warn') ? 'warn' : 'ok';
}

/** Tizim sog'ligi ro'yxati: har qator — ikon shakli + matn + sabab. `action` — sarlavha yonida ixtiyoriy havola/tugma (masalan, batafsil sahifaga). */
export function HealthList({ items, title, action }: { items: HealthItem[]; title?: string; action?: ReactNode }) {
  const { t } = useTranslation('common');
  const levelText: Record<HealthLevel, string> = { ok: t('health.ok'), warn: t('health.warn'), crit: t('health.crit') };
  const LEVEL: Record<HealthLevel, { icon: ReactNode; text: string; cls: string; bar: string }> = {
    ok: { icon: LEVEL_ICON.ok, text: levelText.ok, ...LEVEL_CLS.ok },
    warn: { icon: LEVEL_ICON.warn, text: levelText.warn, ...LEVEL_CLS.warn },
    crit: { icon: LEVEL_ICON.crit, text: levelText.crit, ...LEVEL_CLS.crit },
  };
  const resolvedTitle = title ?? t('health.defaultTitle');
  const worst = LEVEL[worstLevel(items)];
  return (
    <section aria-label={resolvedTitle} className="overflow-hidden rounded-lg border border-line bg-surface shadow-card">
      <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
        <h3 className="font-display text-base font-semibold">{resolvedTitle}</h3>
        <div className="flex items-center gap-3">
          <span className={cn('inline-flex items-center gap-1.5 text-sm font-medium [&_svg]:size-4', worst.cls)}>
            {worst.icon}
            {worst.text}
          </span>
          {action}
        </div>
      </header>
      <ul className="divide-y divide-line">
        {items.map((i) => {
          const l = LEVEL[i.level];
          return (
            <li key={i.id} className="relative grid grid-cols-[20px_1fr_auto] items-start gap-x-3 px-4 py-2.5">
              <span aria-hidden className={cn('absolute inset-y-2 left-0 w-[3px] rounded-r', i.level === 'ok' ? 'bg-transparent' : l.bar)} />
              <span className={cn('mt-px [&_svg]:size-[18px]', l.cls)} aria-hidden>{l.icon}</span>
              <div className="min-w-0">
                <p className="text-base font-medium text-fg">
                  {i.label}
                  <span className="sr-only"> — {l.text}</span>
                </p>
                {i.reason && <p className="text-sm text-muted">{i.reason}</p>}
              </div>
              {i.value && <span className="num pt-px text-sm text-fg">{i.value}</span>}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** Header/sidebar uchun ixcham ko'rinish: segmentlar qatori. */
export function HealthStrip({ items }: { items: HealthItem[] }) {
  const { t } = useTranslation('common');
  const levelText: Record<HealthLevel, string> = { ok: t('health.ok'), warn: t('health.warn'), crit: t('health.crit') };
  const summary = items.map((i) => `${i.label}: ${levelText[i.level]}`).join(', ');
  return (
    <div role="img" aria-label={summary} className="flex items-center gap-[3px]">
      {items.map((i) => {
        const itemTitle = `${i.label} — ${i.reason ?? levelText[i.level]}`;
        return <span key={i.id} title={itemTitle} className={cn('h-3 w-1.5 rounded-[1px]', LEVEL_CLS[i.level].bar)} />;
      })}
    </div>
  );
}
