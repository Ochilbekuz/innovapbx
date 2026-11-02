import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CheckCircle2, Mail, MessageCircle, Pencil, Plus, ShieldAlert, Trash2 } from 'lucide-react';
import {
  useAudio, useCreateVoicemailBox, useDeleteVoicemailBox, useDeleteVoicemailMessage, useExtensions,
  useMarkVoicemailMessageHeard, useUpdateVoicemailBox, useVoicemailBoxes, useVoicemailMessages,
} from '@/api/queries';
import { apiClient } from '@/api';
import { isApiError } from '@/api/errors';
import type { CreateVoicemailBoxPayload, Extension, UpdateVoicemailBoxPayload, VoicemailBox, VoicemailMessage } from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { applyToast } from '@/lib/applyToast';
import { formatDateTimeShort, formatDurationSec } from '@/lib/time';
import { usagesOf } from '@/lib/usageError';
import { AudioPlayer } from '@/pbx/AudioPlayer';
import { UsageList } from '@/pbx/UsageList';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Drawer, Modal } from '@/ui/Dialog';
import { Field, Input, Segmented, Select } from '@/ui/Field';
import { Badge } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

const PIN_RE = /^\d{4,8}$/;
const MAILBOX_RE = /^[0-9]{2,10}$/;

function ownerLabel(box: VoicemailBox, t: (k: string, o?: Record<string, unknown>) => string): string {
  return box.extension ? `${box.extension.name} (${box.extension.number})` : t('ownerShared', { mailbox: box.mailbox });
}

/** S23 — Ovozli pochta: qutilar ro'yxati, yaratish/tahrirlash, xabarlarni tinglash/o'chirish. */
export function VoicemailPage() {
  const { t } = useTranslation('voicemail');
  const { data, isLoading, isError, refetch } = useVoicemailBoxes({});
  const { data: extensions } = useExtensions({ page: 1, size: 200 });
  const { data: audio } = useAudio();
  const canManage = useCanEdit('extensions');
  const toast = useToast();

  const [editing, setEditing] = useState<VoicemailBox | 'new' | null>(null);
  const [deleting, setDeleting] = useState<VoicemailBox | null>(null);
  const [deleteErr, setDeleteErr] = useState<ReturnType<typeof usagesOf> | null>(null);

  const createM = useCreateVoicemailBox();
  const updateM = useUpdateVoicemailBox();
  const deleteM = useDeleteVoicemailBox();
  const close = () => { setEditing(null); createM.reset(); updateM.reset(); };
  const mutation = editing === 'new' ? createM : updateM;

  const freeExtensions = (extensions?.items ?? []).filter((e) => !(data?.items ?? []).some((b) => b.extension?.id === e.id));

  const columns: Column<VoicemailBox>[] = [
    { key: 'owner', header: t('column.owner'), cell: (r) => <span className="block max-w-[220px] truncate font-medium">{ownerLabel(r, t)}</span> },
    { key: 'mailbox', header: t('column.mailbox'), sortValue: (r) => r.mailbox, cell: (r) => <span className="num text-muted">{r.mailbox}</span> },
    { key: 'new', header: t('column.newCount'), cell: (r) => <Badge tone={r.counts.new > 0 ? 'accent' : 'neutral'} mono>{r.counts.new}</Badge> },
    { key: 'old', header: t('column.oldCount'), cell: (r) => <Badge tone="neutral" mono>{r.counts.old}</Badge> },
    {
      key: 'notify', header: t('column.notify'), cell: (r) => (
        <div className="flex gap-1">
          {r.email_notify && <Badge tone="info"><Mail aria-hidden className="size-3" /> {t('badge.email')}</Badge>}
          {r.telegram_notify && <Badge tone="info"><MessageCircle aria-hidden className="size-3" /> {t('badge.telegram')}</Badge>}
        </div>
      ),
    },
    {
      key: 'actions', header: '', align: 'right', cell: (r) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('editAriaLabel', { mailbox: r.mailbox })} disabled={!canManage} onClick={() => setEditing(r)} />
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('deleteAriaLabel', { mailbox: r.mailbox })} disabled={!canManage} onClick={() => setDeleting(r)} />
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
        rowId={(r) => r.id}
        searchText={(r) => `${r.mailbox} ${r.extension?.name ?? ''} ${r.extension?.number ?? ''}`}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        onRowOpen={canManage ? (r) => setEditing(r) : undefined}
        empty={{ title: t('empty.title'), body: t('empty.body'), action: canManage ? <Button size="sm" onClick={() => setEditing('new')}>{t('empty.action')}</Button> : undefined }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setEditing('new')}>{t('newBox')}</Button> : undefined}
      />

      {editing && (
        <VoicemailDrawer
          box={editing === 'new' ? undefined : editing}
          freeExtensions={freeExtensions}
          greetings={audio?.items ?? []}
          pending={mutation.isPending}
          errorField={isApiError(mutation.error) ? mutation.error.field : undefined}
          errorMessage={isApiError(mutation.error) ? mutation.error.message : undefined}
          onClose={close}
          onSubmitCreate={(payload) => createM.mutate(payload, { onSuccess: (res) => { close(); toast(applyToast(res.apply, t('toast.created'))); } })}
          onSubmitUpdate={(payload) => editing !== 'new' && updateM.mutate({ id: editing.id, payload: { ...payload, updated_at: editing.updated_at } }, {
            onSuccess: (res) => { close(); toast(applyToast(res.apply, t('toast.saved'))); },
          })}
        />
      )}

      <Modal
        open={!!deleting}
        onOpenChange={(v) => !v && (setDeleting(null), setDeleteErr(null))}
        title={deleting ? t('deleteModal.title', { mailbox: deleting.mailbox }) : ''}
        footer={
          <>
            <Button variant="ghost" onClick={() => { setDeleting(null); setDeleteErr(null); }}>{t('cancel')}</Button>
            {!deleteErr && (
              <Button
                variant="danger" loading={deleteM.isPending}
                onClick={() => deleting && deleteM.mutate(deleting.id, {
                  onSuccess: () => { toast({ kind: 'success', title: t('toast.deleted', { mailbox: deleting.mailbox }) }); setDeleting(null); },
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
            <p className="text-sm text-danger">{t('deleteModal.usagePrefix', { mailbox: deleting?.mailbox })}</p>
            <UsageList usages={deleteErr} />
          </div>
        ) : (
          <p className="text-sm text-muted">{t('deleteModal.body', { mailbox: deleting?.mailbox })}</p>
        )}
      </Modal>
    </AppShellPage>
  );
}

type OwnerType = 'extension' | 'shared';
type Greeting = { id: string; name: string };

function VoicemailDrawer({
  box, freeExtensions, greetings, onClose, onSubmitCreate, onSubmitUpdate, pending, errorField, errorMessage,
}: {
  box?: VoicemailBox;
  freeExtensions: Extension[];
  greetings: Greeting[];
  onClose: () => void;
  onSubmitCreate: (payload: CreateVoicemailBoxPayload) => void;
  onSubmitUpdate: (payload: Omit<UpdateVoicemailBoxPayload, 'updated_at'>) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('voicemail');
  const [ownerType, setOwnerType] = useState<OwnerType>('extension');
  const [extensionId, setExtensionId] = useState(freeExtensions[0]?.id ?? '');
  const [mailbox, setMailbox] = useState('');
  const [pin, setPin] = useState('');
  const [email, setEmail] = useState(box?.email ?? '');
  const [emailNotify, setEmailNotify] = useState(box?.email_notify ?? true);
  const [telegramNotify, setTelegramNotify] = useState(box?.telegram_notify ?? false);
  const [chatId, setChatId] = useState(box?.telegram_chat_id ?? '');
  const [attachAudio, setAttachAudio] = useState(box?.attach_audio ?? false);
  const [greetingId, setGreetingId] = useState(box?.greeting?.id ?? '');

  const pinValid = box ? pin === '' || PIN_RE.test(pin) : PIN_RE.test(pin);
  const ownerValid = box ? true : ownerType === 'extension' ? !!extensionId : MAILBOX_RE.test(mailbox.trim());
  const valid = pinValid && ownerValid;

  const submit = () => {
    if (!valid) return;
    const common = {
      email: email.trim() || null,
      email_notify: emailNotify,
      telegram_notify: telegramNotify,
      telegram_chat_id: chatId.trim() || null,
      attach_audio: attachAudio,
      greeting_audio_id: greetingId || null,
    };
    if (box) {
      onSubmitUpdate({ ...common, pin: pin.trim() || null });
    } else {
      onSubmitCreate({
        ...common,
        pin: pin.trim(),
        extension_id: ownerType === 'extension' ? extensionId : null,
        mailbox: ownerType === 'shared' ? mailbox.trim() : null,
      });
    }
  };

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={box ? t('form.editTitle', { mailbox: box.mailbox }) : t('form.newTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={submit}>{box ? t('save') : t('create')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errorMessage && !['pin', 'email', 'telegram_chat_id', 'mailbox', 'extension_id'].includes(errorField ?? '') && (
          <p className="text-sm text-danger">{errorMessage}</p>
        )}

        {!box && (
          <Field label={t('form.ownerLabel')} required>
            {() => (
              <div className="flex flex-col gap-3">
                <Segmented
                  label={t('form.ownerLabel')} value={ownerType} onChange={setOwnerType}
                  options={[{ value: 'extension', label: t('form.ownerExtension') }, { value: 'shared', label: t('form.ownerShared') }]}
                />
                {ownerType === 'extension' ? (
                  freeExtensions.length === 0 ? (
                    <p className="text-sm text-muted">{t('form.noFreeExtensions')}</p>
                  ) : (
                    <Select
                      value={extensionId} onValueChange={setExtensionId}
                      options={freeExtensions.map((e) => ({ value: e.id, label: `${e.name} (${e.number})` }))}
                    />
                  )
                ) : (
                  <Input mono maxLength={10} value={mailbox} onChange={(e) => setMailbox(e.target.value)} placeholder="200" aria-label={t('form.mailboxLabel')} />
                )}
                {(errorField === 'mailbox' || errorField === 'extension_id') && errorMessage && <p className="text-sm text-danger">{errorMessage}</p>}
              </div>
            )}
          </Field>
        )}

        <Field label={t('form.pinLabel')} required={!box} error={errorField === 'pin' ? errorMessage : undefined} hint={box ? t('form.pinHintEdit') : t('form.pinHintCreate')}>
          {(a) => <Input {...a} mono inputMode="numeric" maxLength={8} value={pin} onChange={(e) => setPin(e.target.value)} />}
        </Field>
        <Field label={t('form.emailLabel')} aside={t('form.optional')} error={errorField === 'email' ? errorMessage : undefined}>
          {(a) => <Input {...a} type="email" value={email} onChange={(e) => setEmail(e.target.value)} />}
        </Field>
        <Toggle checked={emailNotify} onCheckedChange={setEmailNotify} label={t('form.emailNotifyLabel')} description={t('form.emailNotifyDesc')} />
        <Toggle checked={telegramNotify} onCheckedChange={setTelegramNotify} label={t('form.telegramNotifyLabel')} description={t('form.telegramNotifyDesc')} />
        <Field label={t('form.telegramChatIdLabel')} aside={t('form.optional')} error={errorField === 'telegram_chat_id' ? errorMessage : undefined} hint={t('form.telegramChatIdHint')}>
          {(a) => <Input {...a} mono value={chatId} onChange={(e) => setChatId(e.target.value)} />}
        </Field>
        <Toggle checked={attachAudio} onCheckedChange={setAttachAudio} label={t('form.attachAudioLabel')} description={t('form.attachAudioDesc')} />
        <Field label={t('form.greetingLabel')}>
          {({ id }) => (
            <Select
              id={id} value={greetingId} onValueChange={setGreetingId}
              options={[{ value: '', label: t('form.greetingNone') }, ...greetings.map((g) => ({ value: g.id, label: g.name }))]}
            />
          )}
        </Field>

        {box && <VoicemailMessages boxId={box.id} />}
      </div>
    </Drawer>
  );
}

function VoicemailMessages({ boxId }: { boxId: string }) {
  const { t } = useTranslation('voicemail');
  const toast = useToast();
  const { data, isLoading } = useVoicemailMessages(boxId);
  const markHeardM = useMarkVoicemailMessageHeard();
  const deleteM = useDeleteVoicemailMessage();
  const [deleting, setDeleting] = useState<VoicemailMessage | null>(null);

  const markHeard = (msg: VoicemailMessage) => markHeardM.mutate({ boxId, msg: msg.id }, {
    onSuccess: () => toast({ kind: 'success', title: t('toast.markedHeard') }),
    onError: (e) => toast({ kind: 'error', title: t('toast.markHeardFailed'), description: e.message }),
  });

  return (
    <div className="mt-2 border-t border-line pt-4">
      <p className="mb-2 text-sm font-medium text-fg">{t('messages.title')}</p>
      {isLoading ? (
        <div className="skeleton h-16" />
      ) : !data || data.items.length === 0 ? (
        <p className="rounded-md border border-dashed border-line px-3 py-4 text-center text-sm text-muted">{t('messages.empty')}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {data.items.map((m) => (
            <li key={m.id} className="flex items-center gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="num text-sm font-medium text-fg">{m.callerid}</span>
                  {m.folder === 'inbox' ? <Badge tone="accent">{t('messages.new')}</Badge> : <Badge tone="neutral">{t('messages.heard')}</Badge>}
                </div>
                <p className="num text-xs text-muted">{formatDateTimeShort(m.received_at)} · {formatDurationSec(m.duration_s)}</p>
              </div>
              <AudioPlayer variant="inline" src={() => apiClient.fetchVoicemailMessageAudio(boxId, m.id)} title={m.callerid} seed={m.id.length} />
              {m.folder === 'inbox' && (
                <Button size="sm" variant="ghost" iconOnly icon={<CheckCircle2 />} aria-label={t('messages.markHeardAriaLabel', { caller: m.callerid })} loading={markHeardM.isPending} onClick={() => markHeard(m)} />
              )}
              <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('messages.deleteAriaLabel', { caller: m.callerid })} onClick={() => setDeleting(m)} />
            </li>
          ))}
        </ul>
      )}

      <Modal
        open={!!deleting}
        onOpenChange={(v) => !v && setDeleting(null)}
        title={t('deleteMessageModal.title')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleting(null)}>{t('cancel')}</Button>
            <Button
              variant="danger" loading={deleteM.isPending}
              onClick={() => deleting && deleteM.mutate({ boxId, msg: deleting.id }, {
                onSuccess: () => { toast({ kind: 'success', title: t('toast.messageDeleted') }); setDeleting(null); },
                onError: (e) => { toast({ kind: 'error', title: t('toast.messageDeleteFailed'), description: e.message }); setDeleting(null); },
              })}
            >
              {t('delete')}
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted">{t('deleteMessageModal.body')}</p>
      </Modal>
    </div>
  );
}
