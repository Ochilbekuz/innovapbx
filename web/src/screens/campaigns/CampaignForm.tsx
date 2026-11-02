import { useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { apiErrorMessage, isApiError } from '@/api/errors';
import { useAudio } from '@/api/queries';
import type { Campaign, CampaignMode } from '@/api/types';
import { campaignToForm, defaultCampaignForm, toggleDay, type CampaignForm as FormState } from '@/domain/campaigns';
import { cn } from '@/lib/cn';
import { Button } from '@/ui/Button';
import { Drawer } from '@/ui/Dialog';
import { Field, Input, Segmented, Select } from '@/ui/Field';
import { Toggle } from '@/ui/Toggle';

const FIELDS_SHOWN = ['name', 'audio_id', 'target_number', 'callerid', 'window_start', 'window_end', 'days',
  'max_concurrent', 'max_attempts', 'retry_delay_s', 'ring_seconds'];
const DAYS = [1, 2, 3, 4, 5, 6, 7];

type SectionProps = {
  form: FormState;
  set: <K extends keyof FormState>(k: K, v: FormState[K]) => void;
  fieldError: (name: string) => string | undefined;
};

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3.5 border-t border-line pt-4 first:border-t-0 first:pt-0">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">{title}</h3>
      {children}
    </section>
  );
}

/** Raqamli maydon: faqat raqamlar; bo'sh — 0 (backend 422 qaytaradi). */
function NumberField({ label, hint, value, onChange, error }: { label: string; hint: string; value: number; onChange: (v: number) => void; error?: string }) {
  return (
    <Field label={label} hint={hint} error={error}>
      {(a) => <Input {...a} mono inputMode="numeric" value={String(value)} onChange={(e) => onChange(Number(e.target.value.replace(/\D/g, '')) || 0)} />}
    </Field>
  );
}

function MessageOptions({ form, set, fieldError }: SectionProps) {
  const { t } = useTranslation('campaigns');
  const { data: audio } = useAudio();
  return (
    <>
      <Field label={t('form.audioLabel')} hint={t('form.audioHint')} required error={fieldError('audio_id')}>
        {(a) => (
          <Select
            {...a} placeholder={t('form.audioPlaceholder')} value={form.audio_id ?? ''} onValueChange={(v) => set('audio_id', v)}
            options={(audio?.items ?? []).map((x) => ({ value: x.id, label: x.name }))}
          />
        )}
      </Field>
      <div className="flex flex-col gap-3 rounded-md border border-line bg-surface-2/50 p-3">
        <Toggle checked={form.dtmf_connect} onCheckedChange={(v) => set('dtmf_connect', v)} label={t('form.dtmfConnectLabel')} description={t('form.dtmfConnectHint')} />
        <Toggle checked={form.dtmf_optout} onCheckedChange={(v) => set('dtmf_optout', v)} label={t('form.dtmfOptoutLabel')} description={t('form.dtmfOptoutHint')} />
      </div>
    </>
  );
}

function WhatSection(props: SectionProps) {
  const { t } = useTranslation('campaigns');
  const { form, set, fieldError } = props;
  const message = form.mode === 'message';
  return (
    <Section title={t('form.sectionWhat')}>
      <div className="flex flex-col gap-1.5">
        <Segmented<CampaignMode>
          size="md" label={t('form.modeLabel')} value={form.mode} onChange={(v) => set('mode', v)}
          options={[{ value: 'message', label: t('mode.message') }, { value: 'connect', label: t('mode.connect') }]}
        />
        <p className="text-sm text-muted">{t(`modeHint.${form.mode}`)}</p>
      </div>
      {message && <MessageOptions {...props} />}
      {(!message || form.dtmf_connect) && (
        <Field label={t('form.targetLabel')} hint={t('form.targetHint')} required error={fieldError('target_number')}>
          {(a) => <Input {...a} mono inputMode="numeric" maxLength={15} value={form.target_number} onChange={(e) => set('target_number', e.target.value.trim())} />}
        </Field>
      )}
      <Field label={t('form.calleridLabel')} hint={t('form.calleridHint')} error={fieldError('callerid')}>
        {(a) => <Input {...a} mono inputMode="numeric" maxLength={15} value={form.callerid} onChange={(e) => set('callerid', e.target.value.trim())} />}
      </Field>
    </Section>
  );
}

function DayChip({ day, on, onToggle }: { day: number; on: boolean; onToggle: () => void }) {
  const { t } = useTranslation('campaigns');
  return (
    <button
      type="button" aria-pressed={on} onClick={onToggle}
      className={cn(
        'h-8 w-10 rounded-md border text-sm font-medium transition-colors duration-fast',
        on ? 'border-brand/40 bg-accent-soft text-on-accent-soft' : 'border-line bg-surface text-muted hover:text-fg',
        day >= 6 && !on && 'text-disabled',
      )}
    >
      {t(`day.${day}`)}
    </button>
  );
}

function WhenSection({ form, set, fieldError }: SectionProps) {
  const { t } = useTranslation('campaigns');
  const daysError = fieldError('days');
  return (
    <Section title={t('form.sectionWhen')}>
      <div className="grid grid-cols-2 gap-3">
        <Field label={t('form.windowStart')} error={fieldError('window_start')}>
          {(a) => <Input {...a} mono type="time" value={form.window_start} onChange={(e) => set('window_start', e.target.value)} />}
        </Field>
        <Field label={t('form.windowEnd')} error={fieldError('window_end')}>
          {(a) => <Input {...a} mono type="time" value={form.window_end} onChange={(e) => set('window_end', e.target.value)} />}
        </Field>
      </div>
      <p className="-mt-1.5 text-sm text-muted">{t('form.windowHint')}</p>
      <fieldset className="flex flex-col gap-1.5">
        <legend className="mb-1.5 text-sm font-medium text-fg">{t('form.daysLabel')}</legend>
        <div className="flex gap-1">
          {DAYS.map((d) => <DayChip key={d} day={d} on={form.days.includes(d)} onToggle={() => set('days', toggleDay(form.days, d))} />)}
        </div>
        {daysError && <p className="text-sm text-danger">{daysError}</p>}
      </fieldset>
    </Section>
  );
}

function PaceSection({ form, set, fieldError }: SectionProps) {
  const { t } = useTranslation('campaigns');
  return (
    <Section title={t('form.sectionPace')}>
      <div className="grid grid-cols-2 gap-3">
        <NumberField label={t('form.concurrencyLabel')} hint={t('form.concurrencyHint')} value={form.max_concurrent} onChange={(v) => set('max_concurrent', v)} error={fieldError('max_concurrent')} />
        <NumberField label={t('form.attemptsLabel')} hint={t('form.attemptsHint')} value={form.max_attempts} onChange={(v) => set('max_attempts', v)} error={fieldError('max_attempts')} />
        <NumberField
          label={t('form.retryLabel')} hint={t('form.retryHint')} value={Math.round(form.retry_delay_s / 60)}
          onChange={(v) => set('retry_delay_s', v * 60)} error={fieldError('retry_delay_s')}
        />
        <NumberField label={t('form.ringLabel')} hint={t('form.ringHint')} value={form.ring_seconds} onChange={(v) => set('ring_seconds', v)} error={fieldError('ring_seconds')} />
      </div>
    </Section>
  );
}

/** Server xatosini maydonga yoki umumiy qutiga bo'ladi. */
export function splitFormError(error: unknown): { fieldError: (name: string) => string | undefined; general: string | null } {
  const field = isApiError(error) ? error.field : undefined;
  const message = error ? apiErrorMessage(error) : null;
  return {
    fieldError: (name) => (field === name ? message ?? undefined : undefined),
    general: FIELDS_SHOWN.includes(field ?? '') ? null : message,
  };
}

export function CampaignForm({
  campaign, pending, error, onClose, onSubmit,
}: {
  campaign?: Campaign;
  pending: boolean;
  error: unknown;
  onClose: () => void;
  onSubmit: (form: FormState) => void;
}) {
  const { t } = useTranslation('campaigns');
  const [form, setForm] = useState<FormState>(() => (campaign ? campaignToForm(campaign) : defaultCampaignForm()));
  const set: SectionProps['set'] = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const { fieldError, general } = splitFormError(error);
  const valid = form.name.trim() !== '' && form.days.length > 0;
  const sectionProps = { form, set, fieldError };

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={campaign ? t('form.editTitle', { name: campaign.name }) : t('form.newTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={() => onSubmit(form)}>{campaign ? t('save') : t('add')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-5">
        {general && <p role="alert" className="rounded-md border border-danger/25 bg-danger-soft px-3 py-2 text-sm text-on-danger-soft">{general}</p>}
        <Field label={t('form.nameLabel')} required error={fieldError('name')}>
          {(a) => <Input {...a} autoFocus maxLength={80} placeholder={t('form.namePlaceholder')} value={form.name} onChange={(e) => set('name', e.target.value)} />}
        </Field>
        <WhatSection {...sectionProps} />
        <WhenSection {...sectionProps} />
        <PaceSection {...sectionProps} />
      </div>
    </Drawer>
  );
}
