import { useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Save, Trash2 } from 'lucide-react';
import type { CallDisposition } from '@/api/types';
import { cn } from '@/lib/cn';
import { Button } from '@/ui/Button';
import { Checkbox } from '@/ui/Toggle';
import { Field, Input, Select, type SelectOption } from '@/ui/Field';
import type { AdvancedSearchForm, CallRecordingFilter, CallTextMatchMode } from './advancedSearch';
import type { SearchTemplate } from './searchTemplates';

const DISPOSITIONS: CallDisposition[] = ['answered', 'no_answer', 'busy', 'failed'];

type TextModeFieldProps = {
  label: string;
  value: string;
  mode: CallTextMatchMode;
  not: boolean;
  modeOptions: SelectOption[];
  modeAriaLabel: string;
  notLabel: string;
  placeholder?: string;
  onChangeValue: (v: string) => void;
  onChangeMode: (v: CallTextMatchMode) => void;
  onChangeNot: (v: boolean) => void;
};

/** `src`/`dst`/`did` uchun umumiy ko'rinish — rejim tanlash + qiymat + «emas» (inkor) belgisi. */
function TextModeField({ label, value, mode, not, modeOptions, modeAriaLabel, notLabel, placeholder, onChangeValue, onChangeMode, onChangeNot }: TextModeFieldProps) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-fg">{label}</label>
      <div className="flex gap-1.5">
        <Select
          size="sm" className="w-[108px] shrink-0" value={mode} aria-label={modeAriaLabel}
          onValueChange={(v) => onChangeMode(v as CallTextMatchMode)} options={modeOptions}
        />
        <Input id={id} size="sm" value={value} placeholder={placeholder} onChange={(e) => onChangeValue(e.target.value)} />
      </div>
      <label className="inline-flex items-center gap-1.5 text-xs text-muted">
        <Checkbox checked={not} onCheckedChange={onChangeNot} aria-label={notLabel} />
        {notLabel}
      </label>
    </div>
  );
}

type DispositionChipsProps = {
  selected: CallDisposition[];
  onToggle: (d: CallDisposition) => void;
  labels: Record<CallDisposition, string>;
  groupLabel: string;
};

function DispositionChips({ selected, onToggle, labels, groupLabel }: DispositionChipsProps) {
  return (
    <div role="group" aria-label={groupLabel} className="flex flex-wrap gap-1.5">
      {DISPOSITIONS.map((d) => {
        const on = selected.includes(d);
        return (
          <button
            key={d} type="button" aria-pressed={on} onClick={() => onToggle(d)}
            className={cn(
              'h-7 rounded-full border px-2.5 text-xs font-medium transition-colors duration-fast',
              on ? 'border-brand/40 bg-accent-soft text-on-accent-soft' : 'border-line text-muted hover:border-fg/40 hover:text-fg',
            )}
          >
            {labels[d]}
          </button>
        );
      })}
    </div>
  );
}

export type AdvancedSearchPanelProps = {
  draft: AdvancedSearchForm;
  onChange: (patch: Partial<AdvancedSearchForm>) => void;
  onApply: () => void;
  onClear: () => void;
  templates: SearchTemplate[];
  onApplyTemplate: (id: string) => void;
  onSaveTemplate: (name: string) => void;
  onDeleteTemplate: (id: string) => void;
};

/** FreePBX «CDR Reports» uslubidagi kengaytirilgan qidiruv paneli — `CallsPage` ichida yig'ilib ochiladi. */
export function AdvancedSearchPanel({ draft, onChange, onApply, onClear, templates, onApplyTemplate, onSaveTemplate, onDeleteTemplate }: AdvancedSearchPanelProps) {
  const { t } = useTranslation('calls');
  const [templateId, setTemplateId] = useState('');
  const [templateName, setTemplateName] = useState('');

  const modeOptions: SelectOption[] = [
    { value: 'contains', label: t('advanced.mode.contains') },
    { value: 'begins', label: t('advanced.mode.begins') },
    { value: 'ends', label: t('advanced.mode.ends') },
    { value: 'exact', label: t('advanced.mode.exact') },
  ];
  const dispositionLabel: Record<CallDisposition, string> = {
    answered: t('disposition.answered'), no_answer: t('disposition.no_answer'), busy: t('disposition.busy'), failed: t('disposition.failed'),
  };
  const toggleDisposition = (d: CallDisposition) => {
    const next = draft.disposition.includes(d) ? draft.disposition.filter((x) => x !== d) : [...draft.disposition, d];
    onChange({ disposition: next });
  };

  const saveTemplate = () => {
    if (!templateName.trim()) return;
    onSaveTemplate(templateName);
    setTemplateName('');
  };
  const deleteTemplate = () => {
    if (!templateId) return;
    onDeleteTemplate(templateId);
    setTemplateId('');
  };

  return (
    <div className="mt-3 flex flex-col gap-4 rounded-lg border border-line bg-surface p-3 shadow-card" data-testid="advanced-search-panel">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <TextModeField
          label={t('advanced.src.label')} value={draft.src} mode={draft.srcMode} not={draft.srcNot}
          modeOptions={modeOptions} modeAriaLabel={t('advanced.modeAriaLabel', { field: t('advanced.src.label') })}
          notLabel={t('advanced.not')} placeholder={t('advanced.src.placeholder')}
          onChangeValue={(v) => onChange({ src: v })} onChangeMode={(v) => onChange({ srcMode: v })} onChangeNot={(v) => onChange({ srcNot: v })}
        />
        <TextModeField
          label={t('advanced.dst.label')} value={draft.dst} mode={draft.dstMode} not={draft.dstNot}
          modeOptions={modeOptions} modeAriaLabel={t('advanced.modeAriaLabel', { field: t('advanced.dst.label') })}
          notLabel={t('advanced.not')} placeholder={t('advanced.dst.placeholder')}
          onChangeValue={(v) => onChange({ dst: v })} onChangeMode={(v) => onChange({ dstMode: v })} onChangeNot={(v) => onChange({ dstNot: v })}
        />
        <TextModeField
          label={t('advanced.did.label')} value={draft.did} mode={draft.didMode} not={draft.didNot}
          modeOptions={modeOptions} modeAriaLabel={t('advanced.modeAriaLabel', { field: t('advanced.did.label') })}
          notLabel={t('advanced.not')} placeholder={t('advanced.did.placeholder')}
          onChangeValue={(v) => onChange({ did: v })} onChangeMode={(v) => onChange({ didMode: v })} onChangeNot={(v) => onChange({ didNot: v })}
        />

        <Field label={t('advanced.name.label')}>
          {(a) => <Input {...a} size="sm" value={draft.name} onChange={(e) => onChange({ name: e.target.value })} />}
        </Field>
        <Field label={t('advanced.ext.label')}>
          {(a) => <Input {...a} size="sm" mono value={draft.ext} onChange={(e) => onChange({ ext: e.target.value })} />}
        </Field>
        <Field label={t('advanced.trunk.label')}>
          {(a) => <Input {...a} size="sm" value={draft.trunk} onChange={(e) => onChange({ trunk: e.target.value })} />}
        </Field>
        <Field label={t('advanced.account.label')}>
          {(a) => <Input {...a} size="sm" value={draft.account} onChange={(e) => onChange({ account: e.target.value })} />}
        </Field>
        <Field label={t('advanced.recording.label')}>
          {({ id }) => (
            <Select
              id={id} size="sm" value={draft.recording} onValueChange={(v) => onChange({ recording: v as CallRecordingFilter })}
              options={[
                { value: 'any', label: t('advanced.recording.any') },
                { value: 'with', label: t('advanced.recording.with') },
                { value: 'without', label: t('advanced.recording.without') },
              ]}
            />
          )}
        </Field>
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-fg">{t('advanced.duration.label')}</span>
          <div className="flex items-center gap-1.5">
            <Input size="sm" inputMode="numeric" aria-label={t('advanced.duration.min')} placeholder={t('advanced.duration.min')} value={draft.minDuration} onChange={(e) => onChange({ minDuration: e.target.value })} />
            <span aria-hidden className="text-muted">–</span>
            <Input size="sm" inputMode="numeric" aria-label={t('advanced.duration.max')} placeholder={t('advanced.duration.max')} value={draft.maxDuration} onChange={(e) => onChange({ maxDuration: e.target.value })} />
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-fg">{t('advanced.disposition.label')}</span>
        <DispositionChips selected={draft.disposition} onToggle={toggleDisposition} labels={dispositionLabel} groupLabel={t('advanced.disposition.label')} />
      </div>

      <div className="flex flex-wrap items-end gap-2.5 border-t border-line pt-3">
        <Button variant="primary" size="sm" onClick={onApply}>{t('advanced.apply')}</Button>
        <Button variant="ghost" size="sm" onClick={onClear}>{t('advanced.clear')}</Button>
      </div>

      <div className="flex flex-wrap items-end gap-2.5 border-t border-line pt-3">
        <Field label={t('advanced.templates.label')} className="min-w-[180px]">
          {(a) => (
            <Select
              {...a} value={templateId} onValueChange={setTemplateId} size="sm"
              placeholder={t('advanced.templates.placeholder')}
              options={templates.map((tpl) => ({ value: tpl.id, label: tpl.name }))}
            />
          )}
        </Field>
        <Button variant="secondary" size="sm" disabled={!templateId} onClick={() => onApplyTemplate(templateId)}>{t('advanced.templates.apply')}</Button>
        <Button
          variant="ghost" size="sm" icon={<Trash2 />} iconOnly disabled={!templateId} onClick={deleteTemplate}
          aria-label={t('advanced.templates.delete')}
        />
        <Field label={t('advanced.templates.saveLabel')} className="min-w-[180px] flex-1">
          {(a) => <Input {...a} size="sm" value={templateName} placeholder={t('advanced.templates.savePlaceholder')} onChange={(e) => setTemplateName(e.target.value)} />}
        </Field>
        <Button variant="secondary" size="sm" icon={<Save />} disabled={!templateName.trim()} onClick={saveTemplate}>{t('advanced.templates.save')}</Button>
      </div>
    </div>
  );
}
