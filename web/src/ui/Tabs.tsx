import type { ReactNode } from 'react';
import * as RTabs from '@radix-ui/react-tabs';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';

export type TabItem = { value: string; label: ReactNode; count?: number; invalid?: boolean; disabled?: boolean; content: ReactNode };

/**
 * Chiziqli tablar. Radix: role=tablist, strelkalar, Home/End. Xato bor tab — qizil nuqta + «xato bor» SR matni.
 * `value`/`onValueChange` berilsa — boshqariladigan (masalan boshqa joydan "Sozlash" tugmasi bilan tab almashtirish uchun).
 */
export function Tabs({
  items, defaultValue, value, onValueChange, label, className,
}: { items: TabItem[]; defaultValue?: string; value?: string; onValueChange?: (v: string) => void; label: string; className?: string }) {
  const { t } = useTranslation('common');
  return (
    <RTabs.Root
      value={value}
      defaultValue={value === undefined ? (defaultValue ?? items[0]?.value) : undefined}
      onValueChange={onValueChange}
      className={className}
    >
      <RTabs.List aria-label={label} className="flex gap-1 overflow-x-auto border-b border-line">
        {items.map((item) => (
          <RTabs.Trigger
            key={item.value}
            value={item.value}
            disabled={item.disabled}
            className={cn(
              'group relative -mb-px inline-flex h-9 items-center gap-2 whitespace-nowrap border-b-2 border-transparent px-3 text-base font-medium text-muted',
              'transition-colors duration-fast hover:text-fg data-[state=active]:border-brand data-[state=active]:text-fg',
              'disabled:cursor-not-allowed disabled:text-disabled',
            )}
          >
            {item.label}
            {item.count !== undefined && (
              <span className="num rounded-sm bg-surface-2 px-1.5 text-xs text-muted group-data-[state=active]:bg-accent-soft group-data-[state=active]:text-on-accent-soft">
                {item.count}
              </span>
            )}
            {item.invalid && (
              <>
                <span aria-hidden className="size-1.5 rounded-full bg-danger" />
                <span className="sr-only">{t('tabs.hasError')}</span>
              </>
            )}
          </RTabs.Trigger>
        ))}
      </RTabs.List>
      {items.map((item) => (
        <RTabs.Content key={item.value} value={item.value} className="pt-4 focus-visible:outline-offset-4">
          {item.content}
        </RTabs.Content>
      ))}
    </RTabs.Root>
  );
}
