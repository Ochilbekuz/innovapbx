import type { ReactNode } from 'react';
import * as D from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';
import { Button } from './Button';

type Base = {
  open?: boolean;
  onOpenChange?: (v: boolean) => void;
  trigger?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  /** Saqlanmagan o'zgarish bor — yopishga urinilganda chaqiriladi; false qaytarsa yopilmaydi. */
  onAttemptClose?: () => boolean;
};

/** Overlay o'z panelining qatlamida turadi — aks holda drawer (z-drawer) ustini yopib, bosishlarni o'g'irlaydi. */
const overlayBase = 'fixed inset-0 bg-scrim/50 backdrop-blur-[2px] data-[state=open]:animate-fade-in';
const overlay = { modal: `${overlayBase} z-modal`, drawer: `${overlayBase} z-drawer` } as const;

function guard(onAttemptClose?: () => boolean) {
  return (e: Event) => {
    if (onAttemptClose && !onAttemptClose()) e.preventDefault();
  };
}

function Header({ title, description }: Pick<Base, 'title' | 'description'>) {
  const { t } = useTranslation('common');
  return (
    <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
      <div className="min-w-0">
        <D.Title className="font-display text-lg text-fg">{title}</D.Title>
        {description ? (
          <D.Description className="mt-0.5 text-sm text-muted">{description}</D.Description>
        ) : (
          <D.Description className="sr-only">{title}</D.Description>
        )}
      </div>
      <D.Close asChild>
        <Button variant="ghost" size="sm" iconOnly icon={<X />} aria-label={t('dialog.close')} className="-mr-2 -mt-1" />
      </D.Close>
    </div>
  );
}

/** Markaziy modal. Fokus ichida qamaladi, Esc yopadi, fokus trigger'ga qaytadi. */
export function Modal({ size = 'md', open, onOpenChange, trigger, title, description, children, footer, onAttemptClose }: Base & { size?: 'sm' | 'md' }) {
  const g = guard(onAttemptClose);
  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      {trigger && <D.Trigger asChild>{trigger}</D.Trigger>}
      <D.Portal>
        <D.Overlay className={overlay.modal} />
        <D.Content
          onEscapeKeyDown={g}
          onPointerDownOutside={g}
          className={cn(
            'fixed left-1/2 top-[12vh] z-modal w-[calc(100vw-2rem)] -translate-x-1/2 rounded-lg border border-line bg-raised shadow-modal',
            'data-[state=open]:animate-pop-in focus-visible:outline-none',
            size === 'sm' ? 'max-w-modal-sm' : 'max-w-modal-md',
          )}
        >
          <Header title={title} description={description} />
          {children && <div className="px-5 py-4">{children}</div>}
          {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-line bg-surface-2/60 px-5 py-3">{footer}</div>}
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}

/** O'ng tomondan chiqadigan panel — jadval qatorini tahrirlash uchun (sahifani tark etmasdan). */
export function Drawer({ open, onOpenChange, trigger, title, description, children, footer, onAttemptClose }: Base) {
  const g = guard(onAttemptClose);
  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      {trigger && <D.Trigger asChild>{trigger}</D.Trigger>}
      <D.Portal>
        <D.Overlay className={overlay.drawer} />
        <D.Content
          onEscapeKeyDown={g}
          onPointerDownOutside={g}
          className="fixed inset-y-0 right-0 z-drawer flex w-full max-w-drawer flex-col border-l border-line bg-raised shadow-modal data-[state=open]:animate-slide-in-right focus-visible:outline-none"
        >
          <Header title={title} description={description} />
          <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
          {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-line bg-surface-2/60 px-5 py-3">{footer}</div>}
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}

export const DialogClose = D.Close;
