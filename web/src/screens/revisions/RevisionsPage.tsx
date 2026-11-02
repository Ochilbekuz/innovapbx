import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, History, RotateCcw } from 'lucide-react';
import { useConfigRevisions, useRestoreRevision, useRevisionDiff } from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { ConfigRevision, RevisionDiffAgainst } from '@/api/types';
import { formatDateTime } from '@/lib/time';
import { cn } from '@/lib/cn';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Modal } from '@/ui/Dialog';
import { Badge, type Tone } from '@/ui/Status';
import { useToast } from '@/ui/Toast';

const STATUS_TONE: Record<string, Tone> = { applied: 'success', rolled_back: 'danger', applying: 'info' };

/** Konfiguratsiya reviziyalari tarixi: har saqlashda yangi reviziya, farqini koʻrish va avvalgi holatga qaytarish. */
export function RevisionsPage() {
  const { t } = useTranslation('revisions');
  const statusLabel: Record<string, string> = { applied: t('status.applied'), rolled_back: t('status.rolledBack'), applying: t('status.applying') };
  const { data, isLoading, isError, refetch } = useConfigRevisions(50);
  const toast = useToast();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [against, setAgainst] = useState<RevisionDiffAgainst>('prev');
  const [restoring, setRestoring] = useState<ConfigRevision | null>(null);
  const restoreM = useRestoreRevision();

  const revisions = data?.items ?? [];
  const selected = revisions.find((r) => r.id === selectedId) ?? revisions[0] ?? null;
  const { data: diff, isLoading: diffLoading } = useRevisionDiff(selected?.id, against);

  return (
    <AppShellPage title={t('title')}>
      {isLoading ? (
        <p className="rounded-md border border-dashed border-line px-3 py-6 text-center text-sm text-muted">{t('loading')}</p>
      ) : isError ? (
        <div className="flex flex-col items-center gap-2 rounded-md border border-dashed border-line px-3 py-6 text-center text-sm text-muted">
          <p>{t('errorBody')}</p>
          <Button size="sm" variant="secondary" onClick={() => void refetch()}>{t('retry')}</Button>
        </div>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[320px_1fr] lg:items-start">
          <ol aria-label={t('listAriaLabel')} className="flex flex-col gap-1 overflow-hidden rounded-lg border border-line bg-surface shadow-card">
            {revisions.map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(r.id)}
                  aria-current={selected?.id === r.id ? 'true' : undefined}
                  className={cn(
                    'flex w-full flex-col gap-1 border-b border-line px-3 py-2.5 text-left transition-colors duration-fast last:border-b-0 hover:bg-surface-2',
                    selected?.id === r.id && 'bg-accent-soft/60',
                  )}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="num font-medium text-fg">r{r.id}</span>
                    <Badge tone={STATUS_TONE[r.status] ?? 'neutral'}>{statusLabel[r.status] ?? r.status}</Badge>
                  </span>
                  <span className="truncate text-sm text-fg">{r.summary ?? r.message ?? t('defaultSummary')}</span>
                  <span className="text-xs text-muted">{r.user?.login ?? t('systemUser')} · {formatDateTime(r.created_at)}</span>
                </button>
              </li>
            ))}
          </ol>

          {selected && (
            <div className="flex flex-col gap-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <History aria-hidden className="size-4 text-muted" />
                  <h2 className="num text-base font-semibold text-fg">{t('revisionLabel', { id: selected.id })}</h2>
                  <Badge tone={STATUS_TONE[selected.status] ?? 'neutral'}>{statusLabel[selected.status] ?? selected.status}</Badge>
                </div>
                <Button size="sm" variant="secondary" icon={<RotateCcw />} onClick={() => setRestoring(selected)}>{t('restore')}</Button>
              </div>

              <div className="flex gap-2">
                <Button size="sm" variant={against === 'prev' ? 'primary' : 'secondary'} onClick={() => setAgainst('prev')}>{t('compareWithPrevious')}</Button>
                <Button size="sm" variant={against === 'current' ? 'primary' : 'secondary'} onClick={() => setAgainst('current')}>{t('compareWithCurrent')}</Button>
              </div>

              <DiffView unified={diff?.unified} loading={diffLoading} />
            </div>
          )}
        </div>
      )}

      <Modal
        open={!!restoring}
        onOpenChange={(v) => !v && setRestoring(null)}
        title={restoring ? t('restoreModal.title', { id: restoring.id }) : ''}
        footer={
          <>
            <Button variant="ghost" onClick={() => setRestoring(null)}>{t('restoreModal.cancel')}</Button>
            <Button
              variant="danger" loading={restoreM.isPending}
              onClick={() => restoring && restoreM.mutate(restoring.id, {
                onSuccess: (res) => { toast({ kind: 'success', title: t('toast.restoredTitle'), description: res.apply.message ?? undefined }); setRestoring(null); },
                onError: (e) => toast({ kind: 'error', title: t('toast.restoreFailedTitle'), description: isApiError(e) ? e.message : e.message }),
              })}
            >
              {t('restoreModal.confirm')}
            </Button>
          </>
        }
      >
        <div className="flex items-start gap-2 rounded-md border border-warning/30 bg-warning-soft px-3 py-2.5 text-sm text-on-warning-soft">
          <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0" />
          <p>{t('restoreModal.body')}</p>
        </div>
      </Modal>
    </AppShellPage>
  );
}

function DiffView({ unified, loading }: { unified?: string; loading: boolean }) {
  const { t } = useTranslation('revisions');
  if (loading) return <p className="rounded-md border border-dashed border-line px-3 py-6 text-center text-sm text-muted">{t('diff.loading')}</p>;
  if (!unified) return <p className="rounded-md border border-dashed border-line px-3 py-6 text-center text-sm text-muted">{t('diff.empty')}</p>;
  const lines = unified.split('\n');
  return (
    <pre className="num overflow-x-auto rounded-lg border border-line bg-surface p-3 text-xs leading-relaxed shadow-card">
      {lines.map((line, i) => (
        <div
          key={i}
          className={cn(
            'whitespace-pre',
            line.startsWith('+++') || line.startsWith('---') ? 'font-medium text-muted' :
            line.startsWith('+') ? 'bg-success-soft text-on-success-soft' :
            line.startsWith('-') ? 'bg-danger-soft text-on-danger-soft' : 'text-muted',
          )}
        >
          {line || ' '}
        </div>
      ))}
    </pre>
  );
}
