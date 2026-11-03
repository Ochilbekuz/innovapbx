import { useState } from 'react';
import { Plus, X } from 'lucide-react';
import { Button } from '@/ui/Button';
import { Field, Input } from '@/ui/Field';
import { Badge } from '@/ui/Status';

type Props = {
  items: string[];
  onChange: (items: string[]) => void;
  label: string;
  hint?: string;
  emptyLabel?: string;
  placeholder?: string;
  addLabel: string;
  removeAriaLabel: (value: string) => string;
  disabled?: boolean;
  error?: string;
  mono?: boolean;
  /** Qiymat chipga qo'shilishdan oldin shuni qaytarsa — rad etiladi (masalan noto'g'ri formatdagi email). */
  normalize?: (value: string) => string | null;
};

/**
 * Qayta foydalaniladigan "chip" roʻyxat maydoni — Enter/tugma bilan qoʻshish, belgi (x) bilan olib tashlash
 * (CallbackWidgetPage: allowed_origins; MissedCallsPage: telegram chat_id/email). `AlertsPage`dagi
 * chat-id roʻyxatining umumlashtirilgan versiyasi — ub-mode dryer: endi 3 joyda qaytarilmaydi.
 */
export function ChipListField({
  items, onChange, label, hint, emptyLabel, placeholder, addLabel, removeAriaLabel, disabled, error, mono = true, normalize,
}: Props) {
  const [draft, setDraft] = useState('');

  const add = () => {
    const raw = draft.trim();
    if (!raw) return;
    const v = normalize ? normalize(raw) : raw;
    if (!v || items.includes(v)) return;
    onChange([...items, v]);
    setDraft('');
  };
  const remove = (v: string) => onChange(items.filter((x) => x !== v));

  return (
    <div>
      <p className="mb-1 text-sm font-medium text-fg">{label}</p>
      {hint && <p className="mb-2 text-xs text-muted">{hint}</p>}
      {items.length === 0 ? (
        emptyLabel ? <p className="mb-2 text-sm text-muted">{emptyLabel}</p> : null
      ) : (
        <ul className="mb-2 flex flex-wrap gap-2">
          {items.map((v) => (
            <li key={v}>
              <Badge mono={mono} className="h-7 pr-1">
                {v}
                {!disabled && (
                  <button type="button" aria-label={removeAriaLabel(v)} className="ml-1 rounded-sm p-0.5 hover:bg-surface-2" onClick={() => remove(v)}>
                    <X aria-hidden className="size-3" />
                  </button>
                )}
              </Badge>
            </li>
          ))}
        </ul>
      )}
      {!disabled && (
        <div className="flex items-end gap-2">
          <Field label="" className="flex-1" error={error}>
            {(a) => (
              <Input
                {...a} mono={mono} placeholder={placeholder} value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add(); } }}
              />
            )}
          </Field>
          <Button variant="secondary" icon={<Plus />} onClick={add}>{addLabel}</Button>
        </div>
      )}
    </div>
  );
}
