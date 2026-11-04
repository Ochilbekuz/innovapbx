import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import * as T from '@radix-ui/react-toast';
import { CircleCheck, CircleX, Info, RotateCcw, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';

export type ToastKind = 'success' | 'error' | 'info' | 'not-applied';

export type ToastInput = {
  kind: ToastKind;
  title: string;
  description?: ReactNode;
  action?: { label: string; altText: string; onClick: () => void };
};

export type Item = ToastInput & { id: number };

const STYLE: Record<ToastKind, { icon: ReactNode; bar: string; iconCls: string }> = {
  success: { icon: <CircleCheck />, bar: 'bg-success', iconCls: 'text-success' },
  error: { icon: <CircleX />, bar: 'bg-danger', iconCls: 'text-danger' },
  info: { icon: <Info />, bar: 'bg-info', iconCls: 'text-info' },
  // «PBX'ga qo'llanmadi»: baza saqlandi, dialplan tekshiruvdan o'tmadi va oldingi reviziyaga qaytarildi.
  'not-applied': { icon: <RotateCcw />, bar: 'bg-danger', iconCls: 'text-danger' },
};

/** Hammasi o'zi yopiladi (foydalanuvchi talabi, 2026-11-04); xato/«qo'llanmadi» o'qish uchun uzunroq turadi.
 * Sichqoncha ustida yoki fokusda bo'lsa Radix taymerni to'xtatib turadi. */
export const DURATION: Record<ToastKind, number> = { success: 4000, info: 5000, error: 8000, 'not-applied': 12000 };

/** Bir xil (tur + sarlavha) xabar takrorlansa — ustma-ust qo'shilmaydi, eskisi yangisi bilan almashadi (taymer qaytadan). */
export function pushToast(xs: Item[], t: ToastInput, id: number): Item[] {
  const rest = xs.filter((x) => !(x.kind === t.kind && x.title === t.title));
  return [...rest.slice(-3), { ...t, id }];
}

const Ctx = createContext<(t: ToastInput) => void>(() => undefined);
export const useToast = () => useContext(Ctx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation('common');
  const [items, setItems] = useState<Item[]>([]);
  const push = useCallback((t: ToastInput) => setItems((xs) => pushToast(xs, t, Date.now() + Math.random())), []);
  const drop = (id: number) => setItems((xs) => xs.filter((x) => x.id !== id));
  const value = useMemo(() => push, [push]);
  return (
    <Ctx.Provider value={value}>
      <T.Provider swipeDirection="right" label={t('toast.region')}>
        {children}
        {items.map((t) => (
          <ToastCard key={t.id} item={t} onClose={() => drop(t.id)} />
        ))}
        <T.Viewport className="fixed bottom-4 right-4 z-toast flex w-[380px] max-w-[calc(100vw-2rem)] flex-col gap-2 outline-none" />
      </T.Provider>
    </Ctx.Provider>
  );
}

export function ToastCard({ item, onClose, static: isStatic }: { item: ToastInput; onClose?: () => void; static?: boolean }) {
  const { t } = useTranslation('common');
  const s = STYLE[item.kind];
  const body = (
    <>
      <span aria-hidden className={cn('absolute inset-y-0 left-0 w-[3px]', s.bar)} />
      <span aria-hidden className={cn('mt-0.5 shrink-0 [&_svg]:size-[18px]', s.iconCls)}>{s.icon}</span>
      <div className="min-w-0 flex-1">
        <Title isStatic={isStatic} className="text-base font-semibold text-fg">{item.title}</Title>
        {item.description && <Desc isStatic={isStatic} className="mt-0.5 text-sm text-muted">{item.description}</Desc>}
        {item.action && (
          <ActionBtn isStatic={isStatic} altText={item.action.altText} onClick={item.action.onClick}>
            {item.action.label}
          </ActionBtn>
        )}
      </div>
    </>
  );
  const cls = 'relative flex gap-3 overflow-hidden rounded-md border border-line bg-raised py-3 pl-4 pr-10 shadow-pop';
  if (isStatic) return <div className={cls} role="status">{body}</div>;
  return (
    <T.Root
      duration={DURATION[item.kind]}
      type={item.kind === 'success' || item.kind === 'info' ? 'background' : 'foreground'}
      onOpenChange={(o) => !o && onClose?.()}
      className={cn(cls, 'data-[state=open]:animate-pop-in data-[swipe=move]:translate-x-[var(--radix-toast-swipe-move-x)]')}
    >
      {body}
      <T.Close aria-label={t('toast.close')} className="absolute right-2 top-2 rounded-sm p-1 text-muted hover:bg-surface-2 hover:text-fg">
        <X aria-hidden className="size-4" />
      </T.Close>
    </T.Root>
  );
}

// Toast ichidagi qismlar: provider ichida Radix, /design sahifasidagi statik ko'rinishda oddiy element.
function Title({ isStatic, ...p }: { isStatic?: boolean; className: string; children: ReactNode }) {
  return isStatic ? <p {...p} /> : <T.Title {...p} />;
}
function Desc({ isStatic, ...p }: { isStatic?: boolean; className: string; children: ReactNode }) {
  return isStatic ? <div {...p} /> : <T.Description {...p} />;
}
function ActionBtn({ isStatic, altText, onClick, children }: { isStatic?: boolean; altText: string; onClick: () => void; children: ReactNode }) {
  const btn = (
    <button type="button" onClick={onClick} className="mt-2 text-sm font-semibold text-accent underline-offset-2 hover:underline">
      {children}
    </button>
  );
  return isStatic ? btn : <T.Action asChild altText={altText}>{btn}</T.Action>;
}
