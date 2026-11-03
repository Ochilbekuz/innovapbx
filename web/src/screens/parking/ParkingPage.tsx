import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ShieldAlert } from 'lucide-react';
import { useParkedCalls, useParkingSettings, useTargets, useUpdateParkingSettings } from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { ParkingCall, ParkingOnTimeout } from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { TARGET_KINDS, type Destination } from '@/domain/destination';
import { toCatalog } from '@/pbx/catalog';
import { DestinationPicker } from '@/pbx/DestinationPicker';
import { useToast } from '@/ui/Toast';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Field, Input, Select } from '@/ui/Field';
import { DataTable, type Column } from '@/ui/Table';

/** S26 — parkovka: lot sozlamalari + jonli parklangan qoʻngʻiroqlar roʻyxati (5s poll). */
export function ParkingPage() {
  const { t } = useTranslation('parking');
  const canManage = useCanEdit('routing');
  const { data: settings, isLoading, isError, refetch } = useParkingSettings();
  const { data: targetsData } = useTargets({ kind: TARGET_KINDS.join(',') });
  const catalog = useMemo(() => toCatalog(targetsData?.items ?? []), [targetsData]);
  const { data: liveData } = useParkedCalls();
  const toast = useToast();

  const updateM = useUpdateParkingSettings();

  return (
    <AppShellPage title={t('title')}>
      {!canManage && (
        <p className="mb-3 flex items-center gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2 text-sm text-muted">
          <ShieldAlert aria-hidden className="size-4 shrink-0" />
          {t('readOnlyNotice')}
        </p>
      )}

      {settings && (
        <SettingsForm
          settings={settings}
          catalog={catalog}
          canManage={canManage}
          pending={updateM.isPending}
          errorField={isApiError(updateM.error) ? updateM.error.field : undefined}
          errorMessage={isApiError(updateM.error) ? updateM.error.message : undefined}
          onSubmit={(payload) => updateM.mutate({ ...payload, updated_at: settings.updated_at }, {
            onSuccess: () => { toast({ kind: 'success', title: t('toast.saved') }); void refetch(); },
          })}
        />
      )}
      {isLoading && <p className="text-sm text-muted">…</p>}
      {isError && <p className="text-sm text-danger">—</p>}

      <LiveParked data={liveData?.items ?? []} />
    </AppShellPage>
  );
}

function SettingsForm({
  settings, catalog, canManage, onSubmit, pending, errorField, errorMessage,
}: {
  settings: NonNullable<ReturnType<typeof useParkingSettings>['data']>;
  catalog: ReturnType<typeof toCatalog>;
  canManage: boolean;
  onSubmit: (payload: { lot_number: string; first_slot: number; slot_count: number; timeout_s: number; on_timeout: ParkingOnTimeout; timeout_target_id: string | null; moh_class_id: string | null }) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('parking');
  const [lotNumber, setLotNumber] = useState(settings.lot_number);
  const [firstSlot, setFirstSlot] = useState(String(settings.first_slot));
  const [slotCount, setSlotCount] = useState(String(settings.slot_count));
  const [timeoutS, setTimeoutS] = useState(String(settings.timeout_s));
  const [onTimeout, setOnTimeout] = useState<ParkingOnTimeout>(settings.on_timeout);
  const [timeoutTarget, setTimeoutTarget] = useState<Destination | null>(
    settings.timeout_target ? { kind: settings.timeout_target.kind, targetId: settings.timeout_target.id } : null,
  );
  const [moh, setMoh] = useState(settings.moh_class_id ?? '');

  const valid = lotNumber.trim().length > 0 && Number(firstSlot) > 0 && Number(slotCount) > 0 && Number(timeoutS) > 0
    && (onTimeout === 'origin' || (!!timeoutTarget && timeoutTarget.kind !== 'external'));

  const submit = () => {
    if (!valid) return;
    onSubmit({
      lot_number: lotNumber.trim(), first_slot: Number(firstSlot), slot_count: Number(slotCount), timeout_s: Number(timeoutS),
      on_timeout: onTimeout, timeout_target_id: onTimeout === 'target' && timeoutTarget && timeoutTarget.kind !== 'external' ? timeoutTarget.targetId : null,
      moh_class_id: moh.trim() || null,
    });
  };

  return (
    <section className="mb-6 flex flex-col gap-4 rounded-md border border-line bg-surface p-4">
      <h2 className="text-lg font-semibold text-fg">{t('settingsTitle')}</h2>
      {errorMessage && !['lot_number', 'slot_count', 'timeout_s'].includes(errorField ?? '') && <p className="text-sm text-danger">{errorMessage}</p>}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t('form.lotNumberLabel')} hint={t('form.lotHint')} error={errorField === 'lot_number' ? errorMessage : undefined}>
          {(a) => <Input {...a} className="num" disabled={!canManage} value={lotNumber} onChange={(e) => setLotNumber(e.target.value)} />}
        </Field>
        <Field label={t('form.firstSlotLabel')}>
          {(a) => <Input {...a} type="number" className="num" disabled={!canManage} value={firstSlot} onChange={(e) => setFirstSlot(e.target.value)} />}
        </Field>
        <Field label={t('form.slotCountLabel')} error={errorField === 'slot_count' ? errorMessage : undefined}>
          {(a) => <Input {...a} type="number" className="num" disabled={!canManage} value={slotCount} onChange={(e) => setSlotCount(e.target.value)} />}
        </Field>
        <Field label={t('form.timeoutLabel')} error={errorField === 'timeout_s' ? errorMessage : undefined}>
          {(a) => <Input {...a} type="number" className="num" disabled={!canManage} value={timeoutS} onChange={(e) => setTimeoutS(e.target.value)} />}
        </Field>
        <Field label={t('form.onTimeoutLabel')}>
          {(a) => (
            <Select
              {...a}
              disabled={!canManage}
              value={onTimeout}
              onValueChange={(v) => setOnTimeout(v as ParkingOnTimeout)}
              options={[{ value: 'origin', label: t('form.onTimeoutOrigin') }, { value: 'target', label: t('form.onTimeoutTarget') }]}
            />
          )}
        </Field>
        <Field label={t('form.mohLabel')} hint={t('form.mohHint')}>
          {(a) => <Input {...a} disabled={!canManage} value={moh} onChange={(e) => setMoh(e.target.value)} />}
        </Field>
      </div>

      {onTimeout === 'target' && (
        <DestinationPicker label={t('form.timeoutTargetLabel')} required kinds={[...TARGET_KINDS]} value={timeoutTarget} onChange={setTimeoutTarget} catalog={catalog} disabled={!canManage} />
      )}

      {canManage && (
        <div className="flex justify-end">
          <Button variant="primary" loading={pending} disabled={!valid} onClick={submit}>{t('form.saveButton')}</Button>
        </div>
      )}
    </section>
  );
}

function LiveParked({ data }: { data: ParkingCall[] }) {
  const { t } = useTranslation('parking');
  const columns: Column<ParkingCall>[] = [
    { key: 'slot', header: t('column.slot'), cell: (c) => <span className="num font-medium">{c.slot}</span> },
    { key: 'caller', header: t('column.caller'), cell: (c) => <span className="num text-fg">{c.caller_name ? `${c.caller_name} (${c.caller_num})` : c.caller_num}</span> },
    { key: 'parkedBy', header: t('column.parkedBy'), cell: (c) => <span className="num text-muted">{c.parked_by}</span> },
    { key: 'elapsed', header: t('column.elapsed'), cell: (c) => <span className="num text-muted">{t('secondsShort', { count: c.parked_seconds })}</span> },
    { key: 'timeout', header: t('column.timeout'), cell: (c) => <span className="num text-muted">{t('secondsShort', { count: Math.max(0, c.timeout_s - c.parked_seconds) })}</span> },
  ];

  return (
    <section className="flex flex-col gap-2">
      <div>
        <h2 className="text-lg font-semibold text-fg">{t('liveTitle')}</h2>
        <p className="text-sm text-muted">{t('liveHint')}</p>
      </div>
      <DataTable
        caption={t('liveTitle')}
        rows={data}
        columns={columns}
        rowId={(c) => String(c.slot)}
        searchText={(c) => `${c.caller_num} ${c.caller_name ?? ''} ${c.parked_by}`}
        state="ready"
        empty={{ title: t('liveEmpty'), body: '' }}
      />
    </section>
  );
}
