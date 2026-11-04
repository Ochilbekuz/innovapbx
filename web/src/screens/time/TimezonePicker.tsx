// Qidiriladigan vaqt zonasi tanlagich: har zona yonida UTC siljishi, O'zbekiston/qo'shnilar boshida.
// Ro'yxat va qidiruv — sof `domain/systemTime.ts::searchTimezones`.
import * as Popover from '@radix-ui/react-popover';
import { Check, ChevronDown, Search } from 'lucide-react';
import { useMemo, useState } from 'react';
import { listTimezones, searchTimezones, utcOffsetLabel } from '@/domain/systemTime';
import { cn } from '@/lib/cn';
import { controlBase, type FieldA11y, Input } from '@/ui/Field';

type Props = Partial<FieldA11y> & {
  value: string;
  onChange: (zone: string) => void;
  disabled?: boolean;
  searchPlaceholder: string;
  noMatch: string;
};

export function TimezonePicker({ value, onChange, disabled, searchPlaceholder, noMatch, ...a11y }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const zones = useMemo(() => listTimezones(), []);
  const options = useMemo(() => (open ? searchTimezones(zones, query, new Date()) : []), [zones, query, open]);

  const pick = (zone: string) => {
    onChange(zone);
    setOpen(false);
    setQuery('');
  };

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild disabled={disabled}>
        <button
          type="button"
          {...a11y}
          aria-haspopup="listbox"
          className={cn(controlBase, 'flex h-ctl-lg items-center justify-between gap-2 px-2.5 text-left text-base')}
        >
          <span className="truncate">{value}</span>
          <span className="ml-auto flex shrink-0 items-center gap-2">
            <span className="num text-sm text-muted">{value ? utcOffsetLabel(value, new Date()) : ''}</span>
            <ChevronDown aria-hidden className="size-4 text-muted" />
          </span>
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="start"
          sideOffset={6}
          className="z-popover flex w-[min(420px,calc(100vw-2rem))] flex-col overflow-hidden rounded-lg border border-line bg-raised shadow-pop data-[state=open]:animate-pop-in"
        >
          <div className="border-b border-line p-2">
            <Input
              autoFocus
              aria-label={searchPlaceholder}
              placeholder={searchPlaceholder}
              leading={<Search aria-hidden className="size-4" />}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && options[0]) pick(options[0].zone);
              }}
            />
          </div>
          <ul role="listbox" aria-label={searchPlaceholder} className="max-h-72 overflow-y-auto p-1">
            {options.length === 0 && <li className="px-2 py-3 text-center text-sm text-muted">{noMatch}</li>}
            {options.map((o) => (
              <li key={o.zone} role="option" aria-selected={o.zone === value}>
                <button
                  type="button"
                  onClick={() => pick(o.zone)}
                  className="flex w-full items-center gap-2 rounded-sm py-1.5 pl-7 pr-2 text-left text-base text-fg outline-none hover:bg-surface-2 focus-visible:bg-surface-2"
                >
                  <span className="relative flex-1 truncate">
                    {o.zone === value && <Check aria-hidden className="absolute -left-5 top-1 size-3.5 text-accent" />}
                    {o.zone.replace(/_/g, ' ')}
                  </span>
                  <span className="num shrink-0 text-xs text-muted">{o.offset}</span>
                </button>
              </li>
            ))}
          </ul>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
