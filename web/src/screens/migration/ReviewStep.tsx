import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { TriangleAlert } from 'lucide-react';
import { MIGRATION_ACTIONS, MIGRATION_KINDS, type MigrationJob, type MigrationPatchAction, type MigrationPlanItem } from '@/api/types';
import { useMigrationIgnored, useMigrationPlan, useMigrationWarnings, useUpdateMigrationPlan } from '@/api/queries';
import { apiErrorMessage } from '@/api/errors';
import { useEnumText } from '@/lib/useEnumText';
import { Badge } from '@/ui/Status';
import { Button } from '@/ui/Button';
import { Select } from '@/ui/Field';
import { DataTable, queryState, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';
import { availablePatchActions, byKindRows, planActionTone, planItemKey } from './migrationForms';

/** Turlar bo'yicha jami/to'qnashuvlar kartalari. */
function ByKindCards({ summary }: { summary: MigrationJob['summary'] }) {
  const { t } = useTranslation('migration');
  const kindText = useEnumText('migration', 'kind', MIGRATION_KINDS);
  const rows = byKindRows(summary).filter((r) => r.total > 0);
  if (rows.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {rows.map((r) => (
        <div key={r.kind} className="flex min-w-32 flex-col gap-1 rounded-md border border-line bg-surface px-3 py-2">
          <span className="text-xs text-muted">{kindText[r.kind]}</span>
          <span className="num text-lg font-semibold text-fg">{r.total}</span>
          {r.conflicts > 0 && <Badge tone="warning">{t('review.conflictsBadge', { n: r.conflicts })}</Badge>}
        </div>
      ))}
    </div>
  );
}

/** Bitta reja qatorining amal ustuni: toʻqnashuv/yaratish/oʻtkazib-yuborish oʻrtasida almashtirish. */
function PlanRowActionCell({
  item, jobId, canManage,
}: { item: MigrationPlanItem; jobId: string; canManage: boolean }) {
  const { t } = useTranslation('migration');
  const toast = useToast();
  const patchM = useUpdateMigrationPlan();
  const actionText = useEnumText('migration', 'actionLabel', MIGRATION_ACTIONS);
  const options = availablePatchActions(item);

  const apply = (next: MigrationPatchAction) => patchM.mutate(
    { id: jobId, payload: { items: [{ kind: item.kind, source_ref: item.source_ref, action: next }] } },
    { onError: (e) => toast({ kind: 'error', title: t('review.table.patchFailedToast', { error: apiErrorMessage(e) }) }) },
  );

  return (
    <div className="flex items-center gap-1.5">
      <Badge tone={planActionTone(item.action)}>{actionText[item.action]}</Badge>
      {canManage && options.length > 0 && (
        <Select
          size="sm"
          value={undefined}
          placeholder={t('review.table.skipAction')}
          disabled={patchM.isPending}
          onValueChange={(v) => apply(v as MigrationPatchAction)}
          options={options.map((o) => ({
            value: o,
            label: o === 'skip' ? t('review.table.skipAction') : o === 'replace' ? t('review.table.replaceAction') : t('review.table.createAction'),
          }))}
        />
      )}
      {canManage && item.action === 'conflict' && !item.replaceable && (
        <span className="text-xs text-muted">{t('review.table.notReplaceable')}</span>
      )}
    </div>
  );
}

/** Reja jadvali: turi/amal bo'yicha filtr + qidiruv/saralash/sahifalash (`DataTable`). */
function PlanTable({ jobId, canManage }: { jobId: string; canManage: boolean }) {
  const { t } = useTranslation('migration');
  const kindText = useEnumText('migration', 'kind', MIGRATION_KINDS);
  const actionText = useEnumText('migration', 'actionLabel', MIGRATION_ACTIONS);
  const [kind, setKind] = useState<string | undefined>(undefined);
  const [action, setAction] = useState<string | undefined>(undefined);
  const planQ = useMigrationPlan(jobId, { page_size: 500 });
  const allItems = planQ.data?.items ?? [];
  const rows = allItems.filter((i) => (!kind || i.kind === kind) && (!action || i.action === action));

  const columns: Column<MigrationPlanItem>[] = [
    { key: 'kind', header: t('review.table.column.kind'), cell: (r) => kindText[r.kind], sortValue: (r) => kindText[r.kind] },
    { key: 'name', header: t('review.table.column.name'), cell: (r) => r.name, sortValue: (r) => r.name },
    { key: 'number', header: t('review.table.column.number'), cell: (r) => r.number ?? '—', sortValue: (r) => r.number ?? '' },
    { key: 'action', header: t('review.table.column.action'), cell: (r) => <PlanRowActionCell item={r} jobId={jobId} canManage={canManage} /> },
    { key: 'reason', header: t('review.table.column.reason'), cell: (r) => r.reason ?? '—' },
  ];

  return (
    <DataTable
      caption={t('review.table.caption')}
      rows={rows}
      columns={columns}
      rowId={planItemKey}
      searchText={(r) => `${r.name} ${r.number ?? ''} ${r.source_ref}`}
      state={queryState(planQ.isLoading, planQ.isError)}
      pageSize={10}
      toolbar={
        <div className="flex gap-2">
          <Select
            size="sm" value={kind} onValueChange={setKind} placeholder={t('review.table.filterKindPlaceholder')}
            options={MIGRATION_KINDS.map((k) => ({ value: k, label: kindText[k] }))}
          />
          <Select
            size="sm" value={action} onValueChange={setAction} placeholder={t('review.table.filterActionPlaceholder')}
            options={MIGRATION_ACTIONS.map((a) => ({ value: a, label: actionText[a] }))}
          />
        </div>
      }
    />
  );
}

function WarningsBlock({ jobId }: { jobId: string }) {
  const { t } = useTranslation('migration');
  const warningsQ = useMigrationWarnings(jobId);
  const items = warningsQ.data?.items ?? [];
  if (items.length === 0) return null;
  return (
    <div className="flex flex-col gap-1.5">
      <h3 className="text-sm font-semibold text-fg">{t('review.warningsTitle')}</h3>
      <ul className="flex flex-col gap-1">
        {items.map((w, i) => (
          <li key={`${w.code}-${i}`} className="flex items-start gap-1.5 text-sm text-muted">
            <TriangleAlert aria-hidden className="mt-0.5 size-3.5 shrink-0 text-warning" />
            {w.message}
          </li>
        ))}
      </ul>
    </div>
  );
}

function IgnoredBlock({ jobId }: { jobId: string }) {
  const { t } = useTranslation('migration');
  const ignoredQ = useMigrationIgnored(jobId);
  const items = ignoredQ.data?.items ?? [];
  if (items.length === 0) return null;
  return (
    <div className="flex flex-col gap-1.5">
      <h3 className="text-sm font-semibold text-fg">{t('review.ignoredTitle')}</h3>
      <ul className="flex flex-col gap-1 text-sm text-muted">
        {items.map((i, idx) => <li key={`${i.table}-${i.key}-${idx}`}>{i.table} · {i.key} — {i.reason}</li>)}
      </ul>
    </div>
  );
}

/**
 * Sehrgarning 3-bosqichi: turlar bo'yicha kartalar, reja jadvali (filtr bilan), zaif sirlar
 * (`rotate_weak_secrets` toggle — holati `ApplyStep`ga `rotateWeakSecrets` orqali ko'tariladi),
 * ogohlantirish/e'tiborsiz ro'yxatlar. `plan_stale` bo'lsa qayta tahlil banneri.
 */
export function ReviewStep({
  job, canManage, rotateWeakSecrets, onRotateWeakSecretsChange, onContinue,
}: {
  job: MigrationJob; canManage: boolean; rotateWeakSecrets: boolean; onRotateWeakSecretsChange: (v: boolean) => void;
  onContinue: () => void;
}) {
  const { t } = useTranslation('migration');
  const weakSecrets = job.summary?.weak_secrets ?? 0;

  return (
    <section data-testid="migration-review-step" className="flex flex-col gap-6">
      <h2 className="text-lg font-semibold text-fg">{t('review.title')}</h2>

      <div>
        <h3 className="mb-2 text-sm font-semibold text-fg">{t('review.summaryTitle')}</h3>
        <ByKindCards summary={job.summary} />
      </div>

      <PlanTable jobId={job.id} canManage={canManage} />

      {weakSecrets > 0 && (
        <div className="flex flex-col gap-3 rounded-md border border-line bg-surface-2/50 p-3">
          <h3 className="text-sm font-semibold text-fg">{t('review.weakSecrets.title')}</h3>
          <p className="text-sm text-muted">{t('review.weakSecrets.body', { n: weakSecrets })}</p>
          <Toggle
            checked={rotateWeakSecrets}
            onCheckedChange={onRotateWeakSecretsChange}
            disabled={!canManage}
            label={t('review.weakSecrets.rotateLabel')}
            description={t('review.weakSecrets.rotateHint')}
          />
        </div>
      )}

      <WarningsBlock jobId={job.id} />
      <IgnoredBlock jobId={job.id} />

      {canManage && (
        <div><Button variant="primary" onClick={onContinue}>{t('review.continueButton')}</Button></div>
      )}
    </section>
  );
}
