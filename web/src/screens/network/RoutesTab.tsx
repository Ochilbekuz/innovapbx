// "Statik marshrutlar" tab — qo'shish/tahrirlash/o'chirish + joriy (live) marshrutlar jadvali (faqat o'qish). M8 §5.
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus } from 'lucide-react';
import type { NetworkFieldError, NetworkInterface, NetworkLiveRoute } from '@/api/types';
import { isValidCidr, isValidIPv4 } from '@/lib/validators';
import { Button } from '@/ui/Button';
import { Field, Input, Select } from '@/ui/Field';
import { Modal } from '@/ui/Dialog';
import { closeOnOpenChange } from '@/lib/formHelpers';
import { fieldErrorIn, newRouteDraft } from './networkDraft';
import type { RouteDraft } from './networkDraft';

function RouteCell({ value, fallback }: { value: string; fallback: string }) {
  return <td className="py-2 pr-3 text-muted">{value || fallback}</td>;
}

function RouteRow({
  route, hasError, locked, onEdit, onDelete,
}: { route: RouteDraft; hasError: boolean; locked: boolean; onEdit: () => void; onDelete: () => void }) {
  const { t } = useTranslation('network');
  return (
    <tr className="num border-b border-line last:border-0">
      <td className="py-2 pl-4 pr-3 text-fg">
        <span className="inline-flex items-center gap-1.5">
          {route.destination}
          {hasError && <span aria-hidden className="size-1.5 rounded-full bg-danger" />}
        </span>
      </td>
      <RouteCell value={route.gateway} fallback="—" />
      <RouteCell value={route.interface} fallback={t('routes.interfaceAny')} />
      <RouteCell value={route.metric} fallback="—" />
      <td className="py-2 pr-4">
        <div className="flex justify-end gap-2">
        <Button size="sm" variant="secondary" disabled={locked} onClick={onEdit}>{t('routes.editButton')}</Button>
        <Button size="sm" variant="danger-ghost" disabled={locked} onClick={onDelete}>{t('routes.deleteButton')}</Button>
        </div>
      </td>
    </tr>
  );
}

/** `routeIndex` null bo'lsa (yangi marshrut) server xatosi yo'q — faqat mavjud marshrut uchun dot-path bor. */
function destinationFieldError(draft: RouteDraft, serverErrors: NetworkFieldError[], prefix: string | null, t: (k: string) => string): string | undefined {
  if (draft.destination && !isValidCidr(draft.destination)) return t('validation.cidrInvalid');
  return prefix ? fieldErrorIn(serverErrors, `${prefix}.destination`) : undefined;
}

function gatewayRouteError(draft: RouteDraft, serverErrors: NetworkFieldError[], prefix: string | null, t: (k: string) => string): string | undefined {
  if (draft.gateway && !isValidIPv4(draft.gateway)) return t('validation.ipInvalid');
  return prefix ? fieldErrorIn(serverErrors, `${prefix}.gateway`) : undefined;
}

function canSaveRoute(draft: RouteDraft, destErr: string | undefined, gwErr: string | undefined): boolean {
  return !!draft.destination && !destErr && !gwErr && (!!draft.gateway || !!draft.interface);
}

function RouteEditModal({
  open, initial, ifaceNames, serverErrors, routeIndex, onSave, onClose,
}: {
  open: boolean; initial: RouteDraft; ifaceNames: string[]; serverErrors: NetworkFieldError[]; routeIndex: number | null;
  onSave: (next: RouteDraft) => void; onClose: () => void;
}) {
  const { t } = useTranslation('network');
  const [draft, setDraft] = useState(initial);
  const prefix = routeIndex != null ? `routes.${routeIndex}` : null;

  const destErr = destinationFieldError(draft, serverErrors, prefix, t);
  const gwErr = gatewayRouteError(draft, serverErrors, prefix, t);
  const canSave = canSaveRoute(draft, destErr, gwErr);

  return (
    <Modal
      open={open}
      onOpenChange={(v) => closeOnOpenChange(v, onClose)}
      title={routeIndex != null ? t('routes.modalTitleEdit') : t('routes.modalTitleAdd')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('routes.cancel')}</Button>
          <Button variant="primary" disabled={!canSave} onClick={() => { onSave(draft); onClose(); }}>{t('routes.save')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label={t('routes.destinationLabel')} error={destErr}>
          {(a) => (
            <Input {...a} mono placeholder={t('routes.destinationPlaceholder')} value={draft.destination} onChange={(e) => setDraft((d) => ({ ...d, destination: e.target.value }))} />
          )}
        </Field>
        <Field label={t('routes.gatewayLabel')} error={gwErr}>
          {(a) => <Input {...a} mono value={draft.gateway} onChange={(e) => setDraft((d) => ({ ...d, gateway: e.target.value }))} />}
        </Field>
        <Field label={t('routes.interfaceLabel')}>
          {(a) => (
            <Select
              {...a}
              value={draft.interface || '__any__'}
              onValueChange={(v) => setDraft((d) => ({ ...d, interface: v === '__any__' ? '' : v }))}
              options={[{ value: '__any__', label: t('routes.interfaceAny') }, ...ifaceNames.map((n) => ({ value: n, label: n }))]}
            />
          )}
        </Field>
        <Field label={t('routes.metricLabel')} aside={t('routes.metricOptional')}>
          {(a) => <Input {...a} type="number" mono min={0} value={draft.metric} onChange={(e) => setDraft((d) => ({ ...d, metric: e.target.value }))} />}
        </Field>
      </div>
    </Modal>
  );
}

function LiveRoutesTable({ routes }: { routes: NetworkLiveRoute[] }) {
  const { t } = useTranslation('network');
  return (
    <details className="rounded-lg border border-line bg-surface shadow-card">
      <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium text-fg">{t('routes.liveTitle')}</summary>
      <table className="num w-full border-t border-line text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs text-muted">
            <th className="px-4 py-2 font-medium">{t('routes.column.destination')}</th>
            <th className="px-0 py-2 font-medium">{t('routes.column.gateway')}</th>
            <th className="px-0 py-2 font-medium">{t('routes.column.interface')}</th>
            <th className="px-0 py-2 font-medium">{t('routes.column.metric')}</th>
          </tr>
        </thead>
        <tbody>
          {routes.map((r, i) => (
            <tr key={i} className="border-b border-line px-4 last:border-0">
              <td className="px-4 py-2 text-fg">{r.destination}</td>
              <td className="py-2 text-muted">{r.gateway || '—'}</td>
              <td className="py-2 text-muted">{r.interface || '—'}</td>
              <td className="py-2 text-muted">{r.metric ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

function resolveEditingRoute(routes: RouteDraft[], editingIndex: number | 'new' | null): RouteDraft | null {
  if (editingIndex === 'new') return newRouteDraft();
  if (typeof editingIndex === 'number') return routes[editingIndex] ?? null;
  return null;
}

function applyRouteSave(routes: RouteDraft[], editingIndex: number | 'new' | null, next: RouteDraft): RouteDraft[] {
  if (editingIndex === 'new') return [...routes, next];
  if (typeof editingIndex === 'number') return routes.map((r, i) => (i === editingIndex ? next : r));
  return routes;
}

export function RoutesTab({
  routes, liveRoutes, interfaces, errors, locked, onChange,
}: {
  routes: RouteDraft[];
  liveRoutes: NetworkLiveRoute[];
  interfaces: NetworkInterface[];
  errors: NetworkFieldError[];
  locked: boolean;
  onChange: (next: RouteDraft[]) => void;
}) {
  const { t } = useTranslation('network');
  const [editingIndex, setEditingIndex] = useState<number | 'new' | null>(null);
  const editingValue = resolveEditingRoute(routes, editingIndex);
  const save = (next: RouteDraft) => onChange(applyRouteSave(routes, editingIndex, next));

  return (
    <div className="flex flex-col gap-4">
      <div className="overflow-x-auto rounded-lg border border-line bg-surface shadow-card">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs text-muted">
              <th className="px-4 py-2 font-medium">{t('routes.column.destination')}</th>
              <th className="px-0 py-2 font-medium">{t('routes.column.gateway')}</th>
              <th className="px-0 py-2 font-medium">{t('routes.column.interface')}</th>
              <th className="px-0 py-2 font-medium">{t('routes.column.metric')}</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {routes.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-sm text-muted">{t('routes.empty')}</td></tr>
            ) : (
              routes.map((route, i) => (
                <RouteRow
                  key={route.key}
                  route={route}
                  hasError={errors.some((e) => e.field.startsWith(`routes.${i}`))}
                  locked={locked}
                  onEdit={() => setEditingIndex(i)}
                  onDelete={() => onChange(routes.filter((_, j) => j !== i))}
                />
              ))
            )}
          </tbody>
        </table>
        <div className="flex justify-end border-t border-line px-4 py-2.5">
          <Button size="sm" variant="secondary" icon={<Plus />} disabled={locked} onClick={() => setEditingIndex('new')}>{t('routes.addButton')}</Button>
        </div>
      </div>
      <LiveRoutesTable routes={liveRoutes} />
      {editingValue && (
        <RouteEditModal
          open
          initial={editingValue}
          ifaceNames={interfaces.map((i) => i.name)}
          serverErrors={errors}
          routeIndex={typeof editingIndex === 'number' ? editingIndex : null}
          onSave={save}
          onClose={() => setEditingIndex(null)}
        />
      )}
    </div>
  );
}
