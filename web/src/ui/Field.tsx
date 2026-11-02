import { forwardRef, useId, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes } from 'react';
import * as RSelect from '@radix-ui/react-select';
import { Check, ChevronDown, CircleAlert } from 'lucide-react';
import { cn } from '@/lib/cn';

export type FieldA11y = { id: string; 'aria-describedby'?: string; 'aria-invalid'?: true; 'aria-required'?: true };

type FieldProps = {
  label: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  required?: boolean;
  /** Yorliq yonida qo'shimcha (masalan «ixtiyoriy» yoki havola). */
  aside?: ReactNode;
  className?: string;
  children: (a11y: FieldA11y) => ReactNode;
};

/** Yorliq + boshqaruv + izoh/xato. Id va aria-* larni o'zi bog'laydi. */
export function Field({ label, hint, error, required, aside, className, children }: FieldProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errId = error ? `${id}-err` : undefined;
  const describedBy = [errId, hintId].filter(Boolean).join(' ') || undefined;
  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      <div className="flex items-baseline justify-between gap-2">
        <label htmlFor={id} className="text-sm font-medium text-fg">
          {label}
          {required && <span aria-hidden className="ml-0.5 text-danger">*</span>}
        </label>
        {aside && <span className="text-xs text-muted">{aside}</span>}
      </div>
      {children({ id, 'aria-describedby': describedBy, 'aria-invalid': error ? true : undefined, 'aria-required': required ? true : undefined })}
      {error ? (
        <p id={errId} className="flex items-start gap-1.5 text-sm text-danger">
          <CircleAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="text-sm text-muted">{hint}</p>
      ) : null}
    </div>
  );
}

export const controlBase =
  'w-full rounded-md border border-input bg-surface text-fg placeholder:text-muted shadow-inset ' +
  'transition-[border-color,box-shadow] duration-fast ease-out ' +
  'hover:border-fg/60 focus-visible:outline-none focus-visible:border-focus-ring focus-visible:ring-2 focus-visible:ring-focus-ring/30 ' +
  'aria-[invalid=true]:border-danger aria-[invalid=true]:focus-visible:ring-danger/25 ' +
  'disabled:cursor-not-allowed disabled:bg-surface-2 disabled:text-disabled disabled:border-line-strong [&:is(input,textarea):read-only]:bg-surface-2';

const CONTROL_SIZE = { sm: 'h-ctl-sm text-sm', md: 'h-ctl-md text-base', lg: 'h-ctl-lg text-md' } as const;

type InputProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'size' | 'prefix'> & {
  size?: keyof typeof CONTROL_SIZE;
  mono?: boolean;
  leading?: ReactNode;
  trailing?: ReactNode;
};

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { size = 'md', mono, leading, trailing, className, ...rest },
  ref,
) {
  return (
    <div className="relative flex items-center">
      {leading && <span className="pointer-events-none absolute left-2.5 flex text-muted [&_svg]:size-4">{leading}</span>}
      <input
        ref={ref}
        className={cn(controlBase, CONTROL_SIZE[size], 'px-2.5', mono && 'num tracking-tight', leading && 'pl-8', trailing && 'pr-9', className)}
        {...rest}
      />
      {trailing && <span className="absolute right-2 flex items-center text-muted [&_svg]:size-4">{trailing}</span>}
    </div>
  );
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea(
  { className, ...rest },
  ref,
) {
  return <textarea ref={ref} className={cn(controlBase, 'min-h-20 px-2.5 py-2 text-base', className)} {...rest} />;
});

export type SelectOption = { value: string; label: ReactNode; hint?: ReactNode; disabled?: boolean };

type SelectProps = Partial<FieldA11y> & {
  value?: string;
  defaultValue?: string;
  onValueChange?: (v: string) => void;
  options: SelectOption[];
  placeholder?: string;
  size?: keyof typeof CONTROL_SIZE;
  disabled?: boolean;
  className?: string;
};

export function Select({ options, placeholder, size = 'md', className, id, disabled, value, defaultValue, onValueChange, ...aria }: SelectProps) {
  return (
    <RSelect.Root value={value} defaultValue={defaultValue} onValueChange={onValueChange} disabled={disabled}>
      <RSelect.Trigger
        id={id}
        {...aria}
        className={cn(controlBase, CONTROL_SIZE[size], 'inline-flex items-center justify-between gap-2 px-2.5 text-left data-[placeholder]:text-muted', className)}
      >
        <RSelect.Value placeholder={placeholder} />
        <RSelect.Icon className="text-muted">
          <ChevronDown aria-hidden className="size-4" />
        </RSelect.Icon>
      </RSelect.Trigger>
      <RSelect.Portal>
        <RSelect.Content
          position="popper"
          sideOffset={4}
          className="z-popover max-h-[var(--radix-select-content-available-height)] min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-md border border-line bg-raised p-1 shadow-pop data-[state=open]:animate-pop-in"
        >
          <RSelect.Viewport>
            {options.map((o) => (
              <RSelect.Item
                key={o.value}
                value={o.value}
                disabled={o.disabled}
                className="relative flex cursor-default select-none items-center gap-2 rounded-sm py-1.5 pl-7 pr-2 text-base text-fg outline-none data-[disabled]:text-disabled data-[highlighted]:bg-surface-2"
              >
                <RSelect.ItemIndicator className="absolute left-2 text-accent">
                  <Check aria-hidden className="size-3.5" />
                </RSelect.ItemIndicator>
                <RSelect.ItemText>{o.label}</RSelect.ItemText>
                {o.hint && <span className="ml-auto pl-4 text-xs text-muted">{o.hint}</span>}
              </RSelect.Item>
            ))}
          </RSelect.Viewport>
        </RSelect.Content>
      </RSelect.Portal>
    </RSelect.Root>
  );
}

/** Kichik segmentli tanlagich (til, rejim, ko'rinish). role=radiogroup, strelkalar bilan. */
export function Segmented<T extends string>({
  value, onChange, options, label, size = 'sm',
}: { value: T; onChange: (v: T) => void; options: { value: T; label: ReactNode; title?: string }[]; label: string; size?: 'sm' | 'md' }) {
  const move = (dir: 1 | -1) => {
    const i = options.findIndex((o) => o.value === value);
    const next = options[(i + dir + options.length) % options.length];
    if (next) onChange(next.value);
  };
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="inline-flex rounded-md border border-line bg-surface-2 p-0.5"
      onKeyDown={(e) => {
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { e.preventDefault(); move(1); }
        if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
      }}
    >
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={on}
            title={o.title}
            tabIndex={on ? 0 : -1}
            onClick={() => onChange(o.value)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-sm font-medium transition-colors duration-fast [&_svg]:size-3.5',
              size === 'sm' ? 'h-6 px-2 text-xs' : 'h-7 px-2.5 text-sm',
              on ? 'bg-surface text-fg shadow-card' : 'text-muted hover:text-fg',
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
