import { TabbedAdminPage } from '@/shell/TabbedAdminPage';
import { BackupsTab } from './BackupsTab';
import { SettingsTab } from './SettingsTab';
import { RestoreTab } from './RestoreTab';

/** S34 — /settings/backup: zaxiralash va tiklash (M4b). Faqat `system.manage` huquqi bilan toʻliq boshqariladi. */
export function BackupPage() {
  return (
    <TabbedAdminPage
      ns="backup" testId="backup-page" defaultTab="backups"
      tabs={({ t, canManage, setTab }) => [
        { value: 'backups', label: t('tabs.backups'), content: <BackupsTab canManage={canManage} onGoToSettings={() => setTab('settings')} /> },
        { value: 'settings', label: t('tabs.settings'), content: <SettingsTab canManage={canManage} /> },
        { value: 'restore', label: t('tabs.restore'), content: <RestoreTab canManage={canManage} /> },
      ]}
    />
  );
}
