import { useEffect, useRef, useState, type DragEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { AudioLines, Mic, Music2, Pencil, Plus, Shuffle, Square, Star, Trash2, Upload } from 'lucide-react';
import { apiClient } from '@/api';
import {
  useAudio, useCreateMohClass, useCreateTtsAudio, useDeleteAudio, useDeleteMohClass, useMohClasses, useTtsSettings,
  useUpdateMohClass, useUploadAudio,
} from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { Audio, MohClass, Usage } from '@/api/types';
import { useCanEdit, usePermission } from '@/auth/permissions';
import { cn } from '@/lib/cn';
import { formatDateTimeShort, formatDurationMs, formatDurationSec } from '@/lib/time';
import { usagesOf } from '@/lib/usageError';
import { AudioPlayer } from '@/pbx/AudioPlayer';
import { UsageList } from '@/pbx/UsageList';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Drawer, Modal } from '@/ui/Dialog';
import { Field, Input, Textarea } from '@/ui/Field';
import { Badge } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';
import { Tabs } from '@/ui/Tabs';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

const TTS_MAX_CHARS = 2000;

const ACCEPT = '.wav,.mp3,.ogg';
const MAX_RECORD_S = 300;

/** S11 — Audio kutubxona: salomlashuv/eslatma fayllari (yuklash yoki mikrofondan yozish) va kutish musiqasi sinflari. */
export function AudioPage() {
  const { t } = useTranslation('audio');
  const { data: mohData } = useMohClasses();
  return (
    <AppShellPage title={t('title')}>
      <Tabs
        label={t('tabsAriaLabel')}
        items={[
          { value: 'files', label: t('tab.files'), content: <FilesTab /> },
          { value: 'moh', label: t('tab.moh'), count: mohData?.items.length, content: <MohTab /> },
        ]}
      />
    </AppShellPage>
  );
}

function FilesTab() {
  const { t } = useTranslation('audio');
  const { data, isLoading, isError, refetch } = useAudio();
  const canManage = useCanEdit('apps');
  const toast = useToast();
  const uploadM = useUploadAudio();
  const deleteM = useDeleteAudio();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [deleting, setDeleting] = useState<Audio | null>(null);
  const [deleteErr, setDeleteErr] = useState<Usage[] | null>(null);
  const [uploadErr, setUploadErr] = useState<string | null>(null);

  const upload = (file: File, name?: string) => {
    setUploadErr(null);
    uploadM.mutate({ file, name: name ?? file.name.replace(/\.[^.]+$/, '') }, {
      onSuccess: () => toast({ kind: 'success', title: t('files.uploaded', { name: file.name }) }),
      onError: (e) => setUploadErr(isApiError(e) ? e.message : t('files.uploadFailed')),
    });
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) upload(file);
  };

  const columns: Column<Audio>[] = [
    { key: 'name', header: t('files.column.name'), sortValue: (r) => r.name, cell: (r) => <span className="truncate font-medium">{r.name}</span> },
    { key: 'play', header: t('files.column.play'), cell: (r) => <AudioPlayer variant="inline" src={() => apiClient.fetchAudio(r.id)} title={r.name} seed={r.name.length} /> },
    { key: 'duration', header: t('files.column.duration'), cell: (r) => <span className="num text-muted">{formatDurationMs(r.duration_ms)}</span> },
    { key: 'format', header: t('files.column.format'), cell: (r) => <span className="num uppercase text-muted">{r.format}</span> },
    { key: 'created', header: t('files.column.created'), cell: (r) => <span className="text-sm text-muted">{formatDateTimeShort(r.created_at)}</span> },
    {
      key: 'actions', header: '', align: 'right', cell: (r) => (
        <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('files.deleteAriaLabel', { name: r.name })} disabled={!canManage} onClick={() => setDeleting(r)} />
      ),
    },
  ];

  return (
    <div>
      {canManage && (
        <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            className={cn('flex flex-col items-center gap-2 rounded-lg border-2 border-dashed px-4 py-8 text-center transition-colors duration-fast', dragOver ? 'border-brand bg-accent-soft/40' : 'border-line')}
          >
            <Upload aria-hidden className="size-6 text-muted" />
            <p className="text-sm text-muted">{t('files.dropHint')}</p>
            <Button size="sm" variant="secondary" loading={uploadM.isPending} onClick={() => inputRef.current?.click()}>{t('files.chooseFile')}</Button>
            <p className="text-xs text-muted">{t('files.formatsHint')}</p>
            <input
              ref={inputRef} type="file" accept={ACCEPT} className="sr-only"
              onChange={(e) => { const file = e.target.files?.[0]; if (file) upload(file); e.target.value = ''; }}
            />
          </div>
          <AudioRecorder onSave={upload} pending={uploadM.isPending} />
          <TtsCard />
        </div>
      )}
      {uploadErr && <p className="mb-3 text-sm text-danger">{uploadErr}</p>}

      <DataTable
        caption={t('files.caption')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(r) => r.id}
        searchText={(r) => r.name}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        empty={{ title: t('files.empty.title'), body: t('files.empty.body') }}
      />

      <Modal
        open={!!deleting}
        onOpenChange={(v) => !v && (setDeleting(null), setDeleteErr(null))}
        title={deleting ? t('files.deleteModal.title', { name: deleting.name }) : ''}
        footer={
          <>
            <Button variant="ghost" onClick={() => { setDeleting(null); setDeleteErr(null); }}>{t('cancel')}</Button>
            {!deleteErr && (
              <Button
                variant="danger" loading={deleteM.isPending}
                onClick={() => deleting && deleteM.mutate(deleting.id, {
                  onSuccess: () => { toast({ kind: 'success', title: t('files.toast.deleted', { name: deleting.name }) }); setDeleting(null); },
                  onError: (e) => { if (isApiError(e) && e.code === 'in_use') setDeleteErr(usagesOf(e)); else toast({ kind: 'error', title: t('files.toast.deleteFailed'), description: e.message }); },
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
            <p className="text-sm text-danger">{t('files.deleteModal.usagePrefix', { name: deleting?.name })}</p>
            <UsageList usages={deleteErr} />
          </div>
        ) : (
          <p className="text-sm text-muted">{t('files.deleteModal.body', { name: deleting?.name })}</p>
        )}
      </Modal>
    </div>
  );
}

function pickRecorderFormat(): { mimeType: string; ext: 'ogg' | 'webm' } {
  if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) return { mimeType: 'audio/ogg;codecs=opus', ext: 'ogg' };
  return { mimeType: 'audio/webm', ext: 'webm' };
}

type RecorderPhase = 'idle' | 'recording' | 'recorded';

/** Mikrofondan to'g'ridan-to'g'ri yozib olish: WAV/MP3 fayl tayyorlab yurish shart emas — brauzerda yozib, shu yerdan yuklash mumkin. */
function AudioRecorder({ onSave, pending }: { onSave: (file: File, name: string) => void; pending: boolean }) {
  const { t } = useTranslation('audio');
  const [phase, setPhase] = useState<RecorderPhase>('idle');
  const [elapsed, setElapsed] = useState(0);
  const [name, setName] = useState('');
  const [recErr, setRecErr] = useState<string | null>(null);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const recRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const blobRef = useRef<Blob | null>(null);
  const extRef = useRef<'ogg' | 'webm'>('webm');
  const timerRef = useRef<number | null>(null);

  useEffect(() => () => {
    if (timerRef.current) window.clearInterval(timerRef.current);
    recRef.current?.stream.getTracks().forEach((t) => t.stop());
  }, []);

  const stop = () => {
    recRef.current?.stop();
    if (timerRef.current) { window.clearInterval(timerRef.current); timerRef.current = null; }
  };

  const start = async () => {
    setRecErr(null);
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      setRecErr(t('files.recorder.notSupported'));
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const { mimeType, ext } = pickRecorderFormat();
      extRef.current = ext;
      chunksRef.current = [];
      const mr = new MediaRecorder(stream, { mimeType });
      mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      mr.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: mimeType });
        blobRef.current = blob;
        setBlobUrl(URL.createObjectURL(blob));
        setPhase('recorded');
      };
      recRef.current = mr;
      mr.start();
      setElapsed(0);
      setPhase('recording');
      timerRef.current = window.setInterval(() => {
        setElapsed((s) => {
          if (s + 1 >= MAX_RECORD_S) { stop(); return MAX_RECORD_S; }
          return s + 1;
        });
      }, 1000);
    } catch {
      setRecErr(t('files.recorder.micDenied'));
    }
  };

  const discard = () => {
    if (blobUrl) URL.revokeObjectURL(blobUrl);
    blobRef.current = null;
    setBlobUrl(null);
    setName('');
    setElapsed(0);
    setPhase('idle');
  };

  const save = () => {
    if (!blobRef.current) return;
    const ext = extRef.current;
    const label = name.trim() || t('files.recorder.defaultName');
    const file = new File([blobRef.current], `${label}.${ext}`, { type: blobRef.current.type });
    onSave(file, label);
    discard();
  };

  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border-2 border-dashed border-line px-4 py-8 text-center">
      <Mic aria-hidden className={cn('size-6', phase === 'recording' ? 'text-danger' : 'text-muted')} />
      {phase === 'idle' && (
        <>
          <p className="text-sm text-muted">{t('files.recorder.orRecord')}</p>
          <Button size="sm" variant="secondary" icon={<Mic />} onClick={() => void start()}>{t('files.recorder.start')}</Button>
          <p className="text-xs text-muted">{t('files.recorder.maxLength')}</p>
        </>
      )}
      {phase === 'recording' && (
        <>
          <p className="num text-lg font-semibold text-danger" aria-live="polite">{formatDurationSec(elapsed)}</p>
          <Button size="sm" variant="danger" icon={<Square />} onClick={stop}>{t('files.recorder.stop')}</Button>
        </>
      )}
      {phase === 'recorded' && blobUrl && (
        <div className="flex w-full flex-col items-center gap-2">
          {/* eslint-disable-next-line jsx-a11y/media-has-caption -- mahalliy (serverga yuklanmagan) oldindan tinglash, matn versiyasi yo'q */}
          <audio controls src={blobUrl} className="h-9 w-full max-w-56" />
          <Input aria-label={t('files.recorder.nameAriaLabel')} value={name} onChange={(e) => setName(e.target.value)} placeholder={t('files.recorder.namePlaceholder')} className="w-56" />
          <div className="flex gap-2">
            <Button size="sm" variant="ghost" onClick={discard}>{t('cancel')}</Button>
            <Button size="sm" variant="primary" loading={pending} onClick={save}>{t('save')}</Button>
          </div>
        </div>
      )}
      {recErr && <p className="text-sm text-danger">{recErr}</p>}
    </div>
  );
}

/** M10 C A3 — "Matndan audio yaratish" kartasi: dialogni ochadi, sozlanmagan bo'lsa admin uchun havola ko'rsatadi. */
function TtsCard() {
  const { t } = useTranslation('audio');
  const [open, setOpen] = useState(false);
  const { data: settings } = useTtsSettings();
  const isAdmin = usePermission('*');
  const configured = settings?.provider !== 'none';

  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border-2 border-dashed border-line px-4 py-8 text-center">
      <AudioLines aria-hidden className="size-6 text-muted" />
      <p className="text-sm text-muted">{t('tts.cardDesc')}</p>
      {configured ? (
        <Button size="sm" variant="secondary" icon={<AudioLines />} onClick={() => setOpen(true)}>{t('tts.start')}</Button>
      ) : (
        <>
          <p className="text-xs text-danger">{t('tts.notConfigured')}</p>
          {isAdmin ? (
            <Link to="/settings/integrations" className="text-xs text-brand hover:underline">{t('tts.openSettings')}</Link>
          ) : (
            <p className="text-xs text-muted">{t('tts.notConfiguredAdmin')}</p>
          )}
        </>
      )}
      {open && <TtsDialog onClose={() => setOpen(false)} />}
    </div>
  );
}

function TtsDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation('audio');
  const toast = useToast();
  const [name, setName] = useState('');
  const [text, setText] = useState('');
  const [previewBlob, setPreviewBlob] = useState<Blob | null>(null);
  const [previewPending, setPreviewPending] = useState(false);
  const [previewErr, setPreviewErr] = useState<string | null>(null);
  const createM = useCreateTtsAudio();

  const trimmed = text.trim();
  const valid = trimmed.length !== 0 && trimmed.length <= TTS_MAX_CHARS;

  const preview = () => {
    setPreviewErr(null);
    setPreviewPending(true);
    apiClient.previewTts({ text: trimmed }).then(
      (blob) => { setPreviewBlob(blob); setPreviewPending(false); },
      (e) => { setPreviewErr(isApiError(e) ? e.message : t('tts.previewFailed')); setPreviewPending(false); },
    );
  };

  const save = () => {
    createM.mutate({ name: name.trim(), text: trimmed }, {
      onSuccess: ({ item }) => { toast({ kind: 'success', title: t('tts.toast.created', { name: item.name }) }); onClose(); },
    });
  };

  return (
    <Modal
      open
      onOpenChange={(v) => !v && onClose()}
      title={t('tts.dialogTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('tts.cancel')}</Button>
          <Button variant="primary" loading={createM.isPending} disabled={!valid} onClick={save}>{t('tts.save')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {isApiError(createM.error) && <p className="text-sm text-danger">{createM.error.message}</p>}
        <Field label={t('tts.nameLabel')} hint={t('tts.nameHint')}>
          {(a) => <Input {...a} autoFocus value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Field label={t('tts.textLabel')} hint={t('tts.textHint')}>
          {(a) => <Textarea {...a} className="min-h-24" maxLength={TTS_MAX_CHARS} value={text} onChange={(e) => setText(e.target.value)} />}
        </Field>
        <div className="flex items-center gap-3">
          <Button size="sm" variant="secondary" loading={previewPending} disabled={!valid} onClick={preview}>{t('tts.preview')}</Button>
          {previewBlob && <AudioPlayer variant="inline" src={() => Promise.resolve(previewBlob)} title={name || trimmed.slice(0, 40)} seed={trimmed.length} />}
        </div>
        {previewErr && <p className="text-sm text-danger">{previewErr}</p>}
      </div>
    </Modal>
  );
}

function MohTab() {
  const { t } = useTranslation('audio');
  const { data, isLoading, isError, refetch } = useMohClasses();
  const { data: audioData } = useAudio();
  const canManage = useCanEdit('apps');
  const toast = useToast();
  const createM = useCreateMohClass();
  const updateM = useUpdateMohClass();
  const deleteM = useDeleteMohClass();
  const [editing, setEditing] = useState<MohClass | 'new' | null>(null);
  const [deleting, setDeleting] = useState<MohClass | null>(null);
  const [deleteErr, setDeleteErr] = useState<Usage[] | null>(null);

  const classes = data?.items ?? [];
  const audioFiles = audioData?.items ?? [];

  if (isLoading) return <p className="rounded-md border border-dashed border-line px-3 py-6 text-center text-sm text-muted">{t('moh.loading')}</p>;
  if (isError) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-md border border-dashed border-line px-3 py-6 text-center text-sm text-muted">
        <p>{t('moh.loadFailed')}</p>
        <Button size="sm" variant="secondary" onClick={() => void refetch()}>{t('moh.retry')}</Button>
      </div>
    );
  }

  return (
    <div>
      {canManage && (
        <div className="mb-3">
          <Button size="sm" variant="secondary" icon={<Plus />} onClick={() => setEditing('new')}>{t('moh.newClass')}</Button>
        </div>
      )}

      <ul className="flex flex-col gap-2">
        {classes.map((m) => (
          <li key={m.id} className="flex items-center gap-3 rounded-lg border border-line bg-surface p-3 shadow-card">
            <Music2 aria-hidden className="size-4 shrink-0 text-brand" />
            <div className="min-w-0 flex-1">
              <p className="flex items-center gap-2 truncate font-medium text-fg">
                {m.name}
                {m.is_default && <Badge tone="accent">{t('moh.defaultBadge')}</Badge>}
                {m.shuffle && <Badge tone="neutral"><Shuffle aria-hidden className="size-3" /> {t('moh.shuffleBadge')}</Badge>}
              </p>
              <p className="text-sm text-muted">{t('moh.fileCount', { count: m.files.length })}</p>
            </div>
            {canManage && (
              <div className="flex shrink-0 items-center gap-1.5">
                {!m.is_default && (
                  <Button
                    size="sm" variant="ghost" icon={<Star />} aria-label={t('moh.setDefaultAriaLabel', { name: m.name })}
                    loading={updateM.isPending}
                    onClick={() => updateM.mutate({ id: m.id, payload: { updated_at: m.updated_at, is_default: true } }, {
                      onSuccess: () => toast({ kind: 'success', title: t('moh.toast.defaultSet', { name: m.name }) }),
                    })}
                  >{t('moh.setDefault')}</Button>
                )}
                <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('moh.editAriaLabel', { name: m.name })} onClick={() => setEditing(m)} />
                <Button
                  size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('moh.deleteAriaLabel', { name: m.name })}
                  disabled={m.is_default} title={m.is_default ? t('moh.cannotDeleteDefault') : undefined}
                  onClick={() => setDeleting(m)}
                />
              </div>
            )}
          </li>
        ))}
      </ul>
      {classes.length === 0 && <p className="rounded-md border border-dashed border-line px-3 py-6 text-center text-sm text-muted">{t('moh.empty')}</p>}

      {editing && (
        <MohClassDrawer
          mohClass={editing === 'new' ? undefined : editing}
          audioFiles={audioFiles}
          onClose={() => setEditing(null)}
          pending={createM.isPending || updateM.isPending}
          errorMessage={isApiError(createM.error) ? createM.error.message : isApiError(updateM.error) ? updateM.error.message : undefined}
          onSubmit={(payload) => {
            if (editing === 'new') {
              createM.mutate(payload, { onSuccess: ({ item }) => { toast({ kind: 'success', title: t('moh.toast.added', { name: item.name }) }); setEditing(null); } });
            } else {
              updateM.mutate({ id: editing.id, payload: { ...payload, updated_at: editing.updated_at } }, { onSuccess: ({ item }) => { toast({ kind: 'success', title: t('moh.toast.saved', { name: item.name }) }); setEditing(null); } });
            }
          }}
        />
      )}

      <Modal
        open={!!deleting}
        onOpenChange={(v) => !v && (setDeleting(null), setDeleteErr(null))}
        title={deleting ? t('moh.deleteModal.title', { name: deleting.name }) : ''}
        footer={
          <>
            <Button variant="ghost" onClick={() => { setDeleting(null); setDeleteErr(null); }}>{t('cancel')}</Button>
            {!deleteErr && (
              <Button
                variant="danger" loading={deleteM.isPending}
                onClick={() => deleting && deleteM.mutate(deleting.id, {
                  onSuccess: () => { toast({ kind: 'success', title: t('moh.toast.deleted', { name: deleting.name }) }); setDeleting(null); },
                  onError: (e) => { if (isApiError(e) && e.code === 'in_use') setDeleteErr(usagesOf(e)); else toast({ kind: 'error', title: t('moh.toast.deleteFailed'), description: e.message }); },
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
            <p className="text-sm text-danger">{t('moh.deleteModal.usagePrefix', { name: deleting?.name })}</p>
            <UsageList usages={deleteErr} />
          </div>
        ) : (
          <p className="text-sm text-muted">{t('moh.deleteModal.body', { name: deleting?.name })}</p>
        )}
      </Modal>
    </div>
  );
}

function MohClassDrawer({ mohClass, audioFiles, onClose, onSubmit, pending, errorMessage }: {
  mohClass?: MohClass;
  audioFiles: Audio[];
  onClose: () => void;
  onSubmit: (payload: { name: string; shuffle: boolean; file_ids: string[] }) => void;
  pending: boolean;
  errorMessage?: string;
}) {
  const { t } = useTranslation('audio');
  const [name, setName] = useState(mohClass?.name ?? '');
  const [shuffle, setShuffle] = useState(mohClass?.shuffle ?? false);
  const [fileIds, setFileIds] = useState<string[]>(mohClass?.files.map((f) => f.id) ?? []);

  const selected = fileIds.map((id) => audioFiles.find((f) => f.id === id)).filter((f): f is Audio => !!f);
  const available = audioFiles.filter((f) => !fileIds.includes(f.id));
  const valid = name.trim().length > 0 && fileIds.length > 0;

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={mohClass ? t('moh.drawer.editTitle', { name: mohClass.name }) : t('moh.drawer.newTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={() => onSubmit({ name: name.trim(), shuffle, file_ids: fileIds })}>{mohClass ? t('save') : t('add')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errorMessage && <p className="text-sm text-danger">{errorMessage}</p>}
        <Field label={t('moh.drawer.nameLabel')} required>
          {(a) => <Input {...a} autoFocus value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Toggle checked={shuffle} onCheckedChange={setShuffle} label={t('moh.drawer.shuffleLabel')} description={t('moh.drawer.shuffleDesc')} />

        <div>
          <p className="mb-2 text-sm font-medium text-fg">{t('moh.drawer.filesLabel')} <span className="text-muted">{t('moh.drawer.filesCount', { count: fileIds.length })}</span></p>
          {selected.length === 0 ? (
            <p className="rounded-md border border-dashed border-line px-3 py-4 text-center text-sm text-muted">{t('moh.drawer.noneSelected')}</p>
          ) : (
            <ul className="flex flex-wrap gap-1.5">
              {selected.map((f) => (
                <li key={f.id}>
                  <Badge tone="neutral" className="gap-1 pr-1">
                    {f.name}
                    <button type="button" aria-label={t('moh.drawer.removeFileAriaLabel', { name: f.name })} onClick={() => setFileIds((ids) => ids.filter((id) => id !== f.id))} className="rounded-full p-0.5 hover:bg-line">
                      ×
                    </button>
                  </Badge>
                </li>
              ))}
            </ul>
          )}
          {available.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {available.map((f) => (
                <button
                  key={f.id} type="button" onClick={() => setFileIds((ids) => [...ids, f.id])}
                  className="inline-flex h-6 items-center gap-1 rounded-sm border border-dashed border-line-strong px-1.5 text-xs text-muted hover:border-brand hover:text-fg"
                >
                  + {f.name}
                </button>
              ))}
            </div>
          ) : selected.length < audioFiles.length ? null : (
            <p className="mt-2 text-xs text-muted">{t('moh.drawer.noMoreFiles')}</p>
          )}
        </div>
      </div>
    </Drawer>
  );
}
