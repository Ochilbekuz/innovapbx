import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Copy, FileText, Grid3x3, Pencil, Plus, RotateCw, ShieldAlert, Smartphone, Trash2, X,
} from 'lucide-react';
import {
  useAssignDiscoveredDevice, useCreateDevice, useDeleteDevice, useDeleteDiscoveredDevice, useDeviceConfig,
  useDeviceKeys, useDeviceModels, useDevices, useDiscoveredDevices, useExtensions, useProvisioningSettings,
  useResyncDevice, useRotateProvisioningToken, useUpdateDevice, useUpdateDeviceKeys,
} from '@/api/queries';
import { apiErrorMessage } from '@/api/errors';
import {
  DEVICE_VENDORS, type Device, type DeviceKey, type DeviceKeyType, type DeviceVendor, type DiscoveredDevice,
} from '@/api/types';
import { formatDateTimeShort } from '@/lib/time';
import { Button } from '@/ui/Button';
import { Modal } from '@/ui/Dialog';
import { ConfirmDeleteModal } from '@/ui/ConfirmDeleteModal';
import { Field, Input, Select } from '@/ui/Field';
import { Badge, type Tone } from '@/ui/Status';
import { DataTable, queryState, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';
import { OtherFormError, StaleBanner, useMutationError } from '@/screens/integrations/shared';
import {
  addKeyRow, assignModalDescription, assignPayload, canSubmitAssign, createDevicePayload, createDeviceValid,
  currentExtensionId, deviceModelOptions, editDevicePayload, effectiveVendor, emptyForm, extensionOptions,
  keyTypeOptions, keysLimitFor, keysModalTitle, macFieldError, macValid, modelsForVendor, normalizeKeysForSubmit,
  removeKeyRow, updateKeyRow, useAssignForm, useEditDeviceForm, useKeysForm,
} from './deviceForms';
import { closeOnOpenChange, fieldError, itemsOrEmpty, otherFieldError } from '@/lib/formHelpers';
import { copyText } from '@/lib/browser';

const STATUS_TONE: Record<Device['status'], Tone> = { never: 'neutral', provisioned: 'info', registered: 'success', stale_config: 'warning' };
const KEY_TYPES: DeviceKeyType[] = ['blf', 'speed_dial', 'line', 'park', 'dnd', 'none'];

/** Provizioning manzil kartasi: URL, DHCP option 66, vendor boʻyicha qoʻlda kiritish qoʻllanmasi va token almashtirish. */
function ProvisioningCard({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('devices');
  const toast = useToast();
  const { data } = useProvisioningSettings();
  const rotateM = useRotateProvisioningToken();
  const [confirmOpen, setConfirmOpen] = useState(false);

  const copy = () => {
    void copyText(data?.url ?? '');
    toast({ kind: 'success', title: t('copied') });
  };

  const rotate = () => {
    rotateM.mutate(undefined, {
      onSuccess: () => { toast({ kind: 'success', title: t('provisioning.rotated') }); setConfirmOpen(false); },
    });
  };

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-line bg-surface p-4 shadow-card">
      <div className="flex items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-accent-soft text-on-accent-soft [&_svg]:size-4.5">
          <Smartphone aria-hidden />
        </span>
        <div>
          <h3 className="font-display text-base font-semibold">{t('provisioning.title')}</h3>
          <p className="mt-0.5 max-w-xl text-sm text-muted">{t('provisioning.desc')}</p>
        </div>
      </div>

      <Field label={t('provisioning.urlLabel')}>
        {(a) => (
          <Input
            {...a} readOnly mono value={data?.url ?? ''}
            trailing={<Button size="sm" variant="ghost" iconOnly icon={<Copy />} aria-label={t('copy')} onClick={copy} />}
          />
        )}
      </Field>

      <p className="text-sm text-muted">
        <span className="font-medium text-fg">{t('provisioning.dhcpLabel')}:</span> <span className="num">{data?.url ?? ''}</span>
        <br />{t('provisioning.dhcpHint')}
      </p>

      <div>
        <p className="mb-1.5 text-sm font-medium text-fg">{t('provisioning.instructionsTitle')}</p>
        <dl className="flex flex-col gap-2 text-sm text-muted">
          {DEVICE_VENDORS.map((v) => (
            <div key={v}>
              <dt className="font-medium capitalize text-fg">{v}</dt>
              <dd>{t(`provisioning.steps.${v}`)}</dd>
            </div>
          ))}
        </dl>
      </div>

      {canManage && (
        <div>
          <Button variant="secondary" onClick={() => setConfirmOpen(true)}>{t('provisioning.rotateToken')}</Button>
        </div>
      )}

      <Modal
        size="sm"
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={t('provisioning.rotateConfirmTitle')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmOpen(false)}>{t('cancel')}</Button>
            <Button variant="danger" loading={rotateM.isPending} onClick={rotate}>{t('provisioning.rotateConfirm')}</Button>
          </>
        }
      >
        <p className="flex items-start gap-1.5 text-sm text-danger">
          <ShieldAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />
          {t('provisioning.rotateConfirmBody')}
        </p>
      </Modal>
    </div>
  );
}

/** «Topilgan qurilma»ni ichki raqamga biriktirish modali. */
function AssignDiscoveredModal({ device, onClose }: { device: DiscoveredDevice | null; onClose: () => void }) {
  const { t } = useTranslation('devices');
  const toast = useToast();
  const { data: extensionsData } = useExtensions({ size: 200 });
  const { data: modelsData } = useDeviceModels();
  const assignM = useAssignDiscoveredDevice();
  const { state, setExtensionId, setModel, setLabel, reset } = useAssignForm(device);
  const { field: errorField, message: errorMessage, stale } = useMutationError(assignM.error);

  const models = modelsForVendor(itemsOrEmpty(modelsData), effectiveVendor(device));
  const canSubmit = canSubmitAssign(device, state);

  const close = () => { assignM.reset(); reset(); onClose(); };
  const submit = () => {
    if (!device || !canSubmit) return;
    assignM.mutate({ mac: device.mac, payload: assignPayload(state) }, {
      onSuccess: () => { toast({ kind: 'success', title: t('discovered.assigned') }); close(); },
    });
  };

  return (
    <Modal
      size="sm"
      open={!!device}
      onOpenChange={(v) => closeOnOpenChange(v, close)}
      title={t('discovered.assignModalTitle')}
      description={assignModalDescription(t, device)}
      footer={
        <>
          <Button variant="ghost" onClick={close}>{t('cancel')}</Button>
          <Button variant="primary" loading={assignM.isPending} disabled={!canSubmit} onClick={submit}>{t('discovered.assign')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <StaleBanner stale={stale} message={errorMessage} />
        <Field label={t('discovered.extensionLabel')} error={fieldError(errorField, 'extension_id', errorMessage)}>
          {(a) => (
            <Select
              {...a} value={state.extensionId} onValueChange={setExtensionId}
              placeholder={t('discovered.extensionPlaceholder')}
              options={extensionOptions(itemsOrEmpty(extensionsData))}
            />
          )}
        </Field>
        <Field label={t('form.model')} error={fieldError(errorField, 'model', errorMessage)}>
          {(a) => <Select {...a} value={state.model} onValueChange={setModel} options={deviceModelOptions(models)} />}
        </Field>
        <Field label={t('discovered.labelField')} hint={t('discovered.labelHint')}>
          {(a) => <Input {...a} value={state.label} onChange={(e) => setLabel(e.target.value)} />}
        </Field>
        <OtherFormError message={otherFieldError(errorMessage, stale, errorField, ['extension_id', 'model'])} />
      </div>
    </Modal>
  );
}

/** «Topilgan qurilmalar» — roʻyxatda yoʻq MAC'dan kelgan provizioning soʻrovlari; ichki raqamga biriktirish yoki eʼtiborsiz qoldirish. */
function DiscoveredSection({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('devices');
  const { data } = useDiscoveredDevices();
  const deleteM = useDeleteDiscoveredDevice();
  const [assigning, setAssigning] = useState<DiscoveredDevice | null>(null);
  const items = data?.items ?? [];
  if (items.length === 0) return null;

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-accent/30 bg-accent-soft/40 p-4">
      <div>
        <p className="font-medium text-fg">{t('discovered.banner', { count: items.length })}</p>
        <p className="text-sm text-muted">{t('discovered.desc')}</p>
      </div>
      <div className="flex flex-col gap-2">
        {items.map((d) => (
          <div key={d.mac} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line bg-surface px-3 py-2">
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <span className="num font-medium text-fg">{d.mac}</span>
              <span className="text-muted">{d.vendor ?? '?'} {d.model ?? ''}</span>
              <span className="num text-muted">{d.ip}</span>
              <span className="text-muted">{formatDateTimeShort(d.last_seen_at)}</span>
            </div>
            {canManage && (
              <div className="flex gap-1.5">
                <Button size="sm" variant="secondary" onClick={() => setAssigning(d)}>{t('discovered.assign')}</Button>
                <Button
                  size="sm" variant="ghost" iconOnly icon={<X />} aria-label={t('discovered.ignore')}
                  onClick={() => deleteM.mutate(d.mac)}
                />
              </div>
            )}
          </div>
        ))}
      </div>
      <AssignDiscoveredModal device={assigning} onClose={() => setAssigning(null)} />
    </div>
  );
}

export function DeviceStatusBadge({ status }: { status: Device['status'] }) {
  const { t } = useTranslation('devices');
  return <Badge tone={STATUS_TONE[status]}>{t(`status.${status}`)}</Badge>;
}

/** Ichki raqam maydoni — faqat `fixedExtensionId` berilmaganda koʻrsatiladi. */
function ExtensionField({
  extensionId, error, extensions, onChange,
}: { extensionId: string; error: string | undefined; extensions: { id: string; number: string; name: string; webrtc: boolean }[]; onChange: (v: string) => void }) {
  const { t } = useTranslation('devices');
  return (
    <Field label={t('form.extension')} hint={t('form.extensionHint')} error={error}>
      {(a) => <Select {...a} value={extensionId} onValueChange={onChange} options={extensionOptions(extensions)} />}
    </Field>
  );
}

/**
 * Yangi apparat qoʻshish — MAC/vendor/model `UpdateDevicePayload`da oʻzgarmas, shu sabab tahrirlashdan alohida forma.
 * `fixedExtensionId` berilsa (ichki raqam sahifasidagi «Apparatlar» blokidan chaqirilganda) — ichki raqam maydoni berkitiladi.
 */
export function CreateDeviceModal({ open, onClose, fixedExtensionId }: { open: boolean; onClose: () => void; fixedExtensionId?: string }) {
  const { t } = useTranslation('devices');
  const toast = useToast();
  const createM = useCreateDevice();
  const { data: modelsData } = useDeviceModels();
  const { data: extensionsData } = useExtensions({ size: 200 });
  const [form, setForm] = useState(() => emptyForm(fixedExtensionId));
  const { field: errorField, message: errorMessage, stale } = useMutationError(createM.error);

  const close = () => { createM.reset(); setForm(emptyForm(fixedExtensionId)); onClose(); };
  const models = modelsForVendor(itemsOrEmpty(modelsData), form.vendor);
  const macOk = macValid(form.mac);
  const valid = createDeviceValid(form, macOk);

  const submit = () => {
    if (!valid) return;
    createM.mutate(createDevicePayload(form), { onSuccess: () => { toast({ kind: 'success', title: t('toast.created') }); close(); } });
  };

  return (
    <Modal
      open={open}
      onOpenChange={(v) => closeOnOpenChange(v, close)}
      title={t('form.createTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={close}>{t('cancel')}</Button>
          <Button variant="primary" loading={createM.isPending} disabled={!valid} onClick={submit}>{t('save')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <StaleBanner stale={stale} message={errorMessage} />
        <Field label={t('form.mac')} required hint={t('form.macHint')} error={macFieldError(errorField, errorMessage, form.mac, macOk, t('form.macHint'))}>
          {(a) => <Input {...a} autoFocus mono value={form.mac} onChange={(e) => setForm((p) => ({ ...p, mac: e.target.value }))} />}
        </Field>
        <Field label={t('form.vendor')} error={fieldError(errorField, 'vendor', errorMessage)}>
          {(a) => (
            <Select
              {...a} value={form.vendor}
              onValueChange={(v) => setForm((p) => ({ ...p, vendor: v as DeviceVendor, model: '' }))}
              options={DEVICE_VENDORS.map((v) => ({ value: v, label: v }))}
            />
          )}
        </Field>
        <Field label={t('form.model')} error={fieldError(errorField, 'model', errorMessage)}>
          {(a) => <Select {...a} value={form.model} onValueChange={(v) => setForm((p) => ({ ...p, model: v }))} options={deviceModelOptions(models)} />}
        </Field>
        {!fixedExtensionId && (
          <ExtensionField
            extensionId={form.extensionId} error={fieldError(errorField, 'extension_id', errorMessage)}
            extensions={itemsOrEmpty(extensionsData)} onChange={(v) => setForm((p) => ({ ...p, extensionId: v }))}
          />
        )}
        <Field label={t('form.label')} hint={t('form.labelHint')}>
          {(a) => <Input {...a} value={form.label} onChange={(e) => setForm((p) => ({ ...p, label: e.target.value }))} />}
        </Field>
        <OtherFormError message={otherFieldError(errorMessage, stale, errorField, ['mac', 'vendor', 'model', 'extension_id'])} />
      </div>
    </Modal>
  );
}

/** Apparatni tahrirlash — yorliq, biriktirilgan ichki raqam, yoqilgan/oʻchirilgan holati. */
function EditDeviceModal({ device, onClose }: { device: Device | null; onClose: () => void }) {
  const { t } = useTranslation('devices');
  const toast = useToast();
  const updateM = useUpdateDevice();
  const { data: extensionsData } = useExtensions({ size: 200 });
  const { state, setLabel, setExtensionId, setEnabled } = useEditDeviceForm(device);
  const { field: errorField, message: errorMessage, stale } = useMutationError(updateM.error);

  const close = () => { updateM.reset(); onClose(); };
  const submit = () => {
    if (!device) return;
    updateM.mutate(
      { id: device.id, payload: editDevicePayload(state, device) },
      { onSuccess: () => { toast({ kind: 'success', title: t('saved') }); close(); } },
    );
  };

  return (
    <Modal
      open={!!device}
      onOpenChange={(v) => closeOnOpenChange(v, close)}
      title={t('form.editTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={close}>{t('cancel')}</Button>
          <Button variant="primary" loading={updateM.isPending} onClick={submit}>{t('save')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <StaleBanner stale={stale} message={errorMessage} />
        <Field label={t('form.label')} hint={t('form.labelHint')}>
          {(a) => <Input {...a} autoFocus value={state.label} onChange={(e) => setLabel(e.target.value)} />}
        </Field>
        <Field label={t('form.extension')} hint={t('form.extensionHint')} error={fieldError(errorField, 'extension_id', errorMessage)}>
          {(a) => (
            <Select
              {...a} value={state.extensionId} onValueChange={setExtensionId}
              options={extensionOptions(itemsOrEmpty(extensionsData), currentExtensionId(device))}
            />
          )}
        </Field>
        <Toggle checked={state.enabled} onCheckedChange={setEnabled} label={t('form.enabled')} description={t('form.enabledDesc')} />
        <OtherFormError message={otherFieldError(errorMessage, stale, errorField, ['extension_id'])} />
      </div>
    </Modal>
  );
}

/** Bitta BLF/dastur tugmasi qatori — qiymat/yorliq `??` fallback'lari shu kichik komponentda. */
function KeyRow({
  row, onChange, onRemove,
}: { row: DeviceKey; onChange: (patch: Partial<DeviceKey>) => void; onRemove: () => void }) {
  const { t } = useTranslation('devices');
  return (
    <div className="flex items-center gap-2">
      <span className="num w-5 shrink-0 text-sm text-muted">{row.idx}</span>
      <Select
        className="w-40 shrink-0" value={row.type} onValueChange={(v) => onChange({ type: v as DeviceKeyType })}
        options={keyTypeOptions(t, KEY_TYPES)}
      />
      <Input
        mono className="w-32 shrink-0" placeholder={t('keysModal.valuePlaceholder')} value={row.value ?? ''}
        onChange={(e) => onChange({ value: e.target.value })}
      />
      <Input
        placeholder={t('keysModal.labelPlaceholder')} value={row.label ?? ''}
        onChange={(e) => onChange({ label: e.target.value })}
      />
      <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('keysModal.removeKey')} onClick={onRemove} />
    </div>
  );
}

/** BLF/dastur tugmalari tahrirlovchisi — model qoʻllab-quvvatlaydigan tugmalar soni bilan cheklangan. */
function KeysModal({ device, onClose }: { device: Device | null; onClose: () => void }) {
  const { t } = useTranslation('devices');
  const toast = useToast();
  const deviceId = device?.id ?? '';
  const keysQ = useDeviceKeys(deviceId);
  const { data: modelsData } = useDeviceModels();
  const updateM = useUpdateDeviceKeys();
  const { rows, setRows, reset } = useKeysForm(device, keysQ.data?.items);
  const { message: errorMessage, stale } = useMutationError(updateM.error);

  const limit = keysLimitFor(itemsOrEmpty(modelsData), device);

  const close = () => { updateM.reset(); reset(); onClose(); };
  const updateRow = (i: number, patch: Partial<DeviceKey>) => setRows((prev) => updateKeyRow(prev, i, patch));
  const addRow = () => setRows((prev) => addKeyRow(prev, limit));
  const removeRow = (i: number) => setRows((prev) => removeKeyRow(prev, i));

  const submit = () => {
    if (!device) return;
    updateM.mutate({ id: device.id, payload: { keys: normalizeKeysForSubmit(rows) } }, {
      onSuccess: () => { toast({ kind: 'success', title: t('toast.keysSaved') }); close(); },
    });
  };

  return (
    <Modal
      open={!!device}
      onOpenChange={(v) => closeOnOpenChange(v, close)}
      title={keysModalTitle(t, device)}
      description={t('keysModal.desc', { limit })}
      footer={
        <>
          <Button variant="ghost" onClick={close}>{t('cancel')}</Button>
          <Button variant="primary" loading={updateM.isPending} onClick={submit}>{t('save')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <StaleBanner stale={stale} message={errorMessage} />
        {rows.length === 0 && <p className="text-sm text-muted">—</p>}
        {rows.map((r, i) => (
          <KeyRow key={i} row={r} onChange={(patch) => updateRow(i, patch)} onRemove={() => removeRow(i)} />
        ))}
        {rows.length < limit && (
          <div><Button size="sm" variant="secondary" icon={<Plus />} onClick={addRow}>{t('keysModal.addKey')}</Button></div>
        )}
        <OtherFormError message={otherFieldError(errorMessage, stale, undefined, [])} />
      </div>
    </Modal>
  );
}

function ConfigModal({ device, onClose }: { device: Device | null; onClose: () => void }) {
  const { t } = useTranslation('devices');
  const { data } = useDeviceConfig(device?.id ?? '', !!device);
  return (
    <Modal
      open={!!device}
      onOpenChange={(v) => closeOnOpenChange(v, onClose)}
      title={data ? t('configModal.title', { filename: data.filename }) : ''}
      footer={<Button variant="primary" onClick={onClose}>{t('close')}</Button>}
    >
      <div className="flex flex-col gap-3">
        <p className="text-sm text-muted">{t('configModal.maskedNotice')}</p>
        <pre className="num max-h-80 overflow-auto whitespace-pre-wrap rounded-md border border-line bg-surface-2/60 p-3 text-xs">{data?.content ?? ''}</pre>
      </div>
    </Modal>
  );
}

function DeleteDeviceModal({ device, onClose }: { device: Device | null; onClose: () => void }) {
  const { t } = useTranslation('devices');
  const toast = useToast();
  const deleteM = useDeleteDevice();
  return (
    <ConfirmDeleteModal
      open={!!device}
      onClose={onClose}
      loading={deleteM.isPending}
      onConfirm={() => device && deleteM.mutate(device.id, {
        onSuccess: () => { toast({ kind: 'success', title: t('toast.deleted') }); onClose(); },
      })}
      title={t('deleteModal.title')}
      body={t('deleteModal.body', { label: device?.label ?? device?.mac ?? '', mac: device?.mac ?? '' })}
      cancelLabel={t('cancel')}
      deleteLabel={t('delete')}
    />
  );
}

type RowHandlers = {
  onEdit: (d: Device) => void; onKeys: (d: Device) => void; onConfig: (d: Device) => void; onDelete: (d: Device) => void; onResync: (d: Device) => void;
};

function DeviceRowActions({ device, canManage, handlers }: { device: Device; canManage: boolean; handlers: RowHandlers }) {
  const { t } = useTranslation('devices');
  return (
    <div className="flex justify-end gap-1">
      <Button size="sm" variant="ghost" iconOnly icon={<FileText />} aria-label={t('table.viewConfig')} onClick={() => handlers.onConfig(device)} />
      {canManage && (
        <>
          <Button size="sm" variant="ghost" iconOnly icon={<Grid3x3 />} aria-label={t('table.keys')} onClick={() => handlers.onKeys(device)} />
          <Button size="sm" variant="ghost" iconOnly icon={<RotateCw />} aria-label={t('table.resync')} onClick={() => handlers.onResync(device)} />
          <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('table.edit')} onClick={() => handlers.onEdit(device)} />
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('delete')} onClick={() => handlers.onDelete(device)} />
        </>
      )}
    </div>
  );
}

function deviceColumns(
  t: (k: string, o?: Record<string, unknown>) => string, canManage: boolean, handlers: RowHandlers,
): Column<Device>[] {
  return [
    { key: 'status', header: t('table.column.status'), cell: (r) => <DeviceStatusBadge status={r.status} /> },
    { key: 'mac', header: t('table.column.mac'), sortValue: (r) => r.mac, cell: (r) => <span className="num text-sm">{r.mac}</span> },
    { key: 'model', header: t('table.column.model'), cell: (r) => <span className="text-sm text-muted">{r.vendor} {r.model}</span> },
    {
      key: 'extension', header: t('table.column.extension'), sortValue: (r) => r.extension?.number ?? '',
      cell: (r) => (
        <span className={r.extension ? 'text-sm' : 'text-sm text-muted'}>
          {r.extension ? `${r.extension.number} — ${r.extension.name}` : t('table.noExtension')}
        </span>
      ),
    },
    { key: 'ip', header: t('table.column.ip'), cell: (r) => <span className="num text-sm text-muted">{r.last_ip ?? t('table.never')}</span> },
    { key: 'firmware', header: t('table.column.firmware'), cell: (r) => <span className="num text-sm text-muted">{r.firmware ?? t('table.never')}</span> },
    { key: 'last_seen_at', header: t('table.column.lastSeen'), cell: (r) => <span className="num text-sm text-muted">{r.last_seen_at ? formatDateTimeShort(r.last_seen_at) : t('table.never')}</span> },
    { key: 'actions', header: '', align: 'right', cell: (r) => <DeviceRowActions device={r} canManage={canManage} handlers={handlers} /> },
  ];
}

/** Apparatlar tabi — provizioning manzili, topilgan qurilmalar va apparatlar roʻyxati/CRUD (shartnoma §3-4). */
export function DevicesTab({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('devices');
  const toast = useToast();
  const { data, isLoading, isError, refetch } = useDevices({});
  const resyncM = useResyncDevice();
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<Device | null>(null);
  const [keysFor, setKeysFor] = useState<Device | null>(null);
  const [configFor, setConfigFor] = useState<Device | null>(null);
  const [deleting, setDeleting] = useState<Device | null>(null);

  const columns = deviceColumns(t, canManage, {
    onEdit: setEditing,
    onKeys: setKeysFor,
    onConfig: setConfigFor,
    onDelete: setDeleting,
    onResync: (d) => resyncM.mutate(d.id, {
      onSuccess: () => toast({ kind: 'success', title: t('toast.resyncOk') }),
      onError: (e) => toast({ kind: 'error', title: t('toast.resyncFailed'), description: apiErrorMessage(e) }),
    }),
  });

  return (
    <div className="flex flex-col gap-5">
      <ProvisioningCard canManage={canManage} />
      <DiscoveredSection canManage={canManage} />

      <div>
        <div className="mb-3 flex items-start justify-between gap-3">
          <div />
          {canManage && <Button data-testid="device-create" icon={<Plus />} onClick={() => setCreateOpen(true)}>{t('table.create')}</Button>}
        </div>
        <DataTable
          caption={t('table.caption')}
          rows={data?.items ?? []}
          columns={columns}
          rowId={(r) => r.id}
          searchText={(r) => `${r.mac} ${r.model} ${r.label ?? ''} ${r.extension?.number ?? ''}`}
          state={queryState(isLoading, isError)}
          onRetry={() => void refetch()}
          empty={{ title: t('table.empty.title'), body: t('table.empty.body') }}
        />
      </div>

      <CreateDeviceModal open={createOpen} onClose={() => setCreateOpen(false)} />
      <EditDeviceModal device={editing} onClose={() => setEditing(null)} />
      <KeysModal device={keysFor} onClose={() => setKeysFor(null)} />
      <ConfigModal device={configFor} onClose={() => setConfigFor(null)} />
      <DeleteDeviceModal device={deleting} onClose={() => setDeleting(null)} />
    </div>
  );
}
