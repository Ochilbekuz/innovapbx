import { TabbedAdminPage } from '@/shell/TabbedAdminPage';
import { DevicesTab } from './DevicesTab';
import { SettingsTab } from './SettingsTab';
import { LogTab } from './LogTab';

/** S35 — /devices: apparatlarni avtoprovizioning (M4a). Faqat `system.manage` huquqi bilan toʻliq boshqariladi. */
export function DevicesPage() {
  return (
    <TabbedAdminPage
      ns="devices" testId="devices-page" defaultTab="devices"
      tabs={({ t, canManage }) => [
        { value: 'devices', label: t('tabs.devices'), content: <DevicesTab canManage={canManage} /> },
        { value: 'settings', label: t('tabs.settings'), content: <SettingsTab canManage={canManage} /> },
        { value: 'log', label: t('tabs.log'), content: <LogTab /> },
      ]}
    />
  );
}
