import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pause, Pencil, Play, Square } from 'lucide-react';
import type { Campaign, CampaignStatus } from '@/api/types';
import { campaignActions, canEditCampaign, canImportContacts } from '@/domain/campaigns';
import { formatDateTimeShort } from '@/lib/time';
import { Button } from '@/ui/Button';
import { ConfirmDeleteModal } from '@/ui/ConfirmDeleteModal';
import { Drawer } from '@/ui/Dialog';
import { Badge, LiveDot, type Tone } from '@/ui/Status';
import { CampaignProgress } from './CampaignProgress';
import { ContactsPanel } from './ContactsPanel';
import { ImportPanel } from './ImportPanel';
import { useRunCampaign } from './useRunCampaign';

export const STATUS_TONE: Record<CampaignStatus, Tone> = {
  draft: 'neutral', running: 'success', paused: 'warning', completed: 'info', stopped: 'neutral',
};

export function CampaignStatusBadge({ status }: { status: CampaignStatus }) {
  const { t } = useTranslation('campaigns');
  return (
    <Badge tone={STATUS_TONE[status]}>
      {status === 'running' && <LiveDot />}
      {t(`status.${status}`)}
    </Badge>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-md border border-line bg-surface px-3 py-2">
      <span className={`num text-lg font-semibold leading-tight ${tone ?? 'text-fg'}`}>{value}</span>
      <span className="text-xs text-muted">{label}</span>
    </div>
  );
}

function Stats({ campaign }: { campaign: Campaign }) {
  const { t } = useTranslation('campaigns');
  const s = campaign.stats;
  const message = campaign.mode === 'message';
  const extra: [string, number, boolean][] = [
    ['skipped', s.skipped, message || s.skipped > 0],
    ['connected', s.connected, message && campaign.dtmf_connect],
    ['optout', s.optout, message && campaign.dtmf_optout],
  ];
  return (
    <div className="grid grid-cols-3 gap-2">
      <Stat label={t('detail.stat.done')} value={s.done} tone="text-success" />
      <Stat label={t('detail.stat.failed')} value={s.failed} tone={s.failed ? 'text-danger' : undefined} />
      <Stat label={t('detail.stat.open')} value={s.pending + s.dialing + s.retry} />
      {extra.filter(([, , shown]) => shown).map(([key, value]) => <Stat key={key} label={t(`detail.stat.${key}`)} value={value} />)}
    </div>
  );
}

function Timeline({ campaign }: { campaign: Campaign }) {
  const { t } = useTranslation('campaigns');
  if (!campaign.started_at) return <span>{t('detail.notStarted')}</span>;
  return (
    <>
      <span>{t('detail.started', { at: formatDateTimeShort(campaign.started_at) })}</span>
      {campaign.finished_at && <span>{t('detail.finished', { at: formatDateTimeShort(campaign.finished_at) })}</span>}
    </>
  );
}

function DetailFooter({ campaign, canManage, onEdit, onClose, onStop }: {
  campaign: Campaign; canManage: boolean; onEdit: () => void; onClose: () => void; onStop: () => void;
}) {
  const { t } = useTranslation('campaigns');
  const { run, busy } = useRunCampaign();
  const actions = canManage ? campaignActions(campaign.status) : [];
  const editable = canManage && canEditCampaign(campaign.status);
  return (
    <>
      {actions.includes('stop') && <Button variant="danger-ghost" icon={<Square />} className="mr-auto" onClick={onStop}>{t('action.stop')}</Button>}
      {editable && <Button variant="ghost" icon={<Pencil />} onClick={onEdit}>{t('action.edit')}</Button>}
      {actions.includes('pause') && (
        <Button icon={<Pause />} loading={busy(campaign, 'pause')} onClick={() => run(campaign, 'pause')}>{t('action.pause')}</Button>
      )}
      {actions.includes('start') && (
        <Button variant="primary" icon={<Play />} loading={busy(campaign, 'start')} disabled={campaign.stats.total === 0} onClick={() => run(campaign, 'start')}>
          {t(campaign.status === 'paused' ? 'action.resume' : 'action.start')}
        </Button>
      )}
      {actions.length === 0 && <Button variant="ghost" onClick={onClose}>{t('close')}</Button>}
    </>
  );
}

function StopConfirm({ campaign, open, onClose }: { campaign: Campaign; open: boolean; onClose: () => void }) {
  const { t } = useTranslation('campaigns');
  const { run, busy } = useRunCampaign();
  return (
    <ConfirmDeleteModal
      open={open}
      onClose={onClose}
      onConfirm={() => run(campaign, 'stop', onClose)}
      loading={busy(campaign, 'stop')}
      title={t('stopModal.title', { name: campaign.name })}
      body={t('stopModal.body')}
      cancelLabel={t('cancel')}
      deleteLabel={t('action.stop')}
    />
  );
}

function ImportSlot({ campaign }: { campaign: Campaign }) {
  const { t } = useTranslation('campaigns');
  if (canImportContacts(campaign.status)) return <ImportPanel campaign={campaign} />;
  return <p className="rounded-md border border-line bg-surface-2/50 px-3 py-2 text-sm text-muted">{t('detail.importClosed')}</p>;
}

/** Kampaniya kartasi: holat, statistika, raqam yuklash va kontaktlar. Ma'lumot jadval so'rovidan (jonli). */
export function CampaignDetail({
  campaign, canManage, onEdit, onClose,
}: {
  campaign: Campaign;
  canManage: boolean;
  onEdit: () => void;
  onClose: () => void;
}) {
  const { t } = useTranslation('campaigns');
  const [confirmStop, setConfirmStop] = useState(false);
  const subtitle = campaign.mode === 'message'
    ? campaign.audio_name ?? t('mode.message')
    : t('targetArrow', { number: campaign.target_number });

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={campaign.name}
      description={subtitle}
      footer={<DetailFooter campaign={campaign} canManage={canManage} onEdit={onEdit} onClose={onClose} onStop={() => setConfirmStop(true)} />}
    >
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-2.5">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
            <CampaignStatusBadge status={campaign.status} />
            <Timeline campaign={campaign} />
          </div>
          <CampaignProgress stats={campaign.stats} />
        </div>
        <Stats campaign={campaign} />
        {canManage && <ImportSlot campaign={campaign} />}
        <ContactsPanel campaign={campaign} />
      </div>
      <StopConfirm campaign={campaign} open={confirmStop} onClose={() => setConfirmStop(false)} />
    </Drawer>
  );
}
