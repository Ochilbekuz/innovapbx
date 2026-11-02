import { useTranslation } from 'react-i18next';
import { Database, FileText, KeyRound, Webhook as WebhookIcon } from 'lucide-react';
import { useAmoCrmConfig, useApiKeys, useBitrix24Config, useWebhooks } from '@/api/queries';
import type { CrmStatusState } from '@/api/types';
import { TabbedAdminPage } from '@/shell/TabbedAdminPage';
import { Badge, type Tone } from '@/ui/Status';
import { Button } from '@/ui/Button';
import { ApiKeysTab } from './ApiKeysTab';
import { CrmTab } from './CrmTab';
import { OneCTab } from './OneCTab';
import { SettingsTab } from './SettingsTab';
import { WebhooksTab } from './WebhooksTab';

type OverviewStatus = CrmStatusState | 'not_connected';
const STATUS_TONE: Record<OverviewStatus, Tone> = { ok: 'success', error: 'danger', disabled: 'neutral', not_connected: 'neutral' };

function StatusCard({
  icon, title, desc, status, onConfigure,
}: { icon: React.ReactNode; title: string; desc: string; status: OverviewStatus; onConfigure: () => void }) {
  const { t } = useTranslation('integrations');
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4 shadow-card">
      <div className="flex items-start justify-between gap-2">
        <span className="flex size-9 items-center justify-center rounded-md bg-accent-soft text-on-accent-soft [&_svg]:size-4.5">{icon}</span>
        <Badge tone={STATUS_TONE[status]}>{t(`status.${status}`)}</Badge>
      </div>
      <div>
        <h3 className="font-display text-base font-semibold">{title}</h3>
        <p className="mt-0.5 text-sm text-muted">{desc}</p>
      </div>
      <div><Button size="sm" variant="secondary" onClick={onConfigure}>{t('configure')}</Button></div>
    </div>
  );
}

function countStatus<T>(items: T[] | undefined, isActive: (item: T) => boolean): OverviewStatus {
  return (items ?? []).some(isActive) ? 'ok' : 'not_connected';
}

function crmOverviewStatus(data: { enabled: boolean; status: { state: CrmStatusState } } | undefined): OverviewStatus {
  if (!data || !data.enabled) return 'not_connected';
  return data.status.state;
}

function OverviewTab({ onNavigate }: { onNavigate: (tab: string) => void }) {
  const { t } = useTranslation('integrations');
  const apiKeys = useApiKeys();
  const webhooks = useWebhooks();
  const bitrix = useBitrix24Config();
  const amo = useAmoCrmConfig();

  const restStatus = countStatus(apiKeys.data?.items, (k) => !k.revoked_at);
  const webhooksStatus = countStatus(webhooks.data?.items, (w) => w.enabled);

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <StatusCard icon={<KeyRound />} title={t('cards.rest.title')} desc={t('cards.rest.desc')} status={restStatus} onConfigure={() => onNavigate('apiKeys')} />
      <StatusCard icon={<WebhookIcon />} title={t('cards.webhooks.title')} desc={t('cards.webhooks.desc')} status={webhooksStatus} onConfigure={() => onNavigate('webhooks')} />
      <StatusCard
        icon={<Database />} title={t('cards.bitrix24.title')} desc={t('cards.bitrix24.desc')}
        status={crmOverviewStatus(bitrix.data)} onConfigure={() => onNavigate('bitrix24')}
      />
      <StatusCard
        icon={<Database />} title={t('cards.amocrm.title')} desc={t('cards.amocrm.desc')}
        status={crmOverviewStatus(amo.data)} onConfigure={() => onNavigate('amocrm')}
      />
      <StatusCard icon={<FileText />} title={t('cards.onec.title')} desc={t('cards.onec.desc')} status="not_connected" onConfigure={() => onNavigate('onec')} />
    </div>
  );
}

/** S15 — /settings/integrations: REST API, vebhuklar, Bitrix24/amoCRM, 1C, sozlamalar. Faqat admin. M3b. */
export function IntegrationsPage() {
  return (
    <TabbedAdminPage
      ns="integrations" testId="integrations-page" defaultTab="overview"
      tabs={({ t, canManage, setTab }) => [
        { value: 'overview', label: t('tabs.overview'), content: <OverviewTab onNavigate={setTab} /> },
        { value: 'apiKeys', label: t('tabs.apiKeys'), content: <ApiKeysTab canManage={canManage} /> },
        { value: 'webhooks', label: t('tabs.webhooks'), content: <WebhooksTab canManage={canManage} /> },
        { value: 'bitrix24', label: t('tabs.bitrix24'), content: <CrmTab provider="bitrix24" canManage={canManage} /> },
        { value: 'amocrm', label: t('tabs.amocrm'), content: <CrmTab provider="amocrm" canManage={canManage} /> },
        { value: 'onec', label: t('tabs.onec'), content: <OneCTab /> },
        { value: 'settings', label: t('tabs.settings'), content: <SettingsTab canManage={canManage} /> },
      ]}
    />
  );
}
