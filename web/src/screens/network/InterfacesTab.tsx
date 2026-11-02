// "Interfeyslar" tab — jadval + har bir interfeysni sozlash modali. M8 §5.
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { NetworkFieldError, NetworkInterface } from '@/api/types';
import { isValidCidr, isValidIPv4 } from '@/lib/validators';
import { Button } from '@/ui/Button';
import { Field, Input, Segmented } from '@/ui/Field';
import { Modal } from '@/ui/Dialog';
import { StatusPill, Badge } from '@/ui/Status';
import { closeOnOpenChange } from '@/lib/formHelpers';
import { displayMode, fieldErrorIn } from './networkDraft';
import type { InterfaceDraft, NetworkDraft } from './networkDraft';

/** `1000` → "1 Gbit/s", aks holda "100 Mbit/s" (M8 §5: Gbit formatida ko'rsatish). */
function formatSpeed(mbps: number | null, t: (k: string, v?: Record<string, unknown>) => string): string | null {
  if (mbps == null) return null;
  return mbps >= 1000 && mbps % 1000 === 0 ? t('interfaces.speedGbit', { gbit: mbps / 1000 }) : t('interfaces.speed', { mbps });
}

function isInterfaceOnline(iface: NetworkInterface): boolean {
  return iface.carrier && iface.oper_state === 'up';
}

/** Ulanish holati matni: "Ulangan · 1 Gbit/s" / "Uzilgan". */
function connectionLabel(online: boolean, speed: string | null, t: (k: string) => string): string {
  const base = online ? t('interfaces.connected') : t('interfaces.disconnected');
  return speed ? `${base} · ${speed}` : base;
}

function onlineStatus(online: boolean): 'online' | 'offline' {
  return online ? 'online' : 'offline';
}

function formatLiveAddresses(ipv4: string[], noAddressesLabel: string): string {
  return ipv4.join(', ') || noAddressesLabel;
}

function InterfaceAction({
  editable, locked, onEdit, t,
}: { editable: boolean; locked: boolean; onEdit: () => void; t: (k: string) => string }) {
  if (!editable) return <span className="text-xs text-muted">{t('interfaces.notEditable')}</span>;
  return <Button size="sm" variant="secondary" disabled={locked} onClick={onEdit}>{t('interfaces.editButton')}</Button>;
}

function ModeCell({ iface, draft, t }: { iface: NetworkInterface; draft: InterfaceDraft; t: (k: string) => string }) {
  const mode = displayMode(iface, draft);
  return mode ? <Badge tone="neutral">{t(`interfaces.mode.${mode}`)}</Badge> : <span className="text-muted">—</span>;
}

function InterfaceRow({
  iface, draft, hasError, locked, onEdit,
}: { iface: NetworkInterface; draft: InterfaceDraft; hasError: boolean; locked: boolean; onEdit: () => void }) {
  const { t } = useTranslation('network');
  const online = isInterfaceOnline(iface);
  const speed = formatSpeed(iface.speed_mbps, t);
  return (
    <tr className="border-b border-line last:border-0">
      <td className="py-2 pl-4 pr-3 font-medium text-fg">
        <span className="inline-flex items-center gap-1.5">
          {iface.name}
          {hasError && <span aria-hidden className="size-1.5 rounded-full bg-danger" />}
        </span>
      </td>
      <td className="py-2 pr-3">
        <StatusPill status={onlineStatus(online)}>{connectionLabel(online, speed, t)}</StatusPill>
      </td>
      <td className="py-2 pr-3"><ModeCell iface={iface} draft={draft} t={t} /></td>
      <td className="num py-2 pr-3 text-muted">{formatLiveAddresses(iface.live_ipv4, t('interfaces.noAddresses'))}</td>
      <td className="py-2 pr-4 text-right"><InterfaceAction editable={iface.editable} locked={locked} onEdit={onEdit} t={t} /></td>
    </tr>
  );
}

/** Statik rejimda CIDR shaklini tekshiradi, aks holda serverdan kelgan xatoga tushadi. */
function addressFieldError(draft: InterfaceDraft, serverErrors: NetworkFieldError[], prefix: string, t: (k: string) => string): string | undefined {
  if (draft.mode === 'static' && draft.address && !isValidCidr(draft.address)) return t('validation.cidrInvalid');
  return fieldErrorIn(serverErrors, `${prefix}.address`);
}

function gatewayFieldError(draft: InterfaceDraft, serverErrors: NetworkFieldError[], prefix: string, t: (k: string) => string): string | undefined {
  if (draft.mode === 'static' && draft.gateway && !isValidIPv4(draft.gateway)) return t('validation.ipInvalid');
  return fieldErrorIn(serverErrors, `${prefix}.gateway`);
}

function canSaveInterface(draft: InterfaceDraft, addressErr: string | undefined, gatewayErr: string | undefined): boolean {
  return draft.mode === 'dhcp' || (!!draft.address && !addressErr && !gatewayErr);
}

function InterfaceEditModal({
  open, iface, value, serverErrors, onSave, onClose,
}: {
  open: boolean; iface: NetworkInterface; value: InterfaceDraft; serverErrors: NetworkFieldError[];
  onSave: (next: InterfaceDraft) => void; onClose: () => void;
}) {
  const { t } = useTranslation('network');
  const [draft, setDraft] = useState(value);
  const prefix = `interfaces.${iface.name}`;

  const addressErr = addressFieldError(draft, serverErrors, prefix, t);
  const gatewayErr = gatewayFieldError(draft, serverErrors, prefix, t);
  const canSave = canSaveInterface(draft, addressErr, gatewayErr);

  return (
    <Modal
      open={open}
      onOpenChange={(v) => closeOnOpenChange(v, onClose)}
      title={t('interfaces.modalTitle', { name: iface.name })}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('interfaces.cancel')}</Button>
          <Button variant="primary" disabled={!canSave} onClick={() => { onSave({ ...draft, managed: true }); onClose(); }}>{t('interfaces.save')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label={t('interfaces.modeLabel')}>
          {() => (
            <Segmented
              value={draft.mode}
              onChange={(mode) => setDraft((d) => ({ ...d, mode }))}
              label={t('interfaces.modeLabel')}
              options={[{ value: 'dhcp', label: t('interfaces.mode.dhcp') }, { value: 'static', label: t('interfaces.mode.static') }]}
            />
          )}
        </Field>
        {draft.mode === 'static' && (
          <>
            <Field label={t('interfaces.addressLabel')} error={addressErr}>
              {(a) => (
                <Input {...a} mono placeholder={t('interfaces.addressPlaceholder')} value={draft.address} onChange={(e) => setDraft((d) => ({ ...d, address: e.target.value }))} />
              )}
            </Field>
            <Field label={t('interfaces.gatewayLabel')} aside={t('interfaces.gatewayOptional')} error={gatewayErr}>
              {(a) => (
                <Input {...a} mono placeholder={t('interfaces.gatewayPlaceholder')} value={draft.gateway} onChange={(e) => setDraft((d) => ({ ...d, gateway: e.target.value }))} />
              )}
            </Field>
          </>
        )}
        <Field label={t('interfaces.mtuLabel')}>
          {(a) => <Input {...a} type="number" mono min={0} placeholder={String(iface.mtu)} value={draft.mtu} onChange={(e) => setDraft((d) => ({ ...d, mtu: e.target.value }))} />}
        </Field>
        <div className="rounded-md border border-line bg-surface-2 px-3 py-2 text-sm">
          <p className="mb-1 text-muted">{t('interfaces.currentAddresses')}</p>
          <p className="num text-fg">{formatLiveAddresses(iface.live_ipv4, t('interfaces.noAddresses'))}</p>
        </div>
      </div>
    </Modal>
  );
}

export function InterfacesTab({
  interfaces, draft, errors, locked, onChangeInterface,
}: {
  interfaces: NetworkInterface[];
  draft: NetworkDraft;
  errors: NetworkFieldError[];
  locked: boolean;
  onChangeInterface: (name: string, next: InterfaceDraft) => void;
}) {
  const { t } = useTranslation('network');
  const [editing, setEditing] = useState<string | null>(null);
  const editingIface = interfaces.find((i) => i.name === editing);
  const editingDraft = draft.interfaces.find((i) => i.name === editing);

  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-surface shadow-card">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs text-muted">
            <th className="px-4 py-2 font-medium">{t('interfaces.column.name')}</th>
            <th className="px-0 py-2 font-medium">{t('interfaces.column.status')}</th>
            <th className="px-0 py-2 font-medium">{t('interfaces.column.mode')}</th>
            <th className="px-0 py-2 font-medium">{t('interfaces.column.address')}</th>
            <th className="px-4 py-2" />
          </tr>
        </thead>
        <tbody className="px-4">
          {interfaces.map((iface) => {
            const d = draft.interfaces.find((i) => i.name === iface.name);
            if (!d) return null;
            const hasError = errors.some((e) => e.field.startsWith(`interfaces.${iface.name}`));
            return <InterfaceRow key={iface.name} iface={iface} draft={d} hasError={hasError} locked={locked} onEdit={() => setEditing(iface.name)} />;
          })}
        </tbody>
      </table>
      {editingIface && editingDraft && (
        <InterfaceEditModal
          open
          iface={editingIface}
          value={editingDraft}
          serverErrors={errors}
          onSave={(next) => onChangeInterface(editingIface.name, next)}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}
