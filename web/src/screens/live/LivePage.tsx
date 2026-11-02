import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowLeftRight, Ear, MessageSquare, PhoneIncoming, PhoneOutgoing, TriangleAlert, UserPlus } from 'lucide-react';
import { useLive, useLiveSpy } from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { LiveCall, LiveCallDirection, LiveExtension, LiveExtensionState, LiveQueue, LiveSpyMode } from '@/api/types';
import { formatDurationSec } from '@/lib/time';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Badge, type Tone } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';
import { useToast } from '@/ui/Toast';

const DIRECTION_ICON: Record<LiveCallDirection, typeof PhoneIncoming> = { inbound: PhoneIncoming, outbound: PhoneOutgoing, internal: ArrowLeftRight };
const EXT_STATE_TONE: Record<LiveExtensionState, Tone> = { idle: 'neutral', ringing: 'warning', busy: 'danger', unavailable: 'neutral', dnd: 'info' };
const SPY_MODES: LiveSpyMode[] = ['listen', 'whisper', 'barge'];
const SPY_ICON: Record<LiveSpyMode, typeof Ear> = { listen: Ear, whisper: MessageSquare, barge: UserPlus };

/** `started_at`dan hozirgacha o'tgan soniyalar — 1s tiklash bilan jonli yangilanadi. */
function useNowTick() {
  const [, setN] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setN((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, []);
}

function elapsedSec(startedAt: string): number {
  return Math.max(0, Math.round((Date.now() - Date.parse(startedAt)) / 1000));
}

/** S29 — jonli monitoring: faol qo'ng'iroqlar, navbat kartalari, ichki raqamlar holati, nazorat (M2b §2). */
export function LivePage() {
  const { t } = useTranslation('live');
  const toast = useToast();
  const { data, isError } = useLive();
  const spyM = useLiveSpy();
  useNowTick();

  const spy = (call: LiveCall, mode: LiveSpyMode) => {
    spyM.mutate({ call_id: call.id, mode }, {
      onSuccess: () => toast({ kind: 'success', title: t('spy.started') }),
      onError: (e) => toast({ kind: 'error', title: t('spy.failed'), description: isApiError(e) && e.code === 'no_extension' ? t('spy.noExtension') : e.message }),
    });
  };

  const columns: Column<LiveCall>[] = [
    {
      key: 'direction', header: '', width: '32px', cell: (r) => {
        const Icon = DIRECTION_ICON[r.direction];
        return <Icon aria-hidden className="size-4 text-muted" />;
      },
    },
    { key: 'from', header: t('activeCalls.column.from'), cell: (r) => <span className="num">{r.from}</span> },
    { key: 'to', header: t('activeCalls.column.to'), cell: (r) => <span className="num">{r.to}</span> },
    { key: 'status', header: t('activeCalls.column.status'), cell: (r) => <Badge tone={r.state === 'up' ? 'success' : r.state === 'ringing' ? 'warning' : 'neutral'}>{t(`status.${r.state === 'up' ? 'talking' : r.state === 'ringing' ? 'ringing' : 'hold'}`)}</Badge> },
    { key: 'duration', header: t('activeCalls.column.duration'), align: 'right', cell: (r) => <span className="num">{formatDurationSec(elapsedSec(r.started_at))}</span> },
    {
      key: 'spy', header: '', align: 'right', cell: (r) => (
        <div className="flex justify-end gap-1">
          {SPY_MODES.map((mode) => {
            const Icon = SPY_ICON[mode];
            return (
              <Button key={mode} size="sm" variant="ghost" iconOnly icon={<Icon />} aria-label={t(`spy.${mode}`)} title={t(`spy.${mode}`)} loading={spyM.isPending} onClick={() => spy(r, mode)} />
            );
          })}
        </div>
      ),
    },
  ];

  return (
    <AppShellPage title={t('title')}>
      <div className="flex flex-col gap-5">
        {data?.asterisk === 'down' && (
          <div role="alert" className="flex items-center gap-2 rounded-md border border-danger/30 bg-danger-soft px-3 py-2.5 text-sm text-on-danger-soft">
            <TriangleAlert aria-hidden className="size-4 shrink-0" />
            <div><p className="font-medium">{t('asteriskDown.title')}</p><p>{t('asteriskDown.body')}</p></div>
          </div>
        )}

        <div className="rounded-lg border border-line bg-surface p-4 shadow-card">
          <p className="mb-3 font-display text-base text-fg">{t('activeCalls.title')}</p>
          <DataTable
            caption={t('activeCalls.title')}
            rows={data?.calls ?? []}
            columns={columns}
            rowId={(r) => r.id}
            searchText={(r) => `${r.from} ${r.to}`}
            state={isError ? 'error' : 'ready'}
            empty={{ title: t('activeCalls.empty'), body: '' }}
          />
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {(data?.queues ?? []).map((q) => <QueueCard key={q.id} queue={q} />)}
        </div>

        <ExtensionGrid extensions={data?.extensions ?? []} />
      </div>
    </AppShellPage>
  );
}

function QueueCard({ queue }: { queue: LiveQueue }) {
  const { t } = useTranslation('live');
  const online = queue.agents.filter((a) => a.logged_in).length;
  const longestWaitSec = queue.waiting.length > 0 ? Math.max(...queue.waiting.map((w) => elapsedSec(w.since))) : 0;
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-line bg-surface p-4 shadow-card">
      <p className="truncate font-display text-base text-fg">{queue.name}</p>
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted">{t('queues.waiting')}</span>
        <span className="num font-medium text-fg">{queue.waiting.length}</span>
      </div>
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted">{t('queues.longestWait')}</span>
        <span className="num font-medium text-fg">{queue.waiting.length > 0 ? formatDurationSec(longestWaitSec) : '—'}</span>
      </div>
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted">{t('queues.agents')}</span>
        <span className="num font-medium text-fg">{t('queues.agentsOnline', { online, total: queue.agents.length })}</span>
      </div>
    </div>
  );
}

function ExtensionGrid({ extensions }: { extensions: LiveExtension[] }) {
  const { t } = useTranslation('live');
  return (
    <div className="rounded-lg border border-line bg-surface p-4 shadow-card">
      <p className="mb-3 font-display text-base text-fg">{t('extensions.title')}</p>
      {extensions.length === 0 ? (
        <p className="text-sm text-muted">{t('extensions.empty')}</p>
      ) : (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
          {extensions.map((e) => (
            <div key={e.number} className="flex flex-col gap-1 rounded-md border border-line bg-surface-2/60 px-3 py-2">
              <span className="num text-sm font-medium text-fg">{e.number}</span>
              <span className="truncate text-xs text-muted">{e.name}</span>
              <Badge tone={EXT_STATE_TONE[e.state]} className="self-start">{t(`extensions.status.${e.state}`)}</Badge>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
