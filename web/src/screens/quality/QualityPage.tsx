import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pencil, Plus, ShieldAlert, Trash2 } from 'lucide-react';
import {
  useCreateQaChecklist, useDeleteQaChecklist, useDeleteQaEvaluation, useQaChecklists, useQaEvaluations, useQaSummary, useUpdateQaChecklist,
} from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { QaChecklist, QaCriterionInput, QaCriterionKind, QaEvaluation } from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { newId } from '@/lib/browser';
import { formatDateTimeShort } from '@/lib/time';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Drawer, Modal } from '@/ui/Dialog';
import { Field, Input, Select } from '@/ui/Field';
import { Badge } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';
import { Tabs } from '@/ui/Tabs';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';
import { EvaluationDrawer } from './EvaluationDrawer';
import { scoreTone } from './qaScore';


/** S14 — sifat nazorati: baholash varaqalari (checklists), baholashlar va xulosa (M10 C B1). */
export function QualityPage() {
  const { t } = useTranslation('quality');
  const canManage = useCanEdit('reports');

  return (
    <AppShellPage title={t('title')}>
      {!canManage && (
        <p className="mb-3 flex items-center gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2 text-sm text-muted">
          <ShieldAlert aria-hidden className="size-4 shrink-0" />
          {t('readOnlyNotice')}
        </p>
      )}
      <Tabs
        label={t('title')}
        items={[
          { value: 'checklists', label: t('tabs.checklists'), content: <ChecklistsTab canManage={canManage} /> },
          { value: 'evaluations', label: t('tabs.evaluations'), content: <EvaluationsTab canManage={canManage} /> },
          { value: 'summary', label: t('tabs.summary'), content: <SummaryTab /> },
        ]}
      />
    </AppShellPage>
  );
}

// ─────────────────────────── Varaqalar (checklists) ───────────────────────────

type CriterionRow = { key: string; label: string; kind: QaCriterionKind; weight: number; critical: boolean };

function ChecklistsTab({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('quality');
  const toast = useToast();
  const { data, isLoading, isError, refetch } = useQaChecklists();
  const [editing, setEditing] = useState<QaChecklist | 'new' | null>(null);
  const [deleting, setDeleting] = useState<QaChecklist | null>(null);

  const createM = useCreateQaChecklist();
  const updateM = useUpdateQaChecklist();
  const deleteM = useDeleteQaChecklist();
  const close = () => { setEditing(null); createM.reset(); updateM.reset(); };
  const mutation = editing === 'new' ? createM : updateM;

  const columns: Column<QaChecklist>[] = [
    { key: 'name', header: t('checklists.column.name'), sortValue: (c) => c.name, cell: (c) => <span className="font-medium text-fg">{c.name}</span> },
    { key: 'active', header: t('checklists.column.active'), cell: (c) => <Badge tone={c.is_active ? 'success' : 'neutral'}>{t(c.is_active ? 'checklists.active' : 'checklists.inactive')}</Badge> },
    { key: 'criteria', header: t('checklists.column.criteria'), cell: (c) => <span className="num text-sm text-muted">{c.criteria.length}</span> },
    {
      key: 'actions', header: '', align: 'right', cell: (c) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('checklists.editAriaLabel', { name: c.name })} disabled={!canManage} onClick={() => setEditing(c)} />
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('checklists.deleteAriaLabel', { name: c.name })} disabled={!canManage} onClick={() => setDeleting(c)} />
        </div>
      ),
    },
  ];

  return (
    <div className="pt-4">
      <DataTable
        caption={t('checklists.caption')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(c) => c.id}
        searchText={(c) => c.name}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        onRowOpen={canManage ? (c) => setEditing(c) : undefined}
        empty={{ title: t('checklists.empty.title'), body: t('checklists.empty.body'), action: canManage ? <Button size="sm" onClick={() => setEditing('new')}>{t('checklists.empty.action')}</Button> : undefined }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setEditing('new')}>{t('checklists.newChecklist')}</Button> : undefined}
      />

      {editing && (
        <ChecklistForm
          item={editing === 'new' ? undefined : editing}
          pending={mutation.isPending}
          errorMessage={isApiError(mutation.error) ? mutation.error.message : undefined}
          onClose={close}
          onSubmit={(payload) => {
            if (editing === 'new') {
              createM.mutate(payload, { onSuccess: () => { close(); toast({ kind: 'success', title: t('checklists.toast.added') }); } });
            } else {
              updateM.mutate({ id: editing.id, payload: { ...payload, updated_at: editing.updated_at } }, {
                onSuccess: () => { close(); toast({ kind: 'success', title: t('checklists.toast.saved') }); },
              });
            }
          }}
        />
      )}

      <Modal
        open={!!deleting}
        onOpenChange={(v) => !v && setDeleting(null)}
        title={deleting ? t('checklists.deleteModal.title', { name: deleting.name }) : ''}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleting(null)}>{t('cancel')}</Button>
            <Button
              variant="danger" loading={deleteM.isPending}
              onClick={() => deleting && deleteM.mutate(deleting.id, {
                onSuccess: () => { toast({ kind: 'success', title: t('checklists.toast.deleted', { name: deleting.name }) }); setDeleting(null); },
                onError: (e) => { toast({ kind: 'error', title: t('checklists.toast.deleteFailed'), description: e.message }); setDeleting(null); },
              })}
            >
              {t('delete')}
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted">{t('checklists.deleteModal.body', { name: deleting?.name })}</p>
      </Modal>
    </div>
  );
}

function ChecklistForm({
  item, onClose, onSubmit, pending, errorMessage,
}: {
  item?: QaChecklist;
  onClose: () => void;
  onSubmit: (payload: { name: string; is_active: boolean; criteria: QaCriterionInput[] }) => void;
  pending: boolean;
  errorMessage?: string;
}) {
  const { t } = useTranslation('quality');
  const [name, setName] = useState(item?.name ?? '');
  const [isActive, setIsActive] = useState(item?.is_active ?? true);
  const [rows, setRows] = useState<CriterionRow[]>(
    () => item?.criteria.slice().sort((a, b) => a.position - b.position)
      .map((c) => ({ key: newId(), label: c.label, kind: c.kind, weight: c.weight, critical: c.critical }))
      ?? [],
  );

  const addRow = () => setRows((prev) => [...prev, { key: newId(), label: '', kind: 'yesno', weight: 1, critical: false }]);
  const removeRow = (key: string) => setRows((prev) => prev.filter((r) => r.key !== key));
  const patchRow = (key: string, patch: Partial<CriterionRow>) => setRows((prev) => prev.map((r) => (r.key === key ? { ...r, ...patch } : r)));

  const valid = name.trim().length > 0 && rows.length > 0 && rows.every((r) => r.label.trim().length > 0);

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={item ? t('checklists.form.editTitle', { name: item.name }) : t('checklists.form.newTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button
            variant="primary" loading={pending} disabled={!valid}
            onClick={() => onSubmit({
              name: name.trim(), is_active: isActive,
              criteria: rows.map((r) => ({ label: r.label.trim(), kind: r.kind, weight: r.weight, critical: r.critical })),
            })}
          >
            {item ? t('save') : t('add')}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errorMessage && <p className="text-sm text-danger">{errorMessage}</p>}
        <Field label={t('checklists.form.nameLabel')} required>
          {(a) => <Input {...a} autoFocus value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Toggle checked={isActive} onCheckedChange={setIsActive} label={t('checklists.form.activeLabel')} />

        <div className="flex flex-col gap-2">
          <p className="eyebrow">{t('checklists.form.criteriaLabel')}</p>
          {rows.length === 0 && <p className="text-sm text-muted">{t('checklists.form.criteriaEmpty')}</p>}
          {rows.map((r) => (
            <div key={r.key} className="flex flex-col gap-2 rounded-md border border-line p-3">
              <Input
                aria-label={t('checklists.form.criterionLabelPlaceholder')} placeholder={t('checklists.form.criterionLabelPlaceholder')}
                value={r.label} onChange={(e) => patchRow(r.key, { label: e.target.value })}
              />
              <div className="flex flex-wrap items-center gap-3">
                <div className="w-[140px]">
                  <Select
                    size="sm" value={r.kind} onValueChange={(v) => patchRow(r.key, { kind: v as QaCriterionKind })}
                    options={[{ value: 'yesno', label: t('checklists.kind.yesno') }, { value: 'scale5', label: t('checklists.kind.scale5') }]}
                  />
                </div>
                <div className="w-[88px]">
                  <Input
                    type="number" min={0} className="num" aria-label={t('checklists.form.weightLabel')}
                    value={String(r.weight)} onChange={(e) => patchRow(r.key, { weight: Math.max(0, Number(e.target.value) || 0) })}
                  />
                </div>
                <Toggle checked={r.critical} onCheckedChange={(v) => patchRow(r.key, { critical: v })} label={t('checklists.form.criticalLabel')} />
                <Button
                  size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} className="ml-auto"
                  aria-label={t('checklists.form.removeCriterionAriaLabel')} onClick={() => removeRow(r.key)}
                />
              </div>
            </div>
          ))}
          <Button size="sm" variant="secondary" icon={<Plus />} className="self-start" onClick={addRow}>{t('checklists.form.addCriterion')}</Button>
        </div>
      </div>
    </Drawer>
  );
}

// ─────────────────────────── Baholashlar (evaluations) ───────────────────────────

function EvaluationsTab({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('quality');
  const toast = useToast();
  const { data, isLoading, isError, refetch } = useQaEvaluations({ page: 1, size: 100 });
  const { data: checklistsData } = useQaChecklists();
  const deleteM = useDeleteQaEvaluation();
  const [editingCall, setEditingCall] = useState<QaEvaluation | null>(null);
  const [deleting, setDeleting] = useState<QaEvaluation | null>(null);

  const columns: Column<QaEvaluation>[] = [
    { key: 'created_at', header: t('evaluations.column.date'), sortValue: (r) => r.created_at, cell: (r) => <span className="num text-sm">{formatDateTimeShort(r.created_at)}</span> },
    { key: 'call_id', header: t('evaluations.column.call'), cell: (r) => <span className="num text-sm text-muted">{r.call_id.slice(0, 12)}…</span> },
    { key: 'checklist_name', header: t('evaluations.column.checklist'), cell: (r) => <span className="text-sm text-fg">{r.checklist_name}</span> },
    { key: 'score_pct', header: t('evaluations.column.score'), align: 'right', cell: (r) => <Badge tone={scoreTone(r.score_pct)}>{r.score_pct}%</Badge> },
    { key: 'evaluator', header: t('evaluations.column.evaluator'), cell: (r) => <span className="text-sm text-muted">{r.evaluator_name ?? t('evaluations.evaluatorUnknown')}</span> },
    { key: 'comment', header: t('evaluations.column.comment'), cell: (r) => <span className="line-clamp-2 text-sm text-muted">{r.comment || '—'}</span> },
    {
      key: 'actions', header: '', align: 'right', cell: (r) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('evaluations.editAriaLabel')} disabled={!canManage} onClick={() => setEditingCall(r)} />
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('evaluations.deleteAriaLabel')} disabled={!canManage} onClick={() => setDeleting(r)} />
        </div>
      ),
    },
  ];

  return (
    <div className="pt-4">
      <DataTable
        caption={t('evaluations.caption')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(r) => r.id}
        searchText={(r) => r.checklist_name}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        pageSize={12}
        empty={{ title: t('evaluations.empty.title'), body: t('evaluations.empty.body') }}
      />

      {editingCall && (
        <EvaluationDrawer
          callId={editingCall.call_id}
          callLabel={editingCall.checklist_name}
          checklists={checklistsData?.items ?? []}
          onClose={() => setEditingCall(null)}
        />
      )}

      <Modal
        open={!!deleting}
        onOpenChange={(v) => !v && setDeleting(null)}
        title={t('evaluations.deleteModal.title')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleting(null)}>{t('cancel')}</Button>
            <Button
              variant="danger" loading={deleteM.isPending}
              onClick={() => deleting && deleteM.mutate(deleting.id, {
                onSuccess: () => { toast({ kind: 'success', title: t('evaluations.toast.deleted') }); setDeleting(null); },
                onError: (e) => { toast({ kind: 'error', title: t('evaluations.toast.deleteFailed'), description: e.message }); setDeleting(null); },
              })}
            >
              {t('delete')}
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted">{t('evaluations.deleteModal.body')}</p>
      </Modal>
    </div>
  );
}

// ─────────────────────────── Xulosa (summary) ───────────────────────────

function SummaryTab() {
  const { t } = useTranslation('quality');
  const { data, isLoading } = useQaSummary();

  if (isLoading) return <div className="skeleton h-40 pt-4" />;

  return (
    <div className="flex flex-col gap-4 pt-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border border-line bg-surface p-4 shadow-card">
          <p className="eyebrow">{t('summary.overallCount')}</p>
          <p className="num text-3xl font-semibold text-fg">{data?.count ?? 0}</p>
        </div>
        <div className="rounded-lg border border-line bg-surface p-4 shadow-card">
          <p className="eyebrow">{t('summary.overallScore')}</p>
          <p className="num text-3xl font-semibold text-fg">{data ? `${data.avg_score_pct}%` : '—'}</p>
        </div>
      </div>

      <div className="rounded-lg border border-line bg-surface p-4 shadow-card">
        <p className="mb-3 font-display text-base text-fg">{t('summary.byExtension.title')}</p>
        {!data || data.by_extension.length === 0 ? (
          <p className="text-sm text-muted">{t('summary.byExtension.empty')}</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-muted">
                <th className="py-1.5 font-medium">{t('summary.byExtension.column.extension')}</th>
                <th className="py-1.5 text-right font-medium">{t('summary.byExtension.column.count')}</th>
                <th className="py-1.5 text-right font-medium">{t('summary.byExtension.column.score')}</th>
              </tr>
            </thead>
            <tbody>
              {data.by_extension.map((row) => (
                <tr key={row.extension_id ?? 'none'} className="border-b border-line/60 last:border-0">
                  <td className="num py-1.5 text-fg">{row.extension_number ?? '—'}</td>
                  <td className="num py-1.5 text-right text-muted">{row.count}</td>
                  <td className="num py-1.5 text-right"><Badge tone={scoreTone(row.avg_score_pct)}>{row.avg_score_pct}%</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
