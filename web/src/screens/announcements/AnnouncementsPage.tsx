import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pencil, Plus, Repeat, ShieldAlert, Trash2 } from 'lucide-react';
import { useAnnouncements, useAudio, useCreateAnnouncement, useDeleteAnnouncement, useTargets, useUpdateAnnouncement } from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { Announcement, RepeatKey, Usage } from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { toCatalog } from '@/pbx/catalog';
import { DestinationPicker } from '@/pbx/DestinationPicker';
import { applyToast } from '@/lib/applyToast';
import { usagesOf } from '@/lib/usageError';
import { UsageList } from '@/pbx/UsageList';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Drawer, Modal } from '@/ui/Dialog';
import { Field, Input, Select } from '@/ui/Field';
import { DataTable, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';
import type { Destination } from '@/domain/destination';

const TARGET_KINDS = ['extension', 'ring_group', 'queue', 'ivr', 'time_condition', 'conference', 'hangup', 'busy', 'announcement', 'misc'] as const;
const REPEAT_KEYS: RepeatKey[] = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '#'];

/** M9 A1 — shartnomada S-raqam berilmagan. E'lonlar: xabar + keyingi manzil + o'tkazib yuborish/takror. */
export function AnnouncementsPage() {
  const { t } = useTranslation('announcements');
  const { data, isLoading, isError, refetch } = useAnnouncements();
  const { data: audioData } = useAudio();
  const { data: targetsData } = useTargets({ kind: TARGET_KINDS.join(',') });
  const audio = audioData?.items ?? [];
  const catalog = useMemo(() => toCatalog(targetsData?.items ?? []), [targetsData]);
  const canManage = useCanEdit('routing');
  const toast = useToast();
  const [editing, setEditing] = useState<Announcement | 'new' | null>(null);
  const [deleting, setDeleting] = useState<Announcement | null>(null);
  const [deleteErr, setDeleteErr] = useState<Usage[] | null>(null);

  const createM = useCreateAnnouncement();
  const updateM = useUpdateAnnouncement();
  const deleteM = useDeleteAnnouncement();
  const close = () => { setEditing(null); createM.reset(); updateM.reset(); };
  const mutation = editing === 'new' ? createM : updateM;

  const columns: Column<Announcement>[] = [
    { key: 'name', header: t('column.name'), sortValue: (a) => a.name, cell: (a) => <span className="font-medium">{a.name}</span> },
    { key: 'audio', header: t('column.audio'), cell: (a) => <span className="truncate text-muted">{a.audio_name}</span> },
    { key: 'target', header: t('column.target'), cell: (a) => <span className="truncate text-sm text-muted">{a.next_target.label}</span> },
    {
      key: 'repeat', header: t('column.repeat'), cell: (a) => a.repeat_key ? (
        <span className="flex items-center gap-1 text-sm text-fg"><Repeat aria-hidden className="size-3.5 text-brand" /> {a.repeat_key}</span>
      ) : <span className="text-muted">—</span>,
    },
    {
      key: 'actions', header: '', align: 'right', cell: (a) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('editAriaLabel', { name: a.name })} disabled={!canManage} onClick={() => setEditing(a)} />
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('deleteAriaLabel', { name: a.name })} disabled={!canManage} onClick={() => setDeleting(a)} />
        </div>
      ),
    },
  ];

  return (
    <AppShellPage title={t('title')}>
      {!canManage && (
        <p className="mb-3 flex items-center gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2 text-sm text-muted">
          <ShieldAlert aria-hidden className="size-4 shrink-0" />
          {t('readOnlyNotice')}
        </p>
      )}
      <DataTable
        caption={t('caption')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(a) => a.id}
        searchText={(a) => `${a.name} ${a.audio_name}`}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        onRowOpen={canManage ? (a) => setEditing(a) : undefined}
        empty={{ title: t('empty.title'), body: t('empty.body'), action: canManage ? <Button size="sm" onClick={() => setEditing('new')}>{t('empty.action')}</Button> : undefined }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setEditing('new')}>{t('newAnnouncement')}</Button> : undefined}
      />

      {editing && (
        <AnnouncementForm
          announcement={editing === 'new' ? undefined : editing}
          audio={audio}
          catalog={catalog}
          pending={mutation.isPending}
          errorField={isApiError(mutation.error) ? mutation.error.field : undefined}
          errorMessage={isApiError(mutation.error) ? mutation.error.message : undefined}
          onClose={close}
          onSubmit={(payload) => {
            if (editing === 'new') {
              createM.mutate(payload, { onSuccess: (res) => { close(); toast(applyToast(res.apply, t('toast.added'))); } });
            } else {
              updateM.mutate({ id: editing.id, payload: { ...payload, updated_at: editing.updated_at } }, {
                onSuccess: (res) => { close(); toast(applyToast(res.apply, t('toast.saved'))); },
              });
            }
          }}
        />
      )}

      <Modal
        open={!!deleting}
        onOpenChange={(v) => !v && (setDeleting(null), setDeleteErr(null))}
        title={deleting ? t('deleteModal.title', { name: deleting.name }) : ''}
        footer={
          <>
            <Button variant="ghost" onClick={() => { setDeleting(null); setDeleteErr(null); }}>{t('cancel')}</Button>
            {!deleteErr && (
              <Button
                variant="danger" loading={deleteM.isPending}
                onClick={() => deleting && deleteM.mutate(deleting.id, {
                  onSuccess: () => { toast({ kind: 'success', title: t('toast.deleted', { name: deleting.name }) }); setDeleting(null); },
                  onError: (e) => { if (isApiError(e) && e.code === 'in_use') setDeleteErr(usagesOf(e)); else toast({ kind: 'error', title: t('toast.deleteFailed'), description: e.message }); },
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
    </AppShellPage>
  );
}

function AnnouncementForm({
  announcement, audio, catalog, onClose, onSubmit, pending, errorField, errorMessage,
}: {
  announcement?: Announcement;
  audio: { id: string; name: string }[];
  catalog: ReturnType<typeof toCatalog>;
  onClose: () => void;
  onSubmit: (payload: { name: string; audio_file_id: string; next_target_id: string; allow_skip: boolean; repeat_key: RepeatKey | null; answer: boolean }) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('announcements');
  const [name, setName] = useState(announcement?.name ?? '');
  const [audioId, setAudioId] = useState(announcement?.audio_file_id ?? audio[0]?.id ?? '');
  const [target, setTarget] = useState<Destination | null>(
    announcement ? { kind: announcement.next_target.kind, targetId: announcement.next_target.id } : null,
  );
  const [allowSkip, setAllowSkip] = useState(announcement?.allow_skip ?? false);
  const [repeatKey, setRepeatKey] = useState<string>(announcement?.repeat_key ?? '');
  const [answer, setAnswer] = useState(announcement?.answer ?? true);

  const valid = name.trim().length > 0 && !!audioId && !!target && target.kind !== 'external';

  const submit = () => {
    if (!target || target.kind === 'external' || !valid) return;
    onSubmit({
      name: name.trim(), audio_file_id: audioId, next_target_id: target.targetId,
      allow_skip: allowSkip, repeat_key: (repeatKey || null) as RepeatKey | null, answer,
    });
  };

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={announcement ? t('form.editTitle', { name: announcement.name }) : t('form.newTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={submit}>{announcement ? t('save') : t('add')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errorMessage && !['name', 'audio_file_id', 'next_target_id'].includes(errorField ?? '') && (
          <p className="text-sm text-danger">{errorMessage}</p>
        )}

        <Field label={t('form.nameLabel')} required error={errorField === 'name' ? errorMessage : undefined}>
          {(a) => <Input {...a} autoFocus value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>

        {audio.length === 0 ? (
          <p className="text-sm text-danger">{t('noAudioNotice')}</p>
        ) : (
          <Field label={t('form.audioLabel')} hint={t('form.audioHint')} error={errorField === 'audio_file_id' ? errorMessage : undefined}>
            {(a) => <Select {...a} value={audioId} onValueChange={setAudioId} options={audio.map((f) => ({ value: f.id, label: f.name }))} />}
          </Field>
        )}

        <DestinationPicker label={t('form.targetLabel')} hint={t('form.targetHint')} required kinds={[...TARGET_KINDS]} value={target} onChange={setTarget} catalog={catalog} />

        <Toggle checked={allowSkip} onCheckedChange={setAllowSkip} label={t('form.allowSkipLabel')} description={t('form.allowSkipDesc')} />

        <Field label={t('form.repeatLabel')} hint={t('form.repeatHint')}>
          {(a) => <Select {...a} value={repeatKey} onValueChange={setRepeatKey} options={[{ value: '', label: t('form.repeatNone') }, ...REPEAT_KEYS.map((k) => ({ value: k, label: k }))]} />}
        </Field>

        <Toggle checked={answer} onCheckedChange={setAnswer} label={t('form.answerLabel')} description={t('form.answerDesc')} />
      </div>
    </Drawer>
  );
}
