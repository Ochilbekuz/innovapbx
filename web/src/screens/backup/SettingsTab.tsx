import { useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { ShieldAlert } from 'lucide-react';
import {
  useBackupSettings, useTestBackupTarget, useTrustSftpHostKey, useUpdateBackupPassphrase, useUpdateBackupSettings,
} from '@/api/queries';
import { isApiError } from '@/api/errors';
import { BACKUP_COMPONENTS, type BackupSettings } from '@/api/types';
import { useEnumText } from '@/lib/useEnumText';
import { dayLabels } from '@/pbx/domainText';
import { Button } from '@/ui/Button';
import { Modal } from '@/ui/Dialog';
import { Field, Input, Select } from '@/ui/Field';
import { Badge } from '@/ui/Status';
import { Checkbox, Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';
import { OtherFormError, StaleBanner, useMutationError } from '@/screens/integrations/shared';
import {
  backupSettingsPayload, passphrasePayload, passphraseStrength, passphraseValid, s3Valid,
  scheduleValid, sftpValid, usePassphraseForm, useLocalForm, useS3Form, useScheduleForm, useSftpForm,
} from './backupForms';
import { otherFieldError } from '@/lib/formHelpers';

/** Avtomatik jadval: yoqish/oʻchirish, davriylik, hafta kuni, vaqt, qismlar. */
function ScheduleSection({ form, canManage }: { form: ReturnType<typeof useScheduleForm>; canManage: boolean }) {
  const { t } = useTranslation('backup');
  const componentLabel = useEnumText('backup', 'components', BACKUP_COMPONENTS);
  const weekdays = dayLabels(t, 'long');
  if (!form.state) return null;
  const s = form.state;
  return (
    <section className="flex flex-col gap-4">
      <h4 className="font-display text-sm font-semibold">{t('settings.schedule.title')}</h4>
      <Toggle checked={s.enabled} onCheckedChange={form.setEnabled} disabled={!canManage} label={t('settings.schedule.enabled')} />
      <div className="grid grid-cols-2 gap-3">
        <Field label={t('settings.schedule.frequency')}>
          {(a) => (
            <Select
              {...a} disabled={!canManage} value={s.frequency} onValueChange={(v) => form.setFrequency(v as BackupSettings['schedule']['frequency'])}
              options={[{ value: 'daily', label: t('settings.schedule.frequencyOption.daily') }, { value: 'weekly', label: t('settings.schedule.frequencyOption.weekly') }]}
            />
          )}
        </Field>
        {s.frequency === 'weekly' && (
          <Field label={t('settings.schedule.weekday')}>
            {(a) => (
              <Select
                {...a} disabled={!canManage} value={String(s.weekday)} onValueChange={(v) => form.setWeekday(Number(v) as BackupSettings['schedule']['weekday'])}
                options={weekdays.map((label, i) => ({ value: String(i + 1), label }))}
              />
            )}
          </Field>
        )}
        <Field label={t('settings.schedule.time')}>
          {(a) => <Input {...a} disabled={!canManage} mono type="time" value={s.time} onChange={(e) => form.setTime(e.target.value)} />}
        </Field>
      </div>
      <div>
        <p className="mb-1.5 text-sm font-medium text-fg">{t('settings.schedule.components')}</p>
        <div className="flex flex-col gap-2">
          {BACKUP_COMPONENTS.map((c) => (
            <label key={c} className="flex items-center gap-2 text-sm">
              <Checkbox checked={s.components.includes(c)} disabled={!canManage} onCheckedChange={() => form.toggleComponentAt(c)} aria-label={componentLabel[c]} />
              {componentLabel[c]}
            </label>
          ))}
        </div>
      </div>
    </section>
  );
}

function LocalSection({ form, canManage }: { form: ReturnType<typeof useLocalForm>; canManage: boolean }) {
  const { t } = useTranslation('backup');
  if (!form.state) return null;
  return (
    <section className="flex flex-col gap-3">
      <h4 className="font-display text-sm font-semibold">{t('settings.local.title')}</h4>
      <Field label={t('settings.local.keepLast')} className="max-w-[12rem]">
        {(a) => <Input {...a} disabled={!canManage} mono type="number" min={1} value={form.state!.keepLast} onChange={(e) => form.setKeepLast(Number(e.target.value))} />}
      </Field>
    </section>
  );
}

type Translate = (k: string, o?: Record<string, unknown>) => string;
type TestResult = { ok: boolean; error?: string } | null;

/** Nishonni tekshirish natijasi — muvaffaqiyat/xato matni (S3 va SFTP bir xil koʻrinishda). */
function TestResultLine({ result, okKey, failKey, t }: { result: TestResult; okKey: string; failKey: string; t: Translate }) {
  if (!result) return null;
  return (
    <span className={result.ok ? 'text-sm text-success' : 'text-sm text-danger'}>
      {result.ok ? t(okKey) : t(failKey, { error: result.error ?? '' })}
    </span>
  );
}

/** «Tekshirish» tugmasi + natija qatori — S3 va SFTP seksiyalarida bir xil. */
function TestTargetRow({
  onTest, testing, testResult, testLabelKey, okKey, failKey, t,
}: { onTest: () => void; testing: boolean; testResult: TestResult; testLabelKey: string; okKey: string; failKey: string; t: Translate }) {
  return (
    <div className="flex items-center gap-2">
      <Button size="sm" variant="secondary" loading={testing} onClick={onTest}>{t(testLabelKey)}</Button>
      <TestResultLine result={testResult} okKey={okKey} failKey={failKey} t={t} />
    </div>
  );
}

type S3FieldsProps = {
  s: NonNullable<ReturnType<typeof useS3Form>['state']>;
  canManage: boolean;
  form: ReturnType<typeof useS3Form>;
};

function S3Fields({ s, canManage, form }: S3FieldsProps) {
  const { t } = useTranslation('backup');
  return (
    <div className="grid grid-cols-2 gap-3">
      <Field label={t('settings.s3.endpoint')}>{(a) => <Input {...a} disabled={!canManage} mono value={s.endpoint} onChange={(e) => form.setEndpoint(e.target.value)} />}</Field>
      <Field label={t('settings.s3.region')}>{(a) => <Input {...a} disabled={!canManage} mono value={s.region} onChange={(e) => form.setRegion(e.target.value)} />}</Field>
      <Field label={t('settings.s3.bucket')}>{(a) => <Input {...a} disabled={!canManage} mono value={s.bucket} onChange={(e) => form.setBucket(e.target.value)} />}</Field>
      <Field label={t('settings.s3.prefix')}>{(a) => <Input {...a} disabled={!canManage} mono value={s.prefix} onChange={(e) => form.setPrefix(e.target.value)} />}</Field>
      <Field label={t('settings.s3.accessKey')}>{(a) => <Input {...a} disabled={!canManage} mono value={s.accessKey} onChange={(e) => form.setAccessKey(e.target.value)} />}</Field>
      <Field label={t('settings.s3.secretKey')} hint={s.hasSecretKey ? t('settings.s3.secretKeySet') : undefined}>
        {(a) => <Input {...a} disabled={!canManage} type="password" value={s.secretKey} onChange={(e) => form.setSecretKey(e.target.value)} />}
      </Field>
      <Field label={t('settings.s3.keepLast')}>{(a) => <Input {...a} disabled={!canManage} mono type="number" min={1} value={s.keepLast} onChange={(e) => form.setKeepLast(Number(e.target.value))} />}</Field>
      <Toggle checked={s.pathStyle} onCheckedChange={form.setPathStyle} disabled={!canManage} label={t('settings.s3.pathStyle')} />
    </div>
  );
}

/** Saqlash nishoni seksiyasining umumiy qobigʻi (yoqish toggle + maydonlar + tekshirish qatori)
 * — S3 va SFTP seksiyalarida bir xil edi, shu shaklga ajratilgan. */
function StorageTargetSection({
  titleKey, enabledLabelKey, enabled, onEnabledChange, canManage, renderFields, onTest, testing, testResult, testLabelKey, okKey, failKey, t,
}: {
  titleKey: string; enabledLabelKey: string; enabled: boolean; onEnabledChange: (v: boolean) => void; canManage: boolean;
  renderFields: () => ReactNode; onTest: () => void; testing: boolean; testResult: TestResult;
  testLabelKey: string; okKey: string; failKey: string; t: Translate;
}) {
  return (
    <section className="flex flex-col gap-3">
      <h4 className="font-display text-sm font-semibold">{t(titleKey)}</h4>
      <Toggle checked={enabled} onCheckedChange={onEnabledChange} disabled={!canManage} label={t(enabledLabelKey)} />
      {enabled && renderFields()}
      {enabled && canManage && (
        <TestTargetRow onTest={onTest} testing={testing} testResult={testResult} testLabelKey={testLabelKey} okKey={okKey} failKey={failKey} t={t} />
      )}
    </section>
  );
}

/** S3/SFTP seksiyalari faqat `kind`, forma va maydonlar renderer'i bilan farqlanadi — i18n kalit
 * nomlari ham shu `kind`'dan hosil qilinadi, shuning uchun ikkalasi ham shu umumiy funksiyaga tayanadi. */
function StorageSection<TState extends { enabled: boolean }>({
  kind, form, canManage, onTest, testing, testResult, fields,
}: {
  kind: 's3' | 'sftp';
  form: { state: TState | null | undefined; setEnabled: (v: boolean) => void };
  canManage: boolean; onTest: () => void; testing: boolean; testResult: TestResult;
  fields: (s: TState) => ReactNode;
}) {
  const { t } = useTranslation('backup');
  if (!form.state) return null;
  const s = form.state;
  return (
    <StorageTargetSection
      titleKey={`settings.${kind}.title`} enabledLabelKey={`settings.${kind}.enabled`}
      enabled={s.enabled} onEnabledChange={form.setEnabled} canManage={canManage}
      renderFields={() => fields(s)}
      onTest={onTest} testing={testing} testResult={testResult}
      testLabelKey={`settings.${kind}.test`} okKey={`settings.${kind}.testOk`} failKey={`settings.${kind}.testFailed`} t={t}
    />
  );
}

type SftpFieldsProps = {
  s: NonNullable<ReturnType<typeof useSftpForm>['state']>;
  canManage: boolean;
  form: ReturnType<typeof useSftpForm>;
};

function SftpFields({ s, canManage, form }: SftpFieldsProps) {
  const { t } = useTranslation('backup');
  return (
    <div className="grid grid-cols-2 gap-3">
      <Field label={t('settings.sftp.host')}>{(a) => <Input {...a} disabled={!canManage} mono value={s.host} onChange={(e) => form.setHost(e.target.value)} />}</Field>
      <Field label={t('settings.sftp.port')}>{(a) => <Input {...a} disabled={!canManage} mono type="number" value={s.port} onChange={(e) => form.setPort(Number(e.target.value))} />}</Field>
      <Field label={t('settings.sftp.user')}>{(a) => <Input {...a} disabled={!canManage} mono value={s.user} onChange={(e) => form.setUser(e.target.value)} />}</Field>
      <Field label={t('settings.sftp.password')} hint={s.hasPassword ? t('settings.sftp.passwordSet') : undefined}>
        {(a) => <Input {...a} disabled={!canManage} type="password" value={s.password} onChange={(e) => form.setPassword(e.target.value)} />}
      </Field>
      <Field label={t('settings.sftp.key')} hint={s.hasKey ? t('settings.sftp.keySet') : undefined}>
        {(a) => <Input {...a} disabled={!canManage} type="password" value={s.key} onChange={(e) => form.setKey(e.target.value)} />}
      </Field>
      <Field label={t('settings.sftp.folder')}>{(a) => <Input {...a} disabled={!canManage} mono value={s.folder} onChange={(e) => form.setFolder(e.target.value)} />}</Field>
      <Field label={t('settings.sftp.keepLast')}>{(a) => <Input {...a} disabled={!canManage} mono type="number" min={1} value={s.keepLast} onChange={(e) => form.setKeepLast(Number(e.target.value))} />}</Field>
    </div>
  );
}

/** SFTP server barmoq izini birinchi marta koʻrganda (yoki oʻzgarganda) tasdiqlash modali. */
function TrustHostKeyModal({ fp, onClose }: { fp: string | null; onClose: () => void }) {
  const { t } = useTranslation('backup');
  const toast = useToast();
  const trustM = useTrustSftpHostKey();
  const mismatch = isApiError(trustM.error) && trustM.error.code === 'host_key_mismatch';

  const close = () => { trustM.reset(); onClose(); };
  return (
    <Modal
      size="sm"
      open={!!fp}
      onOpenChange={(v) => !v && close()}
      title={t('settings.sftp.trustTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={close}>{t('settings.sftp.trustCancel')}</Button>
          <Button
            variant="danger" loading={trustM.isPending}
            onClick={() => fp && trustM.mutate({ host_key_fp: fp }, {
              onSuccess: () => { toast({ kind: 'success', title: t('settings.sftp.trusted') }); close(); },
            })}
          >
            {t('settings.sftp.trustConfirm')}
          </Button>
        </>
      }
    >
      <p className="flex items-start gap-1.5 text-sm text-danger">
        <ShieldAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />
        {mismatch ? t('settings.sftp.trustMismatchBody') : t('settings.sftp.trustBody', { fp })}
      </p>
    </Modal>
  );
}

function BackupSettingsForm({ settings, canManage }: { settings: BackupSettings; canManage: boolean }) {
  const { t } = useTranslation('backup');
  const toast = useToast();
  const updateM = useUpdateBackupSettings();
  const testM = useTestBackupTarget();
  const schedule = useScheduleForm(settings);
  const local = useLocalForm(settings);
  const s3 = useS3Form(settings);
  const sftp = useSftpForm(settings);
  const { message: errorMessage, stale } = useMutationError(updateM.error);
  const [s3Test, setS3Test] = useState<{ ok: boolean; error?: string } | null>(null);
  const [sftpTest, setSftpTest] = useState<{ ok: boolean; error?: string } | null>(null);
  const [trustFp, setTrustFp] = useState<string | null>(null);

  if (!schedule.state || !local.state || !s3.state || !sftp.state) return null;

  const valid = scheduleValid(schedule.state) && s3Valid(s3.state) && sftpValid(sftp.state);
  const submit = () => {
    updateM.mutate(backupSettingsPayload(schedule.state!, local.state!, s3.state!, sftp.state!, settings.updated_at), {
      onSuccess: () => toast({ kind: 'success', title: t('saved') }),
    });
  };
  const testS3 = () => {
    setS3Test(null);
    testM.mutate({ target: 's3' }, { onSuccess: (res) => setS3Test(res) });
  };
  const testSftp = () => {
    setSftpTest(null);
    testM.mutate({ target: 'sftp' }, { onSuccess: (res) => (res.host_key_fp ? setTrustFp(res.host_key_fp) : setSftpTest(res)) });
  };

  return (
    <section className="flex max-w-2xl flex-col gap-6 rounded-lg border border-line bg-surface p-4 shadow-card">
      <StaleBanner stale={stale} message={errorMessage} />
      <ScheduleSection form={schedule} canManage={canManage} />
      <LocalSection form={local} canManage={canManage} />
      <StorageSection
        kind="s3" form={s3} canManage={canManage} onTest={testS3} testing={testM.isPending} testResult={s3Test}
        fields={(s) => <S3Fields s={s} canManage={canManage} form={s3} />}
      />
      <StorageSection
        kind="sftp" form={sftp} canManage={canManage} onTest={testSftp} testing={testM.isPending} testResult={sftpTest}
        fields={(s) => <SftpFields s={s} canManage={canManage} form={sftp} />}
      />
      <OtherFormError message={otherFieldError(errorMessage, stale, undefined, [])} />
      {canManage && <div><Button variant="primary" loading={updateM.isPending} disabled={!valid} onClick={submit}>{t('save')}</Button></div>}
      <TrustHostKeyModal fp={trustFp} onClose={() => setTrustFp(null)} />
    </section>
  );
}

/** Hozirgi parol maydoni — faqat parol allaqachon oʻrnatilgan boʻlsa koʻrsatiladi (almashtirishni tasdiqlash uchun). */
function CurrentPasswordField({
  show, value, onChange, error, t,
}: { show: boolean; value: string; onChange: (v: string) => void; error: string | undefined; t: Translate }) {
  if (!show) return null;
  return (
    <Field label={t('settings.passphrase.current')} error={error}>
      {(a) => <Input {...a} type="password" value={value} onChange={(e) => onChange(e.target.value)} />}
    </Field>
  );
}

/** Yangi parol kuchi koʻrsatkichi (kuchsiz/oʻrta/kuchli). */
function StrengthHint({ strength, t }: { strength: ReturnType<typeof passphraseStrength> | null; t: Translate }) {
  if (!strength) return null;
  return <span className="text-sm text-muted">{t(`settings.passphrase.strength.${strength}`)}</span>;
}

/** Zaxira parolini oʻrnatish/almashtirish — kuch koʻrsatkichi va yoʻqotish ogohlantirishi bilan. */
function PassphraseSection({ hasPassphrase, canManage }: { hasPassphrase: boolean; canManage: boolean }) {
  const { t } = useTranslation('backup');
  const toast = useToast();
  const updateM = useUpdateBackupPassphrase();
  const { setCurrent, setNext, reset, state } = usePassphraseForm();
  const { field: errorField, message: errorMessage, stale } = useMutationError(updateM.error);
  const strength = state.next ? passphraseStrength(state.next) : null;

  const submit = () => {
    updateM.mutate(passphrasePayload(state, hasPassphrase), {
      onSuccess: () => { toast({ kind: 'success', title: t('settings.passphrase.saved') }); reset(); },
    });
  };

  return (
    <section className="flex max-w-2xl flex-col gap-4 rounded-lg border border-line bg-surface p-4 shadow-card">
      <div className="flex items-center justify-between">
        <h3 className="font-display text-base font-semibold">{t('settings.passphrase.title')}</h3>
        <Badge tone={hasPassphrase ? 'success' : 'warning'}>{hasPassphrase ? t('settings.passphrase.setBadge') : t('settings.passphrase.notSetBadge')}</Badge>
      </div>
      <p className="text-sm text-muted">{t('settings.passphrase.desc')}</p>
      {canManage && (
        <div className="flex flex-col gap-3">
          <StaleBanner stale={stale} message={errorMessage} />
          <CurrentPasswordField
            show={hasPassphrase} value={state.current} onChange={setCurrent}
            error={errorField === 'current' ? errorMessage : undefined} t={t}
          />
          <Field
            label={t('settings.passphrase.new')} hint={t('settings.passphrase.newHint')}
            error={errorField === 'passphrase' ? errorMessage : undefined}
          >
            {(a) => <Input {...a} type="password" value={state.next} onChange={(e) => setNext(e.target.value)} />}
          </Field>
          <StrengthHint strength={strength} t={t} />
          <div><Button variant="primary" loading={updateM.isPending} disabled={!passphraseValid(state, hasPassphrase)} onClick={submit}>{t('settings.passphrase.submit')}</Button></div>
        </div>
      )}
    </section>
  );
}

/** «Jadval va saqlash joylari» tabi — jadval/lokal/S3/SFTP sozlamalari va zaxira paroli (shartnoma §3). */
export function SettingsTab({ canManage }: { canManage: boolean }) {
  const { data } = useBackupSettings();
  if (!data) return <p className="text-sm text-muted">…</p>;
  return (
    <div className="flex flex-col gap-5">
      <BackupSettingsForm settings={data} canManage={canManage} />
      <PassphraseSection hasPassphrase={data.has_passphrase} canManage={canManage} />
    </div>
  );
}
