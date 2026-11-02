import { useTranslation } from 'react-i18next';
import { useNumbersFree } from '@/api/queries';
import { Field, Input } from '@/ui/Field';

/** Raqam maydoni — boʻsh boʻlsa `/numbers/free`dan boʻsh raqamlarni taklif qiladi, bosib tanlanadi (IVR/navbat/guruh/ish vaqti — bitta hovuz). */
export function NumberField({
  value, onChange, error, required, label, hint,
}: { value: string; onChange: (v: string) => void; error?: string; required?: boolean; label?: string; hint?: string }) {
  const { t } = useTranslation('common');
  const resolvedLabel = label ?? t('numberField.label');
  const empty = value.trim() === '';
  const { data } = useNumbersFree({ limit: 5 }, empty);
  const free = data?.items ?? [];
  return (
    <Field label={resolvedLabel} required={required} error={error} hint={!error ? hint : undefined}>
      {(a) => (
        <div className="flex flex-col gap-1.5">
          <Input {...a} mono value={value} onChange={(e) => onChange(e.target.value)} placeholder={t('numberField.placeholder')} />
          {empty && free.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-muted">{t('numberField.free')}</span>
              {free.map((n) => (
                <button
                  key={n} type="button" onClick={() => onChange(n)}
                  className="num rounded-sm border border-line px-1.5 py-0.5 text-xs text-muted transition-colors duration-fast hover:border-brand hover:text-fg"
                >
                  {n}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </Field>
  );
}
