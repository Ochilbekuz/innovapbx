import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowLeftRight, CheckCircle2, LogIn, LogOut, Pause, Phone, PhoneIncoming, PhoneOutgoing, Play, QrCode, Trash2, Voicemail } from 'lucide-react';
import { apiClient } from '@/api';
import {
  useMeCalls, useMeOverview, useMeQueueAction, useMeVoicemailDelete, useMeVoicemailHeard, useMeVoicemailMessages,
  usePatchMeExtension,
} from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { Call, CallDirection, MeExtensionOverview, MeQueueOverview } from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { daysAgo, formatDateTimeShort, formatDurationSec, isoDate } from '@/lib/time';
import { AppShellPage } from '@/shell/AppShellPage';
import { ClickToCallButton } from '@/softphone/ClickToCallButton';
import { Button } from '@/ui/Button';
import { Modal } from '@/ui/Dialog';
import { Field, Input } from '@/ui/Field';
import { AudioPlayer } from '@/pbx/AudioPlayer';
import { RecordingList } from '@/pbx/RecordingList';
import { FollowMeSection } from '@/screens/extensions/FollowMeSection';
import { QrConnectModal } from '@/screens/extensions/QrConnectModal';
import { Badge, type Tone } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

const DIRECTION_ICON: Record<CallDirection, typeof PhoneIncoming> = { in: PhoneIncoming, out: PhoneOutgoing, internal: ArrowLeftRight };
const DISPOSITION_TONE: Record<Call['disposition'], Tone> = { answered: 'success', no_answer: 'warning', busy: 'warning', failed: 'danger' };

/** S30 — mening kabinetim: DND/yo'naltirish, navbatlarim, bugungi statistika, qo'ng'iroqlar, ovozli pochta (M2b §4). */
export function MePage() {
  const { t } = useTranslation('me');
  const { data, isLoading, refetch } = useMeOverview();

  if (isLoading) return <AppShellPage title={t('title')}><div className="skeleton h-40" /></AppShellPage>;

  if (!data?.extension) {
    return (
      <AppShellPage title={t('title')}>
        <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-line px-6 py-12 text-center">
          <Phone aria-hidden className="size-8 text-muted" />
          <p className="font-display text-lg text-fg">{t('noExtension.title')}</p>
          <p className="max-w-md text-sm text-muted">{t('noExtension.body')}</p>
        </div>
      </AppShellPage>
    );
  }

  return (
    <AppShellPage title={t('title')}>
      <div className="flex flex-col gap-5">
        <div className="grid gap-4 lg:grid-cols-2">
          <DndCard ext={data.extension} onStale={() => void refetch()} />
          <StatsCard today={data.today} />
        </div>
        <div className="grid items-start gap-4 lg:grid-cols-[3fr_2fr]">
          <FollowMeSection target={null} compact className="rounded-lg border border-line bg-surface p-4 shadow-card" />
          <ConnectPhoneCard number={data.extension.number} />
        </div>
        <QueuesCard queues={data.queues} />
        <RecentCallsCard />
        <VoicemailCard />
      </div>
    </AppShellPage>
  );
}

function DndCard({ ext, onStale }: { ext: MeExtensionOverview; onStale: () => void }) {
  const { t } = useTranslation('me');
  const toast = useToast();
  const patchM = usePatchMeExtension();
  const [dnd, setDnd] = useState(ext.dnd);
  const [forwardAlways, setForwardAlways] = useState(ext.forward_always ?? '');

  const dirty = dnd !== ext.dnd || forwardAlways !== (ext.forward_always ?? '');
  const stale = isApiError(patchM.error) && patchM.error.code === 'stale';

  const save = () => {
    patchM.mutate(
      { dnd, forward_always: forwardAlways.trim() || null, updated_at: ext.updated_at },
      {
        onSuccess: () => toast({ kind: 'success', title: t('dnd.saved') }),
        onError: (e) => { if (!(isApiError(e) && e.code === 'stale')) toast({ kind: 'error', title: e.message }); },
      },
    );
  };

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-line bg-surface p-4 shadow-card">
      <p className="font-display text-base text-fg">{t('dnd.title')}</p>
      {stale && (
        <div className="flex flex-col gap-2 rounded-md border border-danger/30 bg-danger-soft px-3 py-2.5 text-sm text-on-danger-soft">
          <p>{t('dnd.conflict')}</p>
          <Button size="sm" variant="secondary" onClick={onStale}>{t('dnd.save')}</Button>
        </div>
      )}
      <Toggle checked={dnd} onCheckedChange={setDnd} label={t('dnd.title')} description={t('dnd.description')} />
      <Field label={t('dnd.forwardLabel')}>
        {(a) => <Input {...a} mono placeholder={t('dnd.forwardPlaceholder')} value={forwardAlways} onChange={(e) => setForwardAlways(e.target.value)} />}
      </Field>
      <Button size="sm" variant="primary" disabled={!dirty} loading={patchM.isPending} onClick={save} className="self-start">
        {t('dnd.save')}
      </Button>
    </div>
  );
}

function ConnectPhoneCard({ number }: { number: string }) {
  const { t } = useTranslation('followme');
  const [open, setOpen] = useState(false);
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4 shadow-card">
      <p className="flex items-center gap-1.5 font-display text-base text-fg"><QrCode aria-hidden className="size-4 text-brand" /> {t('qr.open')}</p>
      <p className="text-sm text-muted">{t('qr.cardBody', { number })}</p>
      <Button size="sm" variant="secondary" className="self-start" data-testid="me-qr-open" onClick={() => setOpen(true)}>{t('qr.open')}</Button>
      <QrConnectModal target={null} number={number} open={open} onOpenChange={setOpen} />
    </div>
  );
}

function StatsCard({ today }: { today: { answered: number; missed: number; talk_seconds: number } }) {
  const { t } = useTranslation('me');
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4 shadow-card">
      <p className="font-display text-base text-fg">{t('stats.title')}</p>
      <div className="grid grid-cols-3 gap-3">
        <div><p className="eyebrow">{t('stats.calls')}</p><p className="num text-2xl font-semibold text-fg">{today.answered + today.missed}</p></div>
        <div><p className="eyebrow">{t('stats.missed')}</p><p className="num text-2xl font-semibold text-fg">{today.missed}</p></div>
        <div><p className="eyebrow">{t('stats.talkTime')}</p><p className="num text-2xl font-semibold text-fg">{formatDurationSec(today.talk_seconds)}</p></div>
      </div>
    </div>
  );
}

function QueuesCard({ queues }: { queues: MeQueueOverview[] }) {
  const { t } = useTranslation(['me', 'common']);
  const toast = useToast();
  const actionM = useMeQueueAction();
  const [pausing, setPausing] = useState<MeQueueOverview | null>(null);
  const [reason, setReason] = useState('');

  const act = (q: MeQueueOverview, action: 'login' | 'logout' | 'unpause') => {
    actionM.mutate({ queueId: q.id, action }, {
      onError: (e) => toast({ kind: 'error', title: e.message }),
    });
  };
  const confirmPause = () => {
    if (!pausing) return;
    actionM.mutate({ queueId: pausing.id, action: 'pause', payload: { reason: reason.trim() || null } }, {
      onSuccess: () => { setPausing(null); setReason(''); },
      onError: (e) => toast({ kind: 'error', title: e.message }),
    });
  };

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4 shadow-card">
      <p className="font-display text-base text-fg">{t('queues.title')}</p>
      {queues.length === 0 ? (
        <p className="text-sm text-muted">{t('queues.empty')}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {queues.map((q) => (
            <li key={q.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2">
              <div className="flex min-w-0 items-center gap-2">
                <span className="truncate text-sm font-medium text-fg">{q.name}</span>
                <Badge tone={!q.logged_in ? 'neutral' : q.paused ? 'warning' : 'success'}>
                  {!q.logged_in ? t('queues.loggedOut') : q.paused ? t('queues.paused') : t('queues.loggedIn')}
                </Badge>
                {q.paused && q.pause_reason && <span className="text-xs text-muted">({q.pause_reason})</span>}
              </div>
              <div className="flex gap-1.5">
                {!q.dynamic ? (
                  <span className="text-xs text-muted">{t('queues.notDynamic')}</span>
                ) : !q.logged_in ? (
                  <Button size="sm" variant="secondary" icon={<LogIn />} loading={actionM.isPending} onClick={() => act(q, 'login')}>{t('queues.login')}</Button>
                ) : (
                  <>
                    <Button size="sm" variant="ghost" icon={<LogOut />} loading={actionM.isPending} onClick={() => act(q, 'logout')}>{t('queues.logout')}</Button>
                    {q.paused ? (
                      <Button size="sm" variant="secondary" icon={<Play />} loading={actionM.isPending} onClick={() => act(q, 'unpause')}>{t('queues.resume')}</Button>
                    ) : (
                      <Button size="sm" variant="secondary" icon={<Pause />} onClick={() => setPausing(q)}>{t('queues.pause')}</Button>
                    )}
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      <Modal
        open={!!pausing}
        onOpenChange={(v) => !v && (setPausing(null), setReason(''))}
        title={pausing ? t('queues.pause') : ''}
        footer={
          <>
            <Button variant="ghost" onClick={() => setPausing(null)}>{t('common:cancel')}</Button>
            <Button variant="primary" loading={actionM.isPending} onClick={confirmPause}>{t('queues.pause')}</Button>
          </>
        }
      >
        <Field label={t('queues.pauseReasonLabel')}>
          {(a) => <Input {...a} autoFocus placeholder={t('queues.pauseReasonPlaceholder')} value={reason} onChange={(e) => setReason(e.target.value)} />}
        </Field>
      </Modal>
    </div>
  );
}

function RecentCallsCard() {
  const { t } = useTranslation(['me', 'calls']);
  const { data, isLoading, isError } = useMeCalls({ from: `${daysAgo(1)}T00:00:00.000Z`, to: `${isoDate(new Date())}T23:59:59.999Z`, page: 1, size: 20 });
  const canManageRecordings = useCanEdit('reports');

  const columns: Column<Call>[] = [
    { key: 'started_at', header: t('me:recentCalls.column.time'), cell: (r) => <span className="num text-sm">{formatDateTimeShort(r.started_at)}</span> },
    {
      key: 'direction', header: t('me:recentCalls.column.direction'), cell: (r) => {
        const Icon = DIRECTION_ICON[r.direction];
        return <span className="flex items-center gap-1.5 text-sm"><Icon aria-hidden className="size-3.5 text-muted" />{t(`me:direction.${r.direction}`)}</span>;
      },
    },
    {
      key: 'from', header: t('me:recentCalls.column.from'), cell: (r) => {
        const number = r.direction === 'in' ? r.src : r.dst;
        return <span className="inline-flex items-center gap-1"><span className="num">{number}</span><ClickToCallButton number={number} /></span>;
      },
    },
    {
      key: 'disposition', header: '', cell: (r) => {
        if (r.disposition === 'answered') return null;
        return <Badge tone={DISPOSITION_TONE[r.disposition]}>{t(`calls:disposition.${r.disposition}`)}</Badge>;
      },
    },
    { key: 'duration', header: t('me:recentCalls.column.duration'), align: 'right', cell: (r) => <span className="num">{formatDurationSec(r.duration)}</span> },
    { key: 'recording', header: '', cell: (r) => <RecordingList recordings={r.recordings} canDelete={canManageRecordings} /> },
  ];

  return (
    <div className="rounded-lg border border-line bg-surface p-4 shadow-card">
      <p className="mb-3 font-display text-base text-fg">{t('me:recentCalls.title')}</p>
      <DataTable
        caption={t('me:recentCalls.title')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(r) => r.uniqueid}
        searchText={(r) => `${r.src} ${r.dst}`}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        empty={{ title: t('me:recentCalls.empty'), body: '' }}
        pageSize={10}
      />
    </div>
  );
}

function VoicemailCard() {
  const { t } = useTranslation('me');
  const toast = useToast();
  const { data, isLoading } = useMeVoicemailMessages();
  const heardM = useMeVoicemailHeard();
  const deleteM = useMeVoicemailDelete();

  return (
    <div className="rounded-lg border border-line bg-surface p-4 shadow-card">
      <p className="mb-3 flex items-center gap-1.5 font-display text-base text-fg"><Voicemail aria-hidden className="size-4 text-brand" /> {t('voicemail.title')}</p>
      {isLoading ? (
        <div className="skeleton h-16" />
      ) : !data || data.items.length === 0 ? (
        <p className="rounded-md border border-dashed border-line px-3 py-4 text-center text-sm text-muted">{t('voicemail.empty')}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {data.items.map((m) => (
            <li key={m.id} className="flex items-center gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="num text-sm font-medium text-fg">{m.callerid}</span>
                  {m.folder === 'inbox' && <Badge tone="accent">{t('voicemail.unread')}</Badge>}
                </div>
                <p className="num text-xs text-muted">{formatDateTimeShort(m.received_at)} · {formatDurationSec(m.duration_s)}</p>
              </div>
              <AudioPlayer variant="inline" src={() => apiClient.meVoicemailAudio(m.id)} title={m.callerid} seed={m.id.length} />
              {m.folder === 'inbox' && (
                <Button size="sm" variant="ghost" iconOnly icon={<CheckCircle2 />} aria-label={t('voicemail.listen')} onClick={() => heardM.mutate(m.id)} />
              )}
              <Button
                size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('voicemail.delete')}
                onClick={() => deleteM.mutate(m.id, { onError: (e) => toast({ kind: 'error', title: e.message }) })}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
