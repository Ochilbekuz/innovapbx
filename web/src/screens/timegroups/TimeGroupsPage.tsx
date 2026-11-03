import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CalendarPlus, Moon, Pencil, Plus, ShieldAlert, Sun, SunMoon, Trash2 } from 'lucide-react';
import {
  useCreateHoliday, useCreateTimeCondition, useCreateTimeGroup, useDeleteHoliday, useDeleteTimeCondition, useDeleteTimeGroup,
  useHolidays, useImportUzHolidays, useOverrideTimeCondition, useTargets, useTimeConditions, useTimeGroups, useUpdateHoliday,
  useUpdateTimeCondition, useUpdateTimeGroup,
} from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { Holiday, TimeCondition, TimeConditionOverride, TimeGroup } from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { applyToast } from '@/lib/applyToast';
import { formatDateShort } from '@/lib/time';
import { usagesOf } from '@/lib/usageError';
import { resolveDestination, type Catalog, type Destination } from '@/domain/destination';
import { emptyWeek, isRangeOrderValid, rangesToWeek, summarizeWeek, weekToRanges, type Week } from '@/domain/week';
import { DestinationPicker } from '@/pbx/DestinationPicker';
import { toCatalog } from '@/pbx/catalog';
import { NumberField } from '@/pbx/NumberField';
import { UsageList } from '@/pbx/UsageList';
import { WeekGrid } from '@/pbx/WeekGrid';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Drawer, Modal } from '@/ui/Dialog';
import { Field, Input } from '@/ui/Field';
import { Badge } from '@/ui/Status';
import { Tabs } from '@/ui/Tabs';
import { DataTable, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';
import { dayLabels } from '@/pbx/domainText';

const NAME_MAX = 60;

/** S08 — ish vaqti: guruhlar (haftalik setka), bayramlar, va shartlar (DID qayerga tushishini belgilaydi). */
export function TimeGroupsPage() {
  const { t } = useTranslation('timegroups');
  const canManage = useCanEdit('routing');
  return (
    <AppShellPage title={t('title')}>
      {!canManage && (
        <p className="mb-3 flex items-center gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2 text-sm text-muted">
          <ShieldAlert aria-hidden className="size-4 shrink-0" />
          {t('readOnlyNotice')}
        </p>
      )}
      <Tabs
        label={t('tabsAriaLabel')}
        items={[
          { value: 'groups', label: t('tab.groups'), content: <TimeGroupsTab canManage={canManage} /> },
          { value: 'holidays', label: t('tab.holidays'), content: <HolidaysTab canManage={canManage} /> },
          { value: 'conditions', label: t('tab.conditions'), content: <TimeConditionsTab canManage={canManage} /> },
        ]}
      />
    </AppShellPage>
  );
}

// ─────────────────────────── Guruhlar ───────────────────────────

function TimeGroupsTab({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('timegroups');
  const { data, isLoading, isError, refetch } = useTimeGroups();
  const toast = useToast();
  const [editing, setEditing] = useState<TimeGroup | 'new' | null>(null);
  const [deleting, setDeleting] = useState<TimeGroup | null>(null);
  const [deleteErr, setDeleteErr] = useState<ReturnType<typeof usagesOf> | null>(null);

  const createM = useCreateTimeGroup();
  const updateM = useUpdateTimeGroup();
  const deleteM = useDeleteTimeGroup();
  const close = () => { setEditing(null); createM.reset(); updateM.reset(); };
  const mutation = editing === 'new' ? createM : updateM;

  const columns: Column<TimeGroup>[] = [
    { key: 'name', header: t('groups.column.name'), sortValue: (r) => r.name, cell: (r) => <span className="block max-w-[320px] truncate font-medium" title={r.name}>{r.name}</span> },
    { key: 'summary', header: t('groups.column.summary'), cell: (r) => <span className="text-sm text-muted">{summarizeWeek(rangesToWeek(r.ranges), dayLabels(t, 'short')).join(' · ') || t('groups.emptySummary')}</span> },
    {
      key: 'actions', header: '', align: 'right', cell: (r) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('groups.editAriaLabel', { name: r.name })} disabled={!canManage} onClick={() => setEditing(r)} />
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('groups.deleteAriaLabel', { name: r.name })} disabled={!canManage} onClick={() => setDeleting(r)} />
        </div>
      ),
    },
  ];

  return (
    <>
      <DataTable
        caption={t('groups.caption')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(r) => r.id}
        searchText={(r) => r.name}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        onRowOpen={canManage ? (r) => setEditing(r) : undefined}
        empty={{ title: t('groups.empty.title'), body: t('groups.empty.body'), action: canManage ? <Button size="sm" onClick={() => setEditing('new')}>{t('groups.empty.action')}</Button> : undefined }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setEditing('new')}>{t('groups.newGroup')}</Button> : undefined}
      />

      {editing && (
        <TimeGroupDrawer
          group={editing === 'new' ? undefined : editing}
          pending={mutation.isPending}
          errorMessage={isApiError(mutation.error) ? mutation.error.message : undefined}
          onClose={close}
          onSubmit={(payload) => {
            if (editing === 'new') {
              createM.mutate(payload, { onSuccess: (res) => { close(); toast(applyToast(res.apply, t('groups.toast.added'))); } });
            } else {
              updateM.mutate({ id: editing.id, payload: { ...payload, updated_at: editing.updated_at } }, {
                onSuccess: (res) => { close(); toast(applyToast(res.apply, t('groups.toast.saved'))); },
              });
            }
          }}
        />
      )}

      <Modal
        open={!!deleting}
        onOpenChange={(v) => !v && (setDeleting(null), setDeleteErr(null))}
        title={deleting ? t('groups.deleteModalTitle', { name: deleting.name }) : ''}
        description={deleteErr ? undefined : t('deleteModal.cannotUndo')}
        footer={
          <>
            <Button variant="ghost" onClick={() => { setDeleting(null); setDeleteErr(null); }}>{t('cancel')}</Button>
            {!deleteErr && (
              <Button
                variant="danger" loading={deleteM.isPending}
                onClick={() => deleting && deleteM.mutate(deleting.id, {
                  onSuccess: () => { toast({ kind: 'success', title: t('groups.toast.deleted', { name: deleting.name }) }); setDeleting(null); },
                  onError: (e) => { if (isApiError(e) && e.code === 'in_use') setDeleteErr(usagesOf(e)); else toast({ kind: 'error', title: t('groups.toast.deleteFailed'), description: e.message }); },
                })}
              >
                {t('delete')}
              </Button>
            )}
          </>
        }
      >
        {deleteErr ? (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-danger">{t('deleteModal.usagePrefix', { name: deleting?.name })}</p>
            <UsageList usages={deleteErr} />
          </div>
        ) : (
          <p className="text-sm text-muted">{t('deleteModal.body', { name: deleting?.name })}</p>
        )}
      </Modal>
    </>
  );
}

function TimeGroupDrawer({
  group, onClose, onSubmit, pending, errorMessage,
}: { group?: TimeGroup; onClose: () => void; onSubmit: (payload: { name: string; ranges: ReturnType<typeof weekToRanges> }) => void; pending: boolean; errorMessage?: string }) {
  const { t } = useTranslation('timegroups');
  const [name, setName] = useState(group?.name ?? '');
  const [week, setWeek] = useState<Week>(() => (group ? rangesToWeek(group.ranges) : emptyWeek()));
  const ranges = useMemo(() => weekToRanges(week), [week]);
  const valid = name.trim().length > 0 && isRangeOrderValid(ranges);

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={group ? t('groups.drawer.editTitle', { name: group.name }) : t('groups.drawer.newTitle')}
      description={t('groups.drawer.description')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={() => onSubmit({ name: name.trim(), ranges })}>{group ? t('save') : t('add')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errorMessage && <p className="text-sm text-danger">{errorMessage}</p>}
        <Field label={t('groups.drawer.nameLabel')} required hint={t('nameHint', { max: NAME_MAX })}>
          {(a) => <Input {...a} autoFocus maxLength={NAME_MAX} value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <WeekGrid value={week} onChange={setWeek} label={t('groups.drawer.weekLabel')} />
      </div>
    </Drawer>
  );
}

// ─────────────────────────── Bayramlar ───────────────────────────

function HolidaysTab({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('timegroups');
  const { data, isLoading, isError, refetch } = useHolidays();
  const toast = useToast();
  const [editing, setEditing] = useState<Holiday | 'new' | null>(null);
  const [deleting, setDeleting] = useState<Holiday | null>(null);

  const createM = useCreateHoliday();
  const updateM = useUpdateHoliday();
  const deleteM = useDeleteHoliday();
  const importM = useImportUzHolidays();
  const close = () => { setEditing(null); createM.reset(); updateM.reset(); };
  const mutation = editing === 'new' ? createM : updateM;

  const columns: Column<Holiday>[] = [
    { key: 'name', header: t('holidays.column.name'), sortValue: (r) => r.name, cell: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'day', header: t('holidays.column.day'), sortValue: (r) => r.day, cell: (r) => <span className="num text-muted">{formatDateShort(r.day)}</span> },
    { key: 'recurring', header: t('holidays.column.recurring'), cell: (r) => <Badge tone={r.recurring_yearly ? 'accent' : 'neutral'}>{r.recurring_yearly ? t('holidays.yes') : t('holidays.notRecurring')}</Badge> },
    {
      key: 'actions', header: '', align: 'right', cell: (r) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('holidays.editAriaLabel', { name: r.name })} disabled={!canManage} onClick={() => setEditing(r)} />
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('holidays.deleteAriaLabel', { name: r.name })} disabled={!canManage} onClick={() => setDeleting(r)} />
        </div>
      ),
    },
  ];

  return (
    <>
      <DataTable
        caption={t('holidays.caption')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(r) => r.id}
        searchText={(r) => `${r.name} ${r.day}`}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        onRowOpen={canManage ? (r) => setEditing(r) : undefined}
        empty={{ title: t('holidays.empty.title'), body: t('holidays.empty.body'), action: canManage ? <Button size="sm" onClick={() => setEditing('new')}>{t('holidays.empty.action')}</Button> : undefined }}
        toolbar={canManage && (
          <div className="flex gap-2">
            <Button
              size="sm" variant="secondary" icon={<CalendarPlus />} loading={importM.isPending}
              onClick={() => importM.mutate({ year: new Date().getFullYear() }, {
                onSuccess: (res) => toast({
                  kind: 'success', title: t('holidays.toast.imported', { count: res.created }),
                  description: res.skipped.length ? t('holidays.toast.skipped', { days: res.skipped.join(', ') }) : t('holidays.toast.allAdded'),
                }),
              })}
            >
              {t('holidays.importUz')}
            </Button>
            <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setEditing('new')}>{t('holidays.newHoliday')}</Button>
          </div>
        )}
      />

      {editing && (
        <HolidayModal
          holiday={editing === 'new' ? undefined : editing}
          pending={mutation.isPending}
          errorMessage={isApiError(mutation.error) ? mutation.error.message : undefined}
          onClose={close}
          onSubmit={(payload) => {
            if (editing === 'new') createM.mutate(payload, { onSuccess: (res) => { close(); toast(applyToast(res.apply, t('holidays.toast.added'))); } });
            else updateM.mutate({ id: editing.id, payload }, { onSuccess: (res) => { close(); toast(applyToast(res.apply, t('holidays.toast.saved'))); } });
          }}
        />
      )}

      <Modal
        open={!!deleting}
        onOpenChange={(v) => !v && setDeleting(null)}
        title={deleting ? t('holidays.deleteModalTitle', { name: deleting.name }) : ''}
        description={t('deleteModal.cannotUndo')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleting(null)}>{t('cancel')}</Button>
            <Button
              variant="danger" loading={deleteM.isPending}
              onClick={() => deleting && deleteM.mutate(deleting.id, {
                onSuccess: () => { toast({ kind: 'success', title: t('holidays.toast.deleted', { name: deleting.name }) }); setDeleting(null); },
                onError: (e) => { toast({ kind: 'error', title: t('holidays.toast.deleteFailed'), description: e.message }); setDeleting(null); },
              })}
            >
              {t('delete')}
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted">{t('deleteModal.body', { name: deleting?.name })}</p>
      </Modal>
    </>
  );
}

function HolidayModal({
  holiday, onClose, onSubmit, pending, errorMessage,
}: { holiday?: Holiday; onClose: () => void; onSubmit: (payload: { name: string; day: string; recurring_yearly: boolean }) => void; pending: boolean; errorMessage?: string }) {
  const { t } = useTranslation('timegroups');
  const [name, setName] = useState(holiday?.name ?? '');
  const [day, setDay] = useState(holiday?.day ?? '');
  const [yearly, setYearly] = useState(holiday?.recurring_yearly ?? true);
  const valid = name.trim().length > 0 && /^\d{4}-\d{2}-\d{2}$/.test(day);

  return (
    <Modal
      open
      onOpenChange={(v) => !v && onClose()}
      title={holiday ? t('holidays.modal.editTitle', { name: holiday.name }) : t('holidays.modal.newTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={() => onSubmit({ name: name.trim(), day, recurring_yearly: yearly })}>{holiday ? t('save') : t('add')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errorMessage && <p className="text-sm text-danger">{errorMessage}</p>}
        <Field label={t('holidays.modal.nameLabel')} required hint={t('nameHint', { max: NAME_MAX })}>
          {(a) => <Input {...a} autoFocus maxLength={NAME_MAX} value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Field label={t('holidays.modal.dayLabel')} required hint={t('holidays.modal.dayHint')}>
          {(a) => <Input {...a} type="date" value={day} onChange={(e) => setDay(e.target.value)} />}
        </Field>
        <Toggle checked={yearly} onCheckedChange={setYearly} label={t('holidays.modal.yearlyLabel')} description={t('holidays.modal.yearlyDesc')} />
      </div>
    </Modal>
  );
}

// ─────────────────────────── Shartlar ───────────────────────────

function TimeConditionsTab({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('timegroups');
  const overrideLabel: Record<TimeConditionOverride, string> = {
    auto: t('conditions.override.auto'), force_open: t('conditions.override.force_open'), force_closed: t('conditions.override.force_closed'),
  };
  const { data, isLoading, isError, refetch } = useTimeConditions();
  const { data: groups } = useTimeGroups();
  const { data: targets } = useTargets({ kind: 'extension,ring_group,queue,ivr,conference,hangup,busy,announcement,misc' });
  const toast = useToast();
  const [editing, setEditing] = useState<TimeCondition | 'new' | null>(null);
  const [deleting, setDeleting] = useState<TimeCondition | null>(null);
  const [deleteErr, setDeleteErr] = useState<ReturnType<typeof usagesOf> | null>(null);

  const createM = useCreateTimeCondition();
  const updateM = useUpdateTimeCondition();
  const deleteM = useDeleteTimeCondition();
  const overrideM = useOverrideTimeCondition();
  const close = () => { setEditing(null); createM.reset(); updateM.reset(); };
  const mutation = editing === 'new' ? createM : updateM;
  const catalog: Catalog = useMemo(() => toCatalog(targets?.items ?? []), [targets]);

  const columns: Column<TimeCondition>[] = [
    { key: 'name', header: t('conditions.column.name'), sortValue: (r) => r.name, cell: (r) => <span className="block max-w-[260px] truncate font-medium" title={r.name}>{r.name}</span> },
    { key: 'number', header: t('conditions.column.number'), cell: (r) => <span className="num text-muted">{r.number ?? '—'}</span> },
    { key: 'group', header: t('conditions.column.group'), cell: (r) => <span className="text-sm">{r.time_group.name}</span> },
    { key: 'state', header: t('conditions.column.state'), cell: (r) => <Badge tone={r.state_now === 'open' ? 'success' : 'neutral'}>{r.state_now === 'open' ? t('conditions.stateOpen') : t('conditions.stateClosed')}</Badge> },
    { key: 'override', header: t('conditions.column.override'), cell: (r) => <Badge tone={r.override === 'auto' ? 'neutral' : 'warning'}>{overrideLabel[r.override]}</Badge> },
    {
      key: 'actions', header: '', align: 'right', cell: (r) => {
        const overrideIcon = r.override === 'force_closed'
          ? <Sun />
          : r.override === 'force_open'
            ? <SunMoon />
            : <Moon />;
        return (
        <div className="flex justify-end gap-1">
          <Button
            size="sm" variant="ghost" iconOnly disabled={!canManage} loading={overrideM.isPending && overrideM.variables?.id === r.id}
            icon={overrideIcon}
            aria-label={r.override === 'auto' ? t('conditions.toggleToNightAriaLabel', { name: r.name }) : t('conditions.toggleToAutoAriaLabel', { name: r.name })}
            onClick={() => overrideM.mutate({ id: r.id, payload: { override: r.override === 'auto' ? 'force_closed' : 'auto' } }, { onSuccess: (res) => toast(applyToast(res.apply)) })}
          />
          <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('conditions.editAriaLabel', { name: r.name })} disabled={!canManage} onClick={() => setEditing(r)} />
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('conditions.deleteAriaLabel', { name: r.name })} disabled={!canManage} onClick={() => setDeleting(r)} />
        </div>
        );
      },
    },
  ];

  return (
    <>
      <DataTable
        caption={t('conditions.caption')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(r) => r.id}
        searchText={(r) => `${r.name} ${r.number ?? ''} ${r.time_group.name}`}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        onRowOpen={canManage ? (r) => setEditing(r) : undefined}
        empty={{
          title: t('conditions.empty.title'), action: canManage ? <Button size="sm" disabled={!groups?.items.length} onClick={() => setEditing('new')}>{t('conditions.empty.action')}</Button> : undefined,
          body: groups?.items.length ? t('conditions.empty.bodyWithGroups') : t('conditions.empty.bodyNoGroups'),
        }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} disabled={!groups?.items.length} onClick={() => setEditing('new')}>{t('conditions.newCondition')}</Button> : undefined}
      />

      {editing && (
        <TimeConditionDrawer
          condition={editing === 'new' ? undefined : editing}
          groups={groups?.items ?? []}
          catalog={catalog}
          pending={mutation.isPending}
          errorField={isApiError(mutation.error) ? mutation.error.field : undefined}
          errorMessage={isApiError(mutation.error) ? mutation.error.message : undefined}
          onClose={close}
          onSubmit={(payload) => {
            if (editing === 'new') createM.mutate(payload, { onSuccess: (res) => { close(); toast(applyToast(res.apply, t('conditions.toast.added'))); } });
            else updateM.mutate({ id: editing.id, payload: { ...payload, updated_at: editing.updated_at } }, { onSuccess: (res) => { close(); toast(applyToast(res.apply, t('conditions.toast.saved'))); } });
          }}
        />
      )}

      <Modal
        open={!!deleting}
        onOpenChange={(v) => !v && (setDeleting(null), setDeleteErr(null))}
        title={deleting ? t('conditions.deleteModalTitle', { name: deleting.name }) : ''}
        footer={
          <>
            <Button variant="ghost" onClick={() => { setDeleting(null); setDeleteErr(null); }}>{t('cancel')}</Button>
            {!deleteErr && (
              <Button
                variant="danger" loading={deleteM.isPending}
                onClick={() => deleting && deleteM.mutate(deleting.id, {
                  onSuccess: () => { toast({ kind: 'success', title: t('conditions.toast.deleted', { name: deleting.name }) }); setDeleting(null); },
                  onError: (e) => { if (isApiError(e) && e.code === 'in_use') setDeleteErr(usagesOf(e)); else toast({ kind: 'error', title: t('conditions.toast.deleteFailed'), description: e.message }); },
                })}
              >
                {t('delete')}
              </Button>
            )}
          </>
        }
      >
        {deleteErr ? (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-danger">{t('conditions.deleteModalUsagePrefix', { name: deleting?.name })}</p>
            <UsageList usages={deleteErr} />
          </div>
        ) : (
          <p className="text-sm text-muted">{t('deleteModal.body', { name: deleting?.name })}</p>
        )}
      </Modal>
    </>
  );
}

type TcFormState = { name: string; number: string; timeGroupId: string; honorHolidays: boolean; open: Destination | null; closed: Destination | null; toggleCode: string };

function TimeConditionDrawer({
  condition, groups, catalog, onClose, onSubmit, pending, errorField, errorMessage,
}: {
  condition?: TimeCondition;
  groups: TimeGroup[];
  catalog: Catalog;
  onClose: () => void;
  onSubmit: (payload: { name: string; number: string | null; time_group_id: string; honor_holidays: boolean; open_target_id: string; closed_target_id: string; toggle_code: string | null }) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('timegroups');
  const [form, setForm] = useState<TcFormState>(() => ({
    name: condition?.name ?? '', number: condition?.number ?? '', timeGroupId: condition?.time_group.id ?? groups[0]?.id ?? '',
    honorHolidays: condition?.honor_holidays ?? true,
    open: condition ? { kind: condition.open_target.kind, targetId: condition.open_target.id } : null,
    closed: condition ? { kind: condition.closed_target.kind, targetId: condition.closed_target.id } : null,
    toggleCode: condition?.toggle_code ?? '',
  }));
  const set = <K extends keyof TcFormState>(k: K, v: TcFormState[K]) => setForm((f) => ({ ...f, [k]: v }));
  const openOk = resolveDestination(form.open, catalog).state === 'ok';
  const closedOk = resolveDestination(form.closed, catalog).state === 'ok';
  const valid = form.name.trim().length > 0 && !!form.timeGroupId && openOk && closedOk;

  const submit = () => {
    if (!valid || !form.open || !form.closed || form.open.kind === 'external' || form.closed.kind === 'external') return;
    onSubmit({
      name: form.name.trim(), number: form.number.trim() || null, time_group_id: form.timeGroupId, honor_holidays: form.honorHolidays,
      open_target_id: form.open.targetId, closed_target_id: form.closed.targetId, toggle_code: form.toggleCode.trim() || null,
    });
  };

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={condition ? t('conditions.drawer.editTitle', { name: condition.name }) : t('conditions.drawer.newTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={submit}>{condition ? t('save') : t('add')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errorMessage && errorField !== 'number' && errorField !== 'toggle_code' && <p className="text-sm text-danger">{errorMessage}</p>}
        <Field label={t('conditions.drawer.nameLabel')} required hint={t('nameHint', { max: NAME_MAX })}>
          {(a) => <Input {...a} autoFocus maxLength={NAME_MAX} value={form.name} onChange={(e) => set('name', e.target.value)} />}
        </Field>
        <NumberField value={form.number} onChange={(v) => set('number', v)} error={errorField === 'number' ? errorMessage : undefined} hint={t('conditions.drawer.numberHint')} />
        <Field label={t('conditions.drawer.groupLabel')} required>
          {({ id }) => (
            <select
              id={id}
              className="h-ctl-md w-full rounded-md border border-input bg-surface px-2.5 text-base text-fg shadow-inset"
              value={form.timeGroupId} onChange={(e) => set('timeGroupId', e.target.value)}
            >
              {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
            </select>
          )}
        </Field>
        <Toggle checked={form.honorHolidays} onCheckedChange={(v) => set('honorHolidays', v)} label={t('conditions.drawer.honorHolidaysLabel')} description={t('conditions.drawer.honorHolidaysDesc')} />
        <DestinationPicker label={t('conditions.drawer.openLabel')} required kinds={['extension', 'ring_group', 'queue', 'ivr', 'conference', 'hangup', 'busy', 'announcement', 'misc']} value={form.open} onChange={(d) => set('open', d)} catalog={catalog} />
        <DestinationPicker label={t('conditions.drawer.closedLabel')} required kinds={['extension', 'ring_group', 'queue', 'ivr', 'conference', 'hangup', 'busy', 'announcement', 'misc']} value={form.closed} onChange={(d) => set('closed', d)} catalog={catalog} />
        <Field
          label={t('conditions.drawer.toggleCodeLabel')} aside={t('conditions.drawer.toggleCodeAside')}
          hint={errorField === 'toggle_code' ? undefined : t('conditions.drawer.toggleCodeHint')}
          error={errorField === 'toggle_code' ? errorMessage : undefined}
        >
          {(a) => <Input {...a} mono placeholder="*21" value={form.toggleCode} onChange={(e) => set('toggleCode', e.target.value)} />}
        </Field>
      </div>
    </Drawer>
  );
}
