import { useId, type ReactNode } from 'react';
import * as Switch from '@radix-ui/react-switch';
import * as RCheckbox from '@radix-ui/react-checkbox';
import { Check, Minus } from 'lucide-react';
import { cn } from '@/lib/cn';

type ToggleProps = {
  checked?: boolean;
  defaultChecked?: boolean;
  onCheckedChange?: (v: boolean) => void;
  label: ReactNode;
  description?: ReactNode;
  disabled?: boolean;
  size?: 'sm' | 'md';
  /** Yorliq vizual yashirin (jadval qatorida) — screen reader uchun baribir o'qiladi. */
  hideLabel?: boolean;
};

/** Yoqish/o'chirish. Radix Switch: role=switch, aria-checked, Space/Enter. */
export function Toggle({ label, description, hideLabel, size = 'md', className, ...rest }: ToggleProps & { className?: string }) {
  const id = useId();
  const descId = description ? `${id}-d` : undefined;
  const track = size === 'sm' ? 'h-4 w-7' : 'h-5 w-9';
  const thumb = size === 'sm' ? 'size-3 data-[state=checked]:translate-x-3' : 'size-4 data-[state=checked]:translate-x-4';
  return (
    <div className={cn('flex items-start gap-3', className)}>
      <Switch.Root
        id={id}
        aria-describedby={descId}
        className={cn(
          'peer relative mt-0.5 inline-flex shrink-0 cursor-pointer items-center rounded-pill border border-transparent p-px',
          'bg-input transition-colors duration-base ease-out data-[state=checked]:bg-accent',
          'disabled:cursor-not-allowed disabled:opacity-45',
          track,
        )}
        {...rest}
      >
        <Switch.Thumb
          className={cn(
            'block rounded-pill bg-surface shadow-card transition-transform duration-base ease-out',
            thumb,
          )}
        />
      </Switch.Root>
      <div className={cn('flex flex-col', hideLabel && 'sr-only')}>
        <label htmlFor={id} className="cursor-pointer text-base font-medium text-fg peer-disabled:cursor-not-allowed peer-disabled:text-disabled">
          {label}
        </label>
        {description && <span id={descId} className="text-sm text-muted">{description}</span>}
      </div>
    </div>
  );
}

type CheckboxProps = {
  checked: boolean | 'indeterminate';
  onCheckedChange: (v: boolean) => void;
  'aria-label': string;
  disabled?: boolean;
};

export function Checkbox({ checked, onCheckedChange, ...rest }: CheckboxProps) {
  return (
    <RCheckbox.Root
      checked={checked}
      onCheckedChange={(v) => onCheckedChange(v === true)}
      className={cn(
        'inline-flex size-4 shrink-0 items-center justify-center rounded-xs border border-input bg-surface text-on-accent',
        'transition-colors duration-fast data-[state=checked]:border-accent data-[state=checked]:bg-accent',
        'data-[state=indeterminate]:border-accent data-[state=indeterminate]:bg-accent disabled:opacity-45',
      )}
      {...rest}
    >
      <RCheckbox.Indicator>
        {checked === 'indeterminate' ? <Minus aria-hidden className="size-3" strokeWidth={3} /> : <Check aria-hidden className="size-3" strokeWidth={3} />}
      </RCheckbox.Indicator>
    </RCheckbox.Root>
  );
}
