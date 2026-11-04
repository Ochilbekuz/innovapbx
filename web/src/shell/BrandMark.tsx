import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';

/** Innova belgisi + so'z belgisi. `wordClassName` — faqat so'zga (masalan, yig'ilgan menyuda yashirish uchun). */
export function BrandMark({ compact, onDark = true, wordClassName }: { compact?: boolean; onDark?: boolean; wordClassName?: string }) {
  const { t } = useTranslation();
  return (
    <span className="inline-flex items-center gap-2.5">
      <img src="/brand/innova-belgi-64.png" alt="" width={28} height={28} className="size-7 shrink-0" />
      {!compact && (
        <span className={cn('whitespace-nowrap font-display text-[19px] font-semibold leading-none tracking-[-0.01em]', onDark ? 'text-sidebar-text' : 'text-fg', wordClassName)}>
          {t('brandWord')} <span className={onDark ? 'text-brand-fire' : 'text-brand'}>{t('brandSuffix')}</span>
        </span>
      )}
    </span>
  );
}
