import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Eye } from 'lucide-react';
import { daysAgo, formatDateTime, isoDate } from '@/lib/time';
import { useAudit } from '@/api/queries';
import type { AuditAction, AuditEntry } from '@/api/types';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Modal } from '@/ui/Dialog';
import { Field, Input, Select } from '@/ui/Field';
import { Badge, type Tone } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';

const ACTION_TONE: Record<AuditAction, Tone> = {
  create: 'success', update: 'info', delete: 'danger', login: 'neutral', login_failed: 'warning',
  restore: 'warning', restart: 'warning', override: 'info', spy: 'neutral',
};

const SECRET_VALUE = '***';

/** Audit jurnali: har yozish amali (va kirish) kim/qachon/nima oʻzgartirgani bilan — parollar `***` bilan maskalanadi. */
export function AuditPage() {
  const { t } = useTranslation('audit');
  const actionLabel: Record<AuditAction, string> = {
    create: t('action.create'), update: t('action.update'), delete: t('action.delete'), login: t('action.login'), login_failed: t('action.login_failed'),
    restore: t('action.restore'), restart: t('action.restart'), override: t('action.override'), spy: t('action.spy'),
  };
  const [from, setFrom] = useState(daysAgo(30));
  const [to, setTo] = useState(isoDate(new Date()));
  const [action, setAction] = useState<'all' | AuditAction>('all');
  const [entity, setEntity] = useState('');
  const [q, setQ] = useState('');
  const [viewing, setViewing] = useState<AuditEntry | null>(null);

  const { data, isLoading, isError, refetch } = useAudit({
    from: `${from}T00:00:00.000Z`, to: `${to}T23:59:59.999Z`,
    action: action === 'all' ? undefined : action,
    entity: entity.trim() || undefined,
    q: q.trim() || undefined,
    page: 1, size: 200,
  });

  const columns: Column<AuditEntry>[] = [
    { key: 'at', header: t('column.at'), sortValue: (r) => r.at, cell: (r) => <span className="num text-sm">{formatDateTime(r.at)}</span>, width: '180px' },
    { key: 'user', header: t('column.user'), cell: (r) => <span className="text-sm">{r.user?.login ?? <span className="text-muted">{t('systemUser')}</span>}</span> },
    { key: 'action', header: t('column.action'), cell: (r) => <Badge tone={ACTION_TONE[r.action]}>{actionLabel[r.action]}</Badge> },
    { key: 'entity', header: t('column.entity'), cell: (r) => <span className="text-sm text-muted">{r.entity}</span> },
    { key: 'label', header: t('column.label'), cell: (r) => <span className="truncate text-sm">{r.label ?? '—'}</span> },
    { key: 'ip', header: t('column.ip'), cell: (r) => <span className="num text-xs text-muted">{r.ip ?? '—'}</span> },
    {
      key: 'diff', header: '', align: 'right', cell: (r) => (
        Object.keys(r.diff).length > 0
          ? <Button size="sm" variant="ghost" iconOnly icon={<Eye />} aria-label={t('viewDiffAriaLabel')} onClick={() => setViewing(r)} />
          : null
      ),
    },
  ];

  return (
    <AppShellPage title={t('title')}>
      <div className="mb-4 flex flex-wrap items-end gap-3 rounded-lg border border-line bg-surface p-3 shadow-card">
        <Field label={t('filter.from')}>
          {(a) => <Input {...a} type="date" value={from} max={to} onChange={(e) => setFrom(e.target.value)} />}
        </Field>
        <Field label={t('filter.to')}>
          {(a) => <Input {...a} type="date" value={to} min={from} max={isoDate(new Date())} onChange={(e) => setTo(e.target.value)} />}
        </Field>
        <Field label={t('filter.action')}>
          {({ id }) => (
            <Select
              id={id} value={action} onValueChange={(v) => setAction(v as typeof action)}
              options={[{ value: 'all', label: t('filter.all') }, ...Object.entries(actionLabel).map(([value, label]) => ({ value, label }))]}
            />
          )}
        </Field>
        <Field label={t('filter.entity')} aside={t('filter.optional')}>
          {(a) => <Input {...a} value={entity} onChange={(e) => setEntity(e.target.value)} placeholder={t('filter.entityPlaceholder')} />}
        </Field>
        <Field label={t('filter.search')} aside={t('filter.optional')} className="min-w-[160px] flex-1">
          {(a) => <Input {...a} value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('filter.searchPlaceholder')} />}
        </Field>
      </div>

      <DataTable
        caption={t('caption')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(r) => r.id}
        searchText={(r) => `${r.user?.login ?? ''} ${r.entity} ${r.label ?? ''}`}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        pageSize={20}
        empty={{ title: t('empty.title'), body: t('empty.body') }}
      />

      <Modal
        open={!!viewing}
        onOpenChange={(v) => !v && setViewing(null)}
        title={viewing ? `${actionLabel[viewing.action]} — ${viewing.entity}` : ''}
        description={viewing ? `${viewing.user?.login ?? t('systemUser')} · ${formatDateTime(viewing.at)}` : undefined}
        footer={<Button variant="primary" onClick={() => setViewing(null)}>{t('close')}</Button>}
      >
        {viewing && <DiffTable diff={viewing.diff} />}
      </Modal>
    </AppShellPage>
  );
}

function fmtVal(v: unknown): string {
  if (v === null || v === undefined) return '—';
  if (v === SECRET_VALUE) return '***';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

function DiffTable({ diff }: { diff: AuditEntry['diff'] }) {
  const { t } = useTranslation('audit');
  const keys = Object.keys(diff);
  if (keys.length === 0) return <p className="text-sm text-muted">{t('diff.empty')}</p>;
  return (
    <table className="num w-full text-sm">
      <thead>
        <tr className="border-b border-line text-left text-xs text-muted">
          <th className="py-1.5 pr-3 font-medium">{t('diff.field')}</th>
          <th className="py-1.5 pr-3 font-medium">{t('diff.before')}</th>
          <th className="py-1.5 font-medium">{t('diff.after')}</th>
        </tr>
      </thead>
      <tbody>
        {keys.map((k) => {
          const [before, after] = diff[k] as [unknown, unknown];
          return (
            <tr key={k} className="border-b border-line last:border-b-0">
              <td className="py-1.5 pr-3 font-medium text-fg">{k}</td>
              <td className="py-1.5 pr-3 text-danger">{fmtVal(before)}</td>
              <td className="py-1.5 text-success">{fmtVal(after)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
