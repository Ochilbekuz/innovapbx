import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { LoaderCircle } from 'lucide-react';
import { cn } from '@/lib/cn';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'danger-ghost';
export type ButtonSize = 'sm' | 'md' | 'lg';

const VARIANT: Record<ButtonVariant, string> = {
  primary:
    'bg-accent text-on-accent shadow-card hover:bg-accent-hover active:translate-y-px',
  secondary:
    'bg-surface text-fg border border-line-strong shadow-card hover:bg-surface-2 hover:border-input active:translate-y-px',
  ghost: 'text-fg hover:bg-surface-2 active:bg-line/60',
  danger: 'bg-danger text-on-danger shadow-card hover:bg-danger-hover active:translate-y-px',
  'danger-ghost': 'text-danger hover:bg-danger-soft',
};

const SIZE: Record<ButtonSize, string> = {
  sm: 'h-ctl-sm px-2.5 gap-1.5 text-sm [&_svg]:size-3.5',
  md: 'h-ctl-md px-3 gap-2 text-base [&_svg]:size-4',
  lg: 'h-ctl-lg px-4 gap-2 text-md [&_svg]:size-[18px]',
};
const ICON_SIZE: Record<ButtonSize, string> = {
  sm: 'size-ctl-sm [&_svg]:size-3.5',
  md: 'size-ctl-md [&_svg]:size-4',
  lg: 'size-ctl-lg [&_svg]:size-[18px]',
};

type Common = Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
};
/** Faqat ikonli tugma — aria-label majburiy (tip darajasida). */
export type ButtonProps =
  | (Common & { icon?: ReactNode; children: ReactNode; iconOnly?: false })
  | (Common & { icon: ReactNode; iconOnly: true; 'aria-label': string; children?: never });

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'secondary', size = 'md', loading = false, icon, iconOnly, className, disabled, children, type = 'button', ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      data-loading={loading || undefined}
      className={cn(
        'relative inline-flex shrink-0 select-none items-center justify-center whitespace-nowrap rounded-md font-medium',
        'transition-[background-color,border-color,color,transform,box-shadow] duration-fast ease-out',
        'disabled:pointer-events-none disabled:opacity-50 data-[loading]:opacity-100',
        VARIANT[variant],
        iconOnly ? ICON_SIZE[size] : SIZE[size],
        className,
      )}
      {...rest}
    >
      {loading ? <LoaderCircle aria-hidden className="animate-spin" /> : icon}
      {children !== undefined && <span>{children}</span>}
    </button>
  );
});

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="num inline-flex h-5 min-w-5 items-center justify-center rounded-sm border border-line-strong bg-surface px-1 text-xs text-muted shadow-[inset_0_-1px_0_rgb(var(--c-border))]">
      {children}
    </kbd>
  );
}
