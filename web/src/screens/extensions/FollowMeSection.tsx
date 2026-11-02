import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowDown, ArrowUp, Plus, Waypoints, X } from 'lucide-react';
import { useFollowMe, useUpdateFollowMe } from '@/api/queries';
import { apiErrorMessage, isApiError } from '@/api/errors';
import {
  FOLLOW_ME_MAX_NUMBERS, FOLLOW_ME_RING_MAX, FOLLOW_ME_RING_MIN,
  type FollowMe, type FollowMeInfo, type FollowMeStrategy, type FollowMeTarget,
} from '@/api/types';
import { cleanNumber, isExternalNumber, isRingSecondsValid, moveItem, numberProblem, sameFollowMe, type NumberProblem } from '@/domain/followMe';
import { cn } from '@/lib/cn';
import { Button } from '@/ui/Button';
import { Field, Input, Select } from '@/ui/Field';
import { Badge } from '@/ui/Status';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

const STRATEGIES: FollowMeStrategy[] = ['ring_all', 'sequential'];

type SectionProps = {
  /** Ichki raqam id (admin) yoki `null` — operatorning o'z raqami. */
  target: FollowMeTarget;
  readOnly?: boolean;
  /** Operator kabineti: «ichki raqam ham» va vaqt yashirin (mavjud qiymat saqlanadi). */
  compact?: boolean;
  /** Saqlangach yangi `updated_at` — tahrir oynasi keyingi saqlashda `stale` olmasin. */
  onSaved?: (updatedAt: string) => void;
  className?: string;
};

/** M5b §1 — Follow Me: ichki raqam javob bermasa ro'yxatdagi raqamlarga jiringlash. Admin tahriri va `/me` uchun bitta blok. */
export function FollowMeSection({ target, className, ...rest }: SectionProps) {
  const { t } = useTranslation('followme');
  const { data, isLoading, isError, refetch } = useFollowMe(target);

  return (
    <section className={cn('flex flex-col gap-4', className)} data-testid="follow-me">
      <p className={cn('flex items-center gap-1.5 text-fg', rest.compact ? 'font-display text-base' : 'text-sm font-medium')}><Waypoints aria-hidden className="size-4 text-brand" /> {t('title')}</p>
      {isLoading && <div className="skeleton h-24" />}
      {!isLoading && (isError || !data) && (
        <div className="flex items-center gap-3 text-sm text-muted">
          <span>{t('loadFailed')}</span>
          <Button size="sm" variant="secondary" onClick={() => void refetch()}>{t('retry')}</Button>
        </div>
      )}
      {data && <FollowMeForm key={data.updated_at} info={data} target={target} onReload={() => void refetch()} {...rest} />}
    </section>
  );
}

type SaveError = { stale: boolean; index: number | null; message?: string };

/** Saqlash xatosini joyiga ajratadi: `stale` — alohida blok, `numbers.{i}` — qator ostida, qolgani — tugma ustida. */
export function describeSaveError(error: unknown): SaveError {
  if (!error) return { stale: false, index: null };
  const field = isApiError(error) ? error.field ?? '' : '';
  const index = field.startsWith('numbers.') ? Number(field.slice('numbers.'.length)) : null;
  return { stale: isApiError(error) && error.code === 'stale', index, message: apiErrorMessage(error) };
}

function FollowMeForm({ info, target, readOnly, compact, onSaved, onReload }: Omit<SectionProps, 'className'> & { info: FollowMeInfo; onReload: () => void }) {
  const { t } = useTranslation('followme');
  const toast = useToast();
  const saveM = useUpdateFollowMe(target);
  const [fm, setFm] = useState<FollowMe>(info.follow_me);
  const patch = (p: Partial<FollowMe>) => setFm((cur) => ({ ...cur, ...p }));
  const err = describeSaveError(saveM.error);
  const emptyEnabled = fm.enabled && fm.numbers.length === 0;
  const canSave = !readOnly && !sameFollowMe(fm, info.follow_me) && isRingSecondsValid(fm.ring_seconds) && !emptyEnabled;

  const save = () => saveM.mutate({ ...fm, updated_at: info.updated_at }, {
    onSuccess: (res) => { toast({ kind: 'success', title: t('saved') }); onSaved?.(res.updated_at); },
  });

  return (
    <div className="flex flex-col gap-4">
      <Toggle
        checked={fm.enabled} onCheckedChange={(enabled) => patch({ enabled })} disabled={readOnly}
        label={t('enabledLabel')} description={t('lead', { number: info.number })}
      />
      <NumbersEditor
        own={info.number} numbers={fm.numbers} readOnly={readOnly} onChange={(numbers) => patch({ numbers })}
        errorIndex={err.index} errorMessage={err.index !== null ? err.message : undefined}
      />
      {emptyEnabled && <p className="text-sm text-warning">{t('follow_me_empty', { ns: 'errors' })}</p>}
      <RingSettings fm={fm} patch={patch} readOnly={readOnly} compact={compact} />
      <Toggle checked={fm.confirm} onCheckedChange={(v) => patch({ confirm: v })} disabled={readOnly} label={t('confirm')} description={t('confirmDesc')} />
      <SaveFooter err={err} readOnly={readOnly} canSave={canSave} pending={saveM.isPending} onSave={save} onReload={onReload} />
    </div>
  );
}

/** Strategiya, jiringlash vaqti va «ichki raqam ham». `compact` (kabinet) — faqat strategiya. */
function RingSettings({ fm, patch, readOnly, compact }: { fm: FollowMe; patch: (p: Partial<FollowMe>) => void; readOnly?: boolean; compact?: boolean }) {
  const { t } = useTranslation('followme');
  const ringHint = t(`ringSecondsHint.${fm.strategy}`, { min: FOLLOW_ME_RING_MIN, max: FOLLOW_ME_RING_MAX });
  return (
    <>
      <div className={cn('grid gap-4', !compact && 'sm:grid-cols-2')}>
        <Field label={t('strategyLabel')} hint={t(`strategyHint.${fm.strategy}`)}>
          {(a) => (
            <Select
              {...a} data-testid="fm-strategy" disabled={readOnly} value={fm.strategy}
              onValueChange={(v) => patch({ strategy: v as FollowMeStrategy })}
              options={STRATEGIES.map((s) => ({ value: s, label: t(`strategy.${s}`) }))}
            />
          )}
        </Field>
        {!compact && (
          <Field label={t('ringSecondsLabel')} hint={ringHint} error={isRingSecondsValid(fm.ring_seconds) ? undefined : ringHint}>
            {(a) => (
              <Input
                {...a} mono type="number" inputMode="numeric" min={FOLLOW_ME_RING_MIN} max={FOLLOW_ME_RING_MAX} disabled={readOnly}
                data-testid="fm-ring-seconds" value={Number.isNaN(fm.ring_seconds) ? '' : String(fm.ring_seconds)}
                onChange={(e) => patch({ ring_seconds: e.target.value === '' ? Number.NaN : Number(e.target.value) })}
              />
            )}
          </Field>
        )}
      </div>
      {!compact && fm.strategy === 'ring_all' && (
        <Toggle
          checked={fm.include_extension} onCheckedChange={(v) => patch({ include_extension: v })} disabled={readOnly}
          label={t('includeExtension')} description={t('includeExtensionDesc')}
        />
      )}
    </>
  );
}

function SaveFooter({ err, readOnly, canSave, pending, onSave, onReload }: {
  err: SaveError; readOnly?: boolean; canSave: boolean; pending: boolean; onSave: () => void; onReload: () => void;
}) {
  const { t } = useTranslation('followme');
  return (
    <>
      {err.stale && (
        <div className="flex flex-col gap-2 rounded-md border border-danger/30 bg-danger-soft px-3 py-2.5 text-sm text-on-danger-soft">
          <p>{t('stale')}</p>
          <Button size="sm" variant="secondary" className="self-start" onClick={onReload}>{t('reload')}</Button>
        </div>
      )}
      {err.message && !err.stale && err.index === null && <p className="text-sm text-danger" role="alert">{err.message}</p>}
      {!readOnly && (
        <Button size="sm" variant="primary" className="self-start" data-testid="fm-save" disabled={!canSave} loading={pending} onClick={onSave}>
          {t('save')}
        </Button>
      )}
    </>
  );
}

const PROBLEM_KEY: Record<NumberProblem, string> = { invalid: 'invalidNumber', self: 'selfNumber', duplicate: 'duplicate', full: 'full' };

function NumbersEditor({ own, numbers, readOnly, onChange, errorIndex, errorMessage }: {
  own: string;
  numbers: string[];
  readOnly?: boolean;
  onChange: (numbers: string[]) => void;
  errorIndex: number | null;
  errorMessage?: string;
}) {
  const { t } = useTranslation('followme');
  return (
    <div className="flex flex-col gap-2">
      <div>
        <p className="text-sm font-medium text-fg">{t('numbersLabel')}</p>
        <p className="text-xs text-muted">{t('numbersHint', { max: FOLLOW_ME_MAX_NUMBERS })}</p>
      </div>
      {numbers.length === 0 ? (
        <p className="rounded-md border border-dashed border-line px-3 py-2.5 text-sm text-muted">{t('numbersEmpty')}</p>
      ) : (
        <ol className="flex flex-col gap-1.5" data-testid="fm-numbers">
          {numbers.map((n, i) => (
            <NumberRow key={n} number={n} index={i} numbers={numbers} readOnly={readOnly} invalid={errorIndex === i} onChange={onChange} />
          ))}
        </ol>
      )}
      {errorMessage && <p className="text-sm text-danger" role="alert">{errorMessage}</p>}
      {!readOnly && numbers.length < FOLLOW_ME_MAX_NUMBERS && <AddNumber own={own} numbers={numbers} onChange={onChange} />}
    </div>
  );
}

function NumberRow({ number, index, numbers, readOnly, invalid, onChange }: {
  number: string; index: number; numbers: string[]; readOnly?: boolean; invalid: boolean; onChange: (numbers: string[]) => void;
}) {
  const { t } = useTranslation('followme');
  const external = isExternalNumber(number);
  return (
    <li
      data-testid={`fm-number-${index}`}
      className={cn('flex items-center gap-2 rounded-md border px-3 py-1.5', invalid ? 'border-danger/50 bg-danger-soft' : 'border-line bg-surface-2/60')}
    >
      <span className="num w-4 text-xs text-muted">{index + 1}</span>
      <span className="num flex-1 text-sm font-medium text-fg">{number}</span>
      <Badge tone={external ? 'info' : 'neutral'}>{external ? t('external') : t('internal')}</Badge>
      {!readOnly && (
        <span className="flex items-center">
          <Button size="sm" variant="ghost" iconOnly icon={<ArrowUp />} aria-label={t('moveUp', { number })} disabled={index === 0} onClick={() => onChange(moveItem(numbers, index, -1))} />
          <Button size="sm" variant="ghost" iconOnly icon={<ArrowDown />} aria-label={t('moveDown', { number })} disabled={index === numbers.length - 1} onClick={() => onChange(moveItem(numbers, index, 1))} />
          <Button size="sm" variant="danger-ghost" iconOnly icon={<X />} aria-label={t('remove', { number })} onClick={() => onChange(numbers.filter((_, j) => j !== index))} />
        </span>
      )}
    </li>
  );
}

function AddNumber({ own, numbers, onChange }: { own: string; numbers: string[]; onChange: (numbers: string[]) => void }) {
  const { t } = useTranslation('followme');
  const [draft, setDraft] = useState('');
  const [problem, setProblem] = useState<NumberProblem | null>(null);

  const add = () => {
    const number = cleanNumber(draft);
    const found = numberProblem(number, own, numbers);
    setProblem(found);
    if (found) return;
    onChange([...numbers, number]);
    setDraft('');
  };

  return (
    <>
      <div className="flex items-center gap-2">
        <Input
          mono inputMode="tel" aria-label={t('add')} placeholder={t('addPlaceholder')} value={draft} data-testid="fm-add-input"
          aria-invalid={problem ? true : undefined}
          onChange={(e) => { setDraft(e.target.value); setProblem(null); }}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add(); } }}
        />
        <Button variant="secondary" icon={<Plus />} data-testid="fm-add" disabled={draft.trim() === ''} onClick={add}>{t('add')}</Button>
      </div>
      {problem && <p className="text-sm text-danger" role="alert">{t(PROBLEM_KEY[problem], { max: FOLLOW_ME_MAX_NUMBERS })}</p>}
    </>
  );
}
