import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { formatDateTimeShort } from '@/lib/time';
import {
  BellOff, ChevronDown, Copy, Eye, EyeOff, Headset, KeyRound, Mail, Pencil, PhoneForwarded, Plus, QrCode, RefreshCw,
  RotateCw, ShieldAlert, ShieldOff, Smartphone, Trash2, Voicemail,
} from 'lucide-react';
import {
  useCreateExtension, useCreateVoicemailBox, useDeleteExtension, useDevices, useExtensions, useRotateExtensionSecret,
  useSetExtensionSecret, useUpdateExtension, useVoicemailBoxes,
} from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { CreateExtensionPayload, Extension, SipCredentials, UpdateExtensionPayload } from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { applyToast } from '@/lib/applyToast';
import { AppShellPage } from '@/shell/AppShellPage';
import { CreateDeviceModal, DeviceStatusBadge } from '@/screens/devices/DevicesTab';
import { Button } from '@/ui/Button';
import { Modal, Drawer } from '@/ui/Dialog';
import { Field, Input, Select } from '@/ui/Field';
import { Badge, StatusPill } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';
import { cn } from '@/lib/cn';
import { generateSipPassword, validateSipPassword, type SipPasswordIssue } from '@/domain/sipPassword';
import {
  DEFAULT_CALL_SETTINGS, type CallSettingsState, callSettingsFromExtension, createExtensionPayload, createExtensionValid,
  editExtensionDirty, editExtensionValid, forwardNumberValid, pickupGroupValid,
  updateExtensionPayload, useCallSettings,
} from './extensionForms';
import { FollowMeSection } from './FollowMeSection';
import { QrConnectModal } from './QrConnectModal';
import type { RecordingPolicy } from '@/api/types';
import { copyText } from '@/lib/browser';

const RECORDING_POLICIES: RecordingPolicy[] = ['always', 'never', 'on_demand'];

/** Yozib olish siyosatini tanlash (always/never/on_demand) — M3c §1: yoʻnalish boʻyicha MUSTAQIL
 * (kiruvchi/chiquvchi). `ext-recording-in-select`/`ext-recording-out-select` testid talab qilinadi. */
function RecordingSelect({ direction, value, onChange, disabled }: {
  direction: 'in' | 'out'; value: RecordingPolicy; onChange: (v: RecordingPolicy) => void; disabled?: boolean;
}) {
  const { t } = useTranslation('extensions');
  return (
    <Field label={t(`recording.${direction}.label`)} hint={t(`recording.${direction}.hint`)}>
      {(a) => (
        <Select
          {...a}
          data-testid={`ext-recording-${direction}-select`}
          disabled={disabled}
          value={value}
          onValueChange={(v) => onChange(v as RecordingPolicy)}
          options={RECORDING_POLICIES.map((p) => ({ value: p, label: t(`recording.${p}`) }))}
        />
      )}
    </Field>
  );
}

const NAME_MAX = 60;
const PIN_RE = /^\d{4,8}$/;

/** Ro'yxatdagi DND/yo'naltirish belgisi — qisqa, bosilmas ko'rinish (§1 "Ro'yxatda belgi"). */
function CallsBadges({ ext }: { ext: Extension }) {
  const { t } = useTranslation('extensions');
  if (!ext.dnd && !ext.forward_always && !ext.forward_busy && !ext.toll_blocked_at) return <span className="text-sm text-muted">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {ext.dnd && <Badge tone="danger"><BellOff aria-hidden className="size-3" /> {t('calls.badgeDnd')}</Badge>}
      {ext.forward_always && <Badge tone="info"><PhoneForwarded aria-hidden className="size-3" /> {t('calls.badgeForwardAlways', { number: ext.forward_always })}</Badge>}
      {ext.forward_busy && <Badge tone="info"><PhoneForwarded aria-hidden className="size-3" /> {t('calls.badgeForwardBusy', { number: ext.forward_busy })}</Badge>}
      {ext.toll_blocked_at && <Badge tone="danger"><ShieldOff aria-hidden className="size-3" /> {t('calls.badgeTollBlocked')}</Badge>}
    </div>
  );
}

/** Haqiqiy backend soʻrov kelgan server xostini qaytaradi; fake buni allaqachon toʻgʻri beradi — bu faqat himoya. */
function sipDomainFallback(domain: string): string {
  return domain || (typeof window !== 'undefined' ? window.location.hostname : '');
}

function SipFields({ sip }: { sip: SipCredentials }) {
  const { t } = useTranslation('extensions');
  const rows: [string, string][] = [
    [t('sip.login'), sip.username], [t('sip.password'), sip.password],
    [t('sip.domain'), sipDomainFallback(sip.domain)], [t('sip.port'), String(sip.port)],
  ];
  return (
    <div className="flex flex-col gap-2">
      <p className="flex items-start gap-1.5 text-sm text-danger">
        <ShieldAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />
        {t('sip.revealWarning')}
      </p>
      {rows.map(([label, value]) => (
        <div key={label} className="flex items-center justify-between gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2">
          <span className="text-sm text-muted">{label}</span>
          <div className="flex items-center gap-2">
            <span className="num text-sm font-medium text-fg">{value}</span>
            <Button
              size="sm" variant="ghost" iconOnly icon={<Copy />} aria-label={t('sip.copyAriaLabel', { label })}
              onClick={() => void copyText(value)}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * SIP parol maydoni — koʻrsatish/yashirish, qayta generatsiya va nusxalash tugmalari bilan.
 * `Input`ning `trailing` slotida 1 tadan ortiq tugma sig'maydi (qarang `ui/Field.tsx`), shu sababli
 * tashqi `relative` o'ram + mustaqil joylashtirilgan tugmalar guruhi qo'llanildi.
 */
function SipPasswordField({
  password, onChange, onRegenerate, issue, serverError, label, hint, autoFocus,
}: {
  password: string;
  onChange: (v: string) => void;
  onRegenerate: () => void;
  issue: SipPasswordIssue | null;
  serverError?: string;
  label: string;
  hint: string;
  autoFocus?: boolean;
}) {
  const { t } = useTranslation('extensions');
  const [reveal, setReveal] = useState(false);
  const error = serverError ?? (issue ? t(`password.issue.${issue}`) : undefined);

  return (
    <Field label={label} required hint={error ? undefined : hint} error={error}>
      {(a) => (
        <div className="relative flex items-center">
          <Input
            {...a} autoFocus={autoFocus} mono type={reveal ? 'text' : 'password'} className="pr-24"
            value={password} onChange={(e) => onChange(e.target.value)}
          />
          <div className="absolute right-1 flex items-center gap-0.5">
            <Button
              size="sm" variant="ghost" iconOnly icon={reveal ? <EyeOff /> : <Eye />}
              aria-label={reveal ? t('password.hideAriaLabel') : t('password.showAriaLabel')}
              onClick={() => setReveal((v) => !v)}
            />
            <Button size="sm" variant="ghost" iconOnly icon={<RefreshCw />} aria-label={t('password.regenerateAriaLabel')} onClick={onRegenerate} />
            <Button size="sm" variant="ghost" iconOnly icon={<Copy />} aria-label={t('password.copyAriaLabel')} onClick={() => void copyText(password)} />
          </div>
        </div>
      )}
    </Field>
  );
}

/** DND/yoʻnaltirish/pickup/chiquvchi qoʻngʻiroq sozlamalari — Yaratish (ixtiyoriy boʻlim ichida) VA Tahrirlashda (doim koʻrinadi) bir xil. */
/** Bitta maydon uchun xato xabari — backend xatosi ustunlik qiladi, aks holda mahalliy formatlash tekshiruvi. */
function fieldError(
  field: string, ok: boolean, invalidHint: string, errorField: string | undefined, errorMessage: string | undefined,
): string | undefined {
  if (errorField === field) return errorMessage;
  return ok ? undefined : invalidHint;
}

function CallSettingsFields({
  calls, setDnd, setForwardAlways, setForwardBusy, setPickupGroup, setOutboundAllowed, setOutboundCallerid, errorField, errorMessage,
}: {
  calls: CallSettingsState;
  setDnd: (v: boolean) => void;
  setForwardAlways: (v: string) => void;
  setForwardBusy: (v: string) => void;
  setPickupGroup: (v: string) => void;
  setOutboundAllowed: (v: boolean) => void;
  setOutboundCallerid: (v: string) => void;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('extensions');
  const forwardAlwaysOk = forwardNumberValid(calls.forwardAlways);
  const forwardBusyOk = forwardNumberValid(calls.forwardBusy);
  const pickupGroupOk = pickupGroupValid(calls.pickupGroup);
  const outboundCalleridOk = forwardNumberValid(calls.outboundCallerid);

  return (
    <div className="flex flex-col gap-4">
      <Toggle checked={calls.dnd} onCheckedChange={setDnd} label={t('calls.dndLabel')} description={t('calls.dndDesc')} />
      <Field
        label={t('calls.forwardAlwaysLabel')} hint={t('calls.forwardAlwaysHint')}
        error={fieldError('forward_always', forwardAlwaysOk, t('calls.forwardAlwaysHint'), errorField, errorMessage)}
      >
        {(a) => <Input {...a} mono value={calls.forwardAlways} onChange={(e) => setForwardAlways(e.target.value)} />}
      </Field>
      <Field
        label={t('calls.forwardBusyLabel')} hint={t('calls.forwardBusyHint')}
        error={fieldError('forward_busy', forwardBusyOk, t('calls.forwardBusyHint'), errorField, errorMessage)}
      >
        {(a) => <Input {...a} mono value={calls.forwardBusy} onChange={(e) => setForwardBusy(e.target.value)} />}
      </Field>
      <Field
        label={t('calls.pickupGroupLabel')} hint={t('calls.pickupGroupHint')}
        error={fieldError('pickup_group', pickupGroupOk, t('calls.pickupGroupHint'), errorField, errorMessage)}
      >
        {(a) => <Input {...a} mono value={calls.pickupGroup} onChange={(e) => setPickupGroup(e.target.value)} />}
      </Field>
      <Toggle checked={calls.outboundAllowed} onCheckedChange={setOutboundAllowed} label={t('calls.outboundAllowedLabel')} description={t('calls.outboundAllowedDesc')} />
      <Field
        label={t('calls.outboundCalleridLabel')} hint={t('calls.outboundCalleridHint')}
        error={fieldError('outbound_callerid', outboundCalleridOk, t('calls.outboundCalleridHint'), errorField, errorMessage)}
      >
        {(a) => <Input {...a} mono value={calls.outboundCallerid} onChange={(e) => setOutboundCallerid(e.target.value)} />}
      </Field>
      <p className="text-xs text-muted">{t('calls.realtimeNotice')}</p>
    </div>
  );
}

/** Mavjud ichki raqam uchun SIP parolini almashtirish — o'z parolini kiritish YOKI tasodifiy generatsiya. */
function ChangePasswordSection({ ext, onChanged }: { ext: Extension; onChanged: (sip: SipCredentials) => void }) {
  const { t } = useTranslation('extensions');
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState('');
  const setSecretM = useSetExtensionSecret();
  const rotateM = useRotateExtensionSecret();
  const issue = validateSipPassword(password, ext.number);

  const applied = (sip: SipCredentials) => {
    setOpen(false);
    setPassword('');
    toast({ kind: 'success', title: t('changePassword.changed') });
    onChanged(sip);
  };

  return (
    <div className="border-t border-line pt-4">
      <p className="mb-2 flex items-center gap-1.5 text-sm font-medium text-fg"><KeyRound aria-hidden className="size-4 text-brand" /> {t('changePassword.title')}</p>
      {!open ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="secondary" onClick={() => setOpen(true)}>{t('changePassword.enterOwn')}</Button>
          <Button
            size="sm" variant="ghost" loading={rotateM.isPending}
            onClick={() => rotateM.mutate(ext.id, { onSuccess: (res) => applied(res.sip) })}
          >
            {t('changePassword.generateNew')}
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <SipPasswordField
            password={password} onChange={setPassword} onRegenerate={() => setPassword(generateSipPassword(ext.number))}
            issue={password ? issue : null} label={t('changePassword.newPasswordLabel')} hint={t('password.hint')} autoFocus
          />
          <div className="flex gap-2">
            <Button size="sm" variant="ghost" onClick={() => { setOpen(false); setPassword(''); }}>{t('cancel')}</Button>
            <Button
              size="sm" variant="primary" loading={setSecretM.isPending} disabled={!password || !!issue}
              data-testid="change-password-save"
              onClick={() => setSecretM.mutate({ id: ext.id, password }, { onSuccess: (res) => applied(res.sip) })}
            >
              {t('changePassword.save')}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

/** S04 — ichki raqamlar: ro'yxat, qidirish, jonli holat, yaratish (bir martalik SIP), tahrirlash, sirni almashtirish, o'chirish. */
export function ExtensionsPage() {
  const { t } = useTranslation('extensions');
  const { data, isLoading, isError, refetch } = useExtensions({ page: 1, size: 200 });
  const canManage = useCanEdit('extensions');
  const toast = useToast();

  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<Extension | null>(null);
  const [deleting, setDeleting] = useState<Extension | null>(null);
  const [qrFor, setQrFor] = useState<Extension | null>(null);
  const [sipReveal, setSipReveal] = useState<{ title: string; sip: SipCredentials } | null>(null);

  const createM = useCreateExtension();
  const updateM = useUpdateExtension();
  const rotateM = useRotateExtensionSecret();
  const deleteM = useDeleteExtension();

  const closeCreate = () => { setCreateOpen(false); createM.reset(); };
  const closeEdit = () => { setEditing(null); updateM.reset(); };

  const columns: Column<Extension>[] = [
    {
      key: 'number', header: t('column.number'), sortValue: (r) => r.number, width: '110px', cell: (r) => (
        <span className="inline-flex items-center gap-1.5">
          <span className="num font-medium">{r.number}</span>
          {r.webrtc && <>{' '}<span title={t('webrtc.desc')}><Badge tone="info"><Headset aria-hidden className="size-3" /> {t('webrtc.badge')}</Badge></span></>}
        </span>
      ),
    },
    { key: 'name', header: t('column.name'), sortValue: (r) => r.name, cell: (r) => <span className="block max-w-[260px] truncate" title={r.name}>{r.name}</span> },
    {
      key: 'status', header: t('column.status'), cell: (r) => (
        <StatusPill status={r.status === 'online' ? 'online' : r.status === 'offline' ? 'offline' : 'disabled'} live={r.status !== 'unknown'}>
          {r.status === 'unknown' ? t('unknownStatus') : undefined}
        </StatusPill>
      ),
    },
    { key: 'enabled', header: t('column.enabled'), cell: (r) => <Badge tone={r.enabled ? 'success' : 'neutral'}>{r.enabled ? t('yes') : t('no')}</Badge> },
    { key: 'calls', header: t('column.calls'), cell: (r) => <CallsBadges ext={r} /> },
    { key: 'updated_at', header: t('column.updatedAt'), sortValue: (r) => r.updated_at, cell: (r) => <span className="num text-sm text-muted">{formatDateTimeShort(r.updated_at)}</span> },
    {
      key: 'actions', header: '', align: 'right', cell: (r) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('editAriaLabel', { number: r.number })} disabled={!canManage} onClick={() => setEditing(r)} />
          <Button
            size="sm" variant="ghost" iconOnly icon={<QrCode />} aria-label={t('qr.openAriaLabel', { ns: 'followme', number: r.number })}
            disabled={!canManage || r.webrtc} data-testid={`qr-open-${r.number}`} onClick={() => setQrFor(r)}
          />
          <Button
            size="sm" variant="ghost" iconOnly icon={<RotateCw />} aria-label={t('rotateAriaLabel', { number: r.number })} disabled={!canManage}
            onClick={() => rotateM.mutate(r.id, { onSuccess: (res) => { setSipReveal({ title: t('toast.newSipTitle', { number: r.number }), sip: res.sip }); toast(applyToast(res.apply, t('toast.secretRotated'))); } })}
          />
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('deleteAriaLabel', { number: r.number })} disabled={!canManage} onClick={() => setDeleting(r)} />
        </div>
      ),
    },
  ];

  return (
    <AppShellPage title={t('title')}>
      {!canManage && (
        <p className="mb-3 flex items-center gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2 text-sm text-muted">
          <ShieldAlert aria-hidden className="size-4 shrink-0" />
          {t('readOnlyNotice')}
        </p>
      )}
      <DataTable
        caption={t('caption')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(r) => r.id}
        searchText={(r) => `${r.number} ${r.name}`}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        onRowOpen={canManage ? (r) => setEditing(r) : undefined}
        empty={{ title: t('empty.title'), body: t('empty.body'), action: canManage ? <Button size="sm" onClick={() => setCreateOpen(true)}>{t('empty.action')}</Button> : undefined }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setCreateOpen(true)}>{t('newExtension')}</Button> : undefined}
      />

      <CreateExtensionModal
        open={createOpen}
        onOpenChange={(v) => (v ? setCreateOpen(true) : closeCreate())}
        onSubmit={(payload) =>
          createM.mutate(payload, {
            onSuccess: (res) => { closeCreate(); setSipReveal({ title: t('toast.sipTitle', { number: res.item.number }), sip: res.sip }); toast(applyToast(res.apply, t('toast.created'))); },
          })
        }
        pending={createM.isPending}
        errorField={isApiError(createM.error) ? createM.error.field : undefined}
        errorMessage={isApiError(createM.error) ? createM.error.message : undefined}
      />

      {editing && (
        <EditExtensionDrawer
          ext={editing}
          onClose={closeEdit}
          onSubmit={(payload) =>
            updateM.mutate({ id: editing.id, payload }, {
              onSuccess: (res) => { closeEdit(); toast(applyToast(res.apply, t('toast.saved'))); },
            })
          }
          pending={updateM.isPending}
          errorField={isApiError(updateM.error) ? updateM.error.field : undefined}
          errorMessage={isApiError(updateM.error) ? updateM.error.message : undefined}
          stale={isApiError(updateM.error) && updateM.error.code === 'stale'}
          onReloadStale={() => { void refetch(); closeEdit(); }}
          onFollowMeSaved={(updatedAt) => setEditing((e) => e && { ...e, updated_at: updatedAt })}
          onSecretChanged={(sip) => setSipReveal({ title: t('toast.newSipTitle', { number: editing.number }), sip })}
        />
      )}

      <QrConnectModal target={qrFor?.id ?? null} number={qrFor?.number ?? ''} open={!!qrFor} onOpenChange={(v) => !v && setQrFor(null)} />

      <Modal
        open={!!deleting}
        onOpenChange={(v) => !v && setDeleting(null)}
        title={deleting ? t('deleteModal.title', { number: deleting.number }) : ''}
        description={t('deleteModal.description')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleting(null)}>{t('cancel')}</Button>
            <Button
              variant="danger" loading={deleteM.isPending}
              onClick={() => deleting && deleteM.mutate(deleting.id, {
                onSuccess: () => { toast({ kind: 'success', title: t('toast.deleted', { number: deleting.number }) }); setDeleting(null); },
                onError: (e) => {
                  if (isApiError(e) && e.code === 'in_use') {
                    const usages = (e.details?.usages as { label: string }[] | undefined) ?? [];
                    toast({ kind: 'error', title: t('toast.deleteFailed'), description: t('deleteModal.inUseBody', { usages: usages.map((u) => u.label).join(', ') || e.message }) });
                  } else {
                    toast({ kind: 'error', title: t('toast.deleteFailed'), description: e.message });
                  }
                  setDeleting(null);
                },
              })}
            >
              {t('delete')}
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted">{t('deleteModal.body', { name: deleting?.name, number: deleting?.number })}</p>
      </Modal>

      <Modal
        open={!!sipReveal}
        onOpenChange={(v) => !v && setSipReveal(null)}
        title={sipReveal?.title ?? ''}
        footer={<Button variant="primary" onClick={() => setSipReveal(null)}>{t('closeSaved')}</Button>}
      >
        {sipReveal && <SipFields sip={sipReveal.sip} />}
      </Modal>
    </AppShellPage>
  );
}

function CreateExtensionModal({
  open, onOpenChange, onSubmit, pending, errorField, errorMessage,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onSubmit: (payload: CreateExtensionPayload) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('extensions');
  const [number, setNumber] = useState('');
  const [name, setName] = useState('');
  const [password, setPassword] = useState(() => generateSipPassword(''));
  const [webrtc, setWebrtc] = useState(false);
  const [recordingIn, setRecordingIn] = useState<RecordingPolicy>('never');
  const [recordingOut, setRecordingOut] = useState<RecordingPolicy>('never');
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const calls = useCallSettings(DEFAULT_CALL_SETTINGS);

  const passwordIssue = validateSipPassword(password, number.trim());
  const valid = createExtensionValid({ number, name, password, webrtc, recordingIn, recordingOut, calls: calls.state });

  const reset = () => {
    setNumber(''); setName(''); setPassword(generateSipPassword('')); setWebrtc(false);
    setRecordingIn('never'); setRecordingOut('never');
    setAdvancedOpen(false); calls.setState(DEFAULT_CALL_SETTINGS);
  };

  return (
    <Modal
      open={open}
      onOpenChange={(v) => { onOpenChange(v); if (!v) reset(); }}
      title={t('createModal.title')}
      description={t('createModal.description')}
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>{t('cancel')}</Button>
          <Button
            variant="primary" loading={pending} icon={<KeyRound />}
            onClick={() => onSubmit(createExtensionPayload({ number, name, password, webrtc, recordingIn, recordingOut, calls: calls.state }))}
            disabled={!valid}
          >
            {t('create')}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label={t('field.number')} aside={t('field.optional')} error={errorField === 'number' ? errorMessage : undefined} hint={t('field.numberHint')}>
          {(a) => <Input {...a} mono placeholder={t('field.numberPlaceholder')} value={number} onChange={(e) => setNumber(e.target.value)} />}
        </Field>
        <Field label={t('field.name')} required hint={t('field.nameHint', { max: NAME_MAX })}>
          {(a) => <Input {...a} autoFocus maxLength={NAME_MAX} value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>

        <Field label={t('sip.loginReadonlyLabel')} hint={t('sip.loginReadonlyHint')}>
          {(a) => <Input {...a} mono readOnly value={number.trim() || t('sip.loginPending')} />}
        </Field>

        <SipPasswordField
          password={password} onChange={setPassword} onRegenerate={() => setPassword(generateSipPassword(number.trim()))}
          issue={passwordIssue} serverError={errorField === 'password' ? errorMessage : undefined}
          label={t('password.label')} hint={t('password.hint')}
        />

        <button
          type="button" onClick={() => setAdvancedOpen((v) => !v)}
          className="flex items-center gap-1.5 self-start text-sm font-medium text-brand hover:underline"
          aria-expanded={advancedOpen}
        >
          <ChevronDown aria-hidden className={cn('size-4 transition-transform duration-fast', advancedOpen && 'rotate-180')} />
          {t('createModal.advancedToggle')}
        </button>
        {advancedOpen && (
          <div className="flex flex-col gap-4 rounded-md border border-line bg-surface-2/40 p-3">
            <Toggle checked={webrtc} onCheckedChange={setWebrtc} label={t('webrtc.label')} description={t('webrtc.desc')} />
            {errorField === 'codecs' && <p className="text-sm text-danger">{errorMessage}</p>}
            <RecordingSelect direction="in" value={recordingIn} onChange={setRecordingIn} />
            <RecordingSelect direction="out" value={recordingOut} onChange={setRecordingOut} />
            <CallSettingsFields
              calls={calls.state} setDnd={calls.setDnd} setForwardAlways={calls.setForwardAlways} setForwardBusy={calls.setForwardBusy}
              setPickupGroup={calls.setPickupGroup} setOutboundAllowed={calls.setOutboundAllowed} setOutboundCallerid={calls.setOutboundCallerid}
              errorField={errorField} errorMessage={errorMessage}
            />
          </div>
        )}
      </div>
    </Modal>
  );
}

/** Qo'ng'iroq maydonlari (forward/pickup/chiquvchi) oʻz ichida alohida xato banner koʻrsatadi — bu yerda qaytarilmasin. */
const EDIT_FIELD_LEVEL_ERRORS = ['forward_always', 'forward_busy', 'pickup_group', 'outbound_callerid', 'codecs'];

function showsGenericEditError(stale: boolean, errorField: string | undefined, errorMessage: string | undefined): boolean {
  return !stale && !!errorMessage && !EDIT_FIELD_LEVEL_ERRORS.includes(errorField ?? '');
}

function confirmDiscardEdit(dirty: boolean, confirmMessage: string): boolean {
  return !dirty || window.confirm(confirmMessage);
}

function CodecsFieldError({ errorField, errorMessage }: { errorField?: string; errorMessage?: string }) {
  if (errorField !== 'codecs') return null;
  return <p className="text-sm text-danger">{errorMessage}</p>;
}

function EditExtensionDrawer({
  ext, onClose, onSubmit, pending, errorField, errorMessage, stale, onReloadStale, onFollowMeSaved, onSecretChanged,
}: {
  ext: Extension;
  onClose: () => void;
  onSubmit: (payload: UpdateExtensionPayload) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
  stale: boolean;
  onReloadStale: () => void;
  /** Follow Me ham ichki raqam yozuvini yangilaydi — tahrir oynasi eski `updated_at` bilan `stale` olmasin. */
  onFollowMeSaved: (updatedAt: string) => void;
  /** Parol almashtirilgach yangi SIP maʼlumotlarini koʻrsatish uchun. */
  onSecretChanged: (sip: SipCredentials) => void;
}) {
  const { t } = useTranslation('extensions');
  const [name, setName] = useState(ext.name);
  const [enabled, setEnabled] = useState(ext.enabled);
  const [webrtc, setWebrtc] = useState(ext.webrtc);
  const [recordingIn, setRecordingIn] = useState<RecordingPolicy>(ext.recording_in);
  const [recordingOut, setRecordingOut] = useState<RecordingPolicy>(ext.recording_out);
  const calls = useCallSettings(callSettingsFromExtension(ext));

  const fields = { name, enabled, webrtc, recordingIn, recordingOut, calls: calls.state };
  const dirty = editExtensionDirty(fields, ext);
  const valid = editExtensionValid(fields);

  const submit = () => {
    if (!valid) return;
    onSubmit(updateExtensionPayload(fields, ext));
  };

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      onAttemptClose={() => confirmDiscardEdit(dirty, t('editDrawer.confirmDiscard'))}
      title={t('editDrawer.title', { number: ext.number })}
      description={ext.contact ?? t('editDrawer.noPhone')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!dirty || !valid} onClick={submit}>
            {t('save')}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {stale && (
          <div className="flex flex-col gap-2 rounded-md border border-danger/30 bg-danger-soft px-3 py-2.5 text-sm text-on-danger-soft">
            <p>{errorMessage}</p>
            <Button size="sm" variant="secondary" onClick={onReloadStale}>{t('editDrawer.reloadList')}</Button>
          </div>
        )}
        {showsGenericEditError(stale, errorField, errorMessage) && (
          <p className="text-sm text-danger">{errorMessage}</p>
        )}
        <Field label={t('field.name')} required hint={t('field.nameHint', { max: NAME_MAX })}>
          {(a) => <Input {...a} maxLength={NAME_MAX} value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Toggle checked={enabled} onCheckedChange={setEnabled} label={t('field.enabled')} description={t('field.enabledDesc')} />
        <Toggle checked={webrtc} onCheckedChange={setWebrtc} label={t('webrtc.label')} description={t('webrtc.desc')} />
        <RecordingSelect direction="in" value={recordingIn} onChange={setRecordingIn} />
        <RecordingSelect direction="out" value={recordingOut} onChange={setRecordingOut} />
        <CodecsFieldError errorField={errorField} errorMessage={errorMessage} />

        <div className="flex flex-col gap-4 border-t border-line pt-4">
          <p className="mb-1 flex items-center gap-1.5 text-sm font-medium text-fg"><BellOff aria-hidden className="size-4 text-brand" /> {t('calls.title')}</p>
          <CallSettingsFields
            calls={calls.state} setDnd={calls.setDnd} setForwardAlways={calls.setForwardAlways} setForwardBusy={calls.setForwardBusy}
            setPickupGroup={calls.setPickupGroup} setOutboundAllowed={calls.setOutboundAllowed} setOutboundCallerid={calls.setOutboundCallerid}
            errorField={errorField} errorMessage={errorMessage}
          />
        </div>

        <ChangePasswordSection ext={ext} onChanged={onSecretChanged} />
        <FollowMeSection target={ext.id} onSaved={onFollowMeSaved} className="border-t border-line pt-4" />
        <VoicemailSection ext={ext} />
        <DevicesSection ext={ext} />
      </div>
    </Drawer>
  );
}

/** Ichki raqam ovozli pochtaga ega bo'lmasa — PIN so'rab yoqish; bo'lsa — holati va `/voicemail`ga havola. */
function VoicemailSection({ ext }: { ext: Extension }) {
  const { t } = useTranslation('extensions');
  const toast = useToast();
  const { data } = useVoicemailBoxes({ extension_id: ext.id });
  const createM = useCreateVoicemailBox();
  const [enableOpen, setEnableOpen] = useState(false);
  const [pin, setPin] = useState('');
  const box = data?.items[0];

  const submit = () => {
    if (!PIN_RE.test(pin)) return;
    createM.mutate({ extension_id: ext.id, pin }, {
      onSuccess: () => { setEnableOpen(false); setPin(''); toast({ kind: 'success', title: t('voicemail.configured') }); },
      onError: (e) => toast({ kind: 'error', title: t('toast.deleteFailed'), description: e.message }),
    });
  };

  return (
    <div className="border-t border-line pt-4">
      <p className="mb-2 flex items-center gap-1.5 text-sm font-medium text-fg"><Voicemail aria-hidden className="size-4 text-brand" /> {t('voicemail.title')}</p>
      {box ? (
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="success">{t('voicemail.configured')}</Badge>
          {box.counts.new > 0 && <Badge tone="accent"><Mail aria-hidden className="size-3" /> {t('voicemail.newMessages', { count: box.counts.new })}</Badge>}
          <Link to="/voicemail" className="text-sm text-brand hover:underline">{t('voicemail.openLink')}</Link>
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <Badge tone="neutral">{t('voicemail.notConfigured')}</Badge>
          <Button size="sm" variant="secondary" onClick={() => setEnableOpen(true)}>{t('voicemail.enable')}</Button>
        </div>
      )}

      <Modal
        open={enableOpen}
        onOpenChange={(v) => { setEnableOpen(v); if (!v) setPin(''); }}
        title={t('voicemail.enableModalTitle')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setEnableOpen(false)}>{t('cancel')}</Button>
            <Button variant="primary" loading={createM.isPending} disabled={!PIN_RE.test(pin)} onClick={submit}>{t('voicemail.enable')}</Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted">{t('voicemail.enableModalBody')}</p>
          <Field label={t('voicemail.pinLabel')} required hint={t('voicemail.pinHint')}>
            {(a) => <Input {...a} mono inputMode="numeric" maxLength={8} autoFocus value={pin} onChange={(e) => setPin(e.target.value)} />}
          </Field>
        </div>
      </Modal>
    </div>
  );
}

/** Ichki raqamga biriktirilgan apparatlar (M4a) — roʻyxat shu yerda, toʻliq boshqarish `/devices`da. */
function DevicesSection({ ext }: { ext: Extension }) {
  const { t } = useTranslation('extensions');
  const canManageDevices = useCanEdit('extensions');
  const { data } = useDevices({ extension_id: ext.id });
  const [addOpen, setAddOpen] = useState(false);
  const items = data?.items ?? [];

  return (
    <div className="border-t border-line pt-4">
      <p className="mb-2 flex items-center gap-1.5 text-sm font-medium text-fg"><Smartphone aria-hidden className="size-4 text-brand" /> {t('devices.title')}</p>
      {items.length > 0 ? (
        <div className="flex flex-col gap-2">
          {items.map((d) => (
            <div key={d.id} className="flex flex-wrap items-center gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2">
              <span className="num text-sm text-muted">{d.mac}</span>
              <span className="text-sm text-muted">{d.vendor} {d.model}</span>
              <DeviceStatusBadge status={d.status} />
            </div>
          ))}
        </div>
      ) : (
        <Badge tone="neutral">{t('devices.empty')}</Badge>
      )}
      <div className="mt-2 flex items-center gap-3">
        {canManageDevices && <Button size="sm" variant="secondary" onClick={() => setAddOpen(true)}>{t('devices.add')}</Button>}
        <Link to="/devices" className="text-sm text-brand hover:underline">{t('devices.openLink')}</Link>
      </div>

      {canManageDevices && <CreateDeviceModal open={addOpen} onClose={() => setAddOpen(false)} fixedExtensionId={ext.id} />}
    </div>
  );
}
