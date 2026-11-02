import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { ShieldAlert } from 'lucide-react';
import { usePermission } from '@/auth/permissions';
import { AppShellPage } from '@/shell/AppShellPage';
import { Tabs, type TabItem } from '@/ui/Tabs';

export type AdminTabsContext = { t: TFunction; canManage: boolean; setTab: (value: string) => void };

/** Tablari bor admin sahifasi qolipi (Integratsiyalar, Qurilmalar, Zaxira): `system.manage` bo'lmasa «faqat o'qish»
 * banneri + tablar. Matnlar `ns` i18n nomlar fazosidan: `title`, `readOnlyBanner`. */
export function TabbedAdminPage({
  ns, testId, defaultTab, tabs,
}: {
  ns: string;
  testId: string;
  defaultTab: string;
  tabs: (ctx: AdminTabsContext) => TabItem[];
}) {
  const { t } = useTranslation(ns);
  const canManage = usePermission('system.manage');
  const [tab, setTab] = useState(defaultTab);
  return (
    <AppShellPage title={t('title')}>
      <div data-testid={testId}>
        {!canManage && (
          <p className="mb-4 flex items-center gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2 text-sm text-muted">
            <ShieldAlert aria-hidden className="size-4 shrink-0" />
            {t('readOnlyBanner')}
          </p>
        )}
        <Tabs label={t('title')} items={tabs({ t, canManage, setTab })} value={tab} onValueChange={setTab} />
      </div>
    </AppShellPage>
  );
}
