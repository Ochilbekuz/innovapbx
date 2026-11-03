import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pencil, Trash2 } from 'lucide-react';
import { useCallEvaluations, useCreateQaEvaluation, useDeleteQaEvaluation, useUpdateQaEvaluation } from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { QaAnswers, QaChecklist, QaEvaluation } from '@/api/types';
import { formatDateTimeShort } from '@/lib/time';
import { Button } from '@/ui/Button';
import { Drawer, Modal } from '@/ui/Dialog';
import { Field, Segmented, Select, Textarea } from '@/ui/Field';
import { Badge } from '@/ui/Status';
import { useToast } from '@/ui/Toast';
import { scoreTone } from './qaScore';


/**
 * M10 C B1 — qoʻngʻiroqni baholash: avvalgi baholashlar roʻyxati + yangi baholash/tahrirlash shakli.
 * `CallsPage` («Baholash» tugmasi) va `QualityPage` (baholashlar jadvalidagi «Tahrirlash») uchun umumiy.
 */
export function EvaluationDrawer({
  callId, callLabel, checklists, onClose,
}: { callId: string; callLabel: string; checklists: QaChecklist[]; onClose: () => void }) {
  const { t } = useTranslation('quality');
  const toast = useToast();
  const { data, isLoading } = useCallEvaluations(callId);
  const createM = useCreateQaEvaluation();
  const updateM = useUpdateQaEvaluation();
  const deleteM = useDeleteQaEvaluation();

  const [editing, setEditing] = useState<QaEvaluation | null>(null);
  const [deleting, setDeleting] = useState<QaEvaluation | null>(null);
  const [checklistId, setChecklistId] = useState<string>('');
  const [answers, setAnswers] = useState<QaAnswers>({});
  const [comment, setComment] = useState('');

  const resetForm = () => { setEditing(null); setChecklistId(''); setAnswers({}); setComment(''); createM.reset(); updateM.reset(); };
  const startEdit = (ev: QaEvaluation) => { setEditing(ev); setChecklistId(ev.checklist_id); setAnswers(ev.answers); setComment(ev.comment ?? ''); };

  const checklist = checklists.find((c) => c.id === checklistId) ?? null;
  const setAnswer = (criterionId: string, value: boolean | number) => setAnswers((prev) => ({ ...prev, [criterionId]: value }));

  const mutation = editing ? updateM : createM;
  const valid = !!checklist && checklist.criteria.every((c) => answers[c.id] !== undefined);

  const submit = () => {
    if (!checklist) return;
    if (editing) {
      updateM.mutate({ id: editing.id, payload: { answers, comment: comment.trim() || null, updated_at: editing.updated_at } }, {
        onSuccess: () => { toast({ kind: 'success', title: t('evaluationDrawer.updatedToast') }); resetForm(); },
      });
    } else {
      createM.mutate({ checklist_id: checklist.id, call_id: callId, answers, comment: comment.trim() || null }, {
        onSuccess: () => { toast({ kind: 'success', title: t('evaluationDrawer.createdToast') }); resetForm(); },
      });
    }
  };

  const errorMessage = isApiError(mutation.error) ? mutation.error.message : undefined;

  return (
    <Drawer open onOpenChange={(v) => !v && onClose()} title={t('evaluationDrawer.title')} description={callLabel}>
      <div className="flex flex-col gap-5">
        <section className="flex flex-col gap-2">
          <p className="eyebrow">{t('evaluationDrawer.existingTitle')}</p>
          {isLoading ? (
            <div className="skeleton h-16" />
          ) : !data || data.items.length === 0 ? (
            <p className="text-sm text-muted">{t('evaluationDrawer.existingEmpty')}</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {data.items.map((ev) => (
                <li key={ev.id} className="flex items-start justify-between gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-fg">{ev.checklist_name}</span>
                      <Badge tone={scoreTone(ev.score_pct)}>{ev.score_pct}%</Badge>
                    </div>
                    <p className="num text-xs text-muted">{formatDateTimeShort(ev.created_at)}</p>
                    {ev.comment && <p className="mt-1 text-sm text-muted">{ev.comment}</p>}
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('evaluationDrawer.editAction')} onClick={() => startEdit(ev)} />
                    <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('evaluationDrawer.deleteAriaLabel')} onClick={() => setDeleting(ev)} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="flex flex-col gap-3 border-t border-line pt-4">
          <p className="eyebrow">{editing ? t('evaluationDrawer.editingTitle') : t('evaluationDrawer.newTitle')}</p>
          <Field label={t('evaluationDrawer.checklistLabel')} required>
            {(a) => (
              <Select
                {...a}
                value={checklistId}
                placeholder={t('evaluationDrawer.checklistPlaceholder')}
                disabled={!!editing}
                onValueChange={(v) => { setChecklistId(v); setAnswers({}); }}
                options={checklists.map((c) => ({ value: c.id, label: c.name, disabled: !c.is_active && c.id !== editing?.checklist_id }))}
              />
            )}
          </Field>

          {checklist && (
            checklist.criteria.length === 0 ? (
              <p className="text-sm text-muted">{t('evaluationDrawer.criteriaEmptyNotice')}</p>
            ) : (
              <ul className="flex flex-col gap-3">
                {checklist.criteria.slice().sort((a, b) => a.position - b.position).map((c) => (
                  <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line px-3 py-2">
                    <span className="min-w-0 flex-1 text-sm text-fg">{c.label}{c.critical ? ' *' : ''}</span>
                    {c.kind === 'yesno' ? (
                      <Segmented
                        label={c.label}
                        value={answers[c.id] === undefined ? '' : answers[c.id] ? 'yes' : 'no'}
                        onChange={(v) => setAnswer(c.id, v === 'yes')}
                        options={[{ value: 'yes', label: t('evaluationDrawer.yes') }, { value: 'no', label: t('evaluationDrawer.no') }]}
                      />
                    ) : (
                      <Segmented
                        label={c.label}
                        value={answers[c.id] === undefined ? '' : String(answers[c.id])}
                        onChange={(v) => setAnswer(c.id, Number(v))}
                        options={['1', '2', '3', '4', '5'].map((n) => ({ value: n, label: n }))}
                      />
                    )}
                  </li>
                ))}
              </ul>
            )
          )}

          <Field label={t('evaluationDrawer.commentLabel')}>
            {(a) => <Textarea {...a} rows={3} placeholder={t('evaluationDrawer.commentPlaceholder')} value={comment} onChange={(e) => setComment(e.target.value)} />}
          </Field>
          {errorMessage && <p className="text-sm text-danger">{errorMessage}</p>}

          <div className="flex justify-end gap-2">
            {editing && <Button variant="ghost" onClick={resetForm}>{t('evaluationDrawer.cancelEdit')}</Button>}
            <Button variant="primary" loading={mutation.isPending} disabled={!valid} onClick={submit}>
              {editing ? t('evaluationDrawer.submitUpdate') : t('evaluationDrawer.submitCreate')}
            </Button>
          </div>
        </section>
      </div>

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
                onSuccess: () => { toast({ kind: 'success', title: t('evaluationDrawer.deletedToast') }); setDeleting(null); if (editing?.id === deleting.id) resetForm(); },
                onError: (e) => toast({ kind: 'error', title: e.message }),
              })}
            >
              {t('delete')}
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted">{t('evaluations.deleteModal.body')}</p>
      </Modal>
    </Drawer>
  );
}
