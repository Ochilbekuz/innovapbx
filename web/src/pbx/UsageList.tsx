import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import type { Usage } from '@/api/types';
import { USAGE_PATH } from '@/lib/usageError';

/** 409 `in_use` — "kim ishlatayotgani" ro'yxati, obyekt sahifasiga havola bilan. O'chirish tasdiqlash dialogida ishlatiladi. */
export function UsageList({ usages }: { usages: Usage[] }) {
  const { t } = useTranslation('common');
  const usageKindLabel: Record<string, string> = {
    inbound_route: t('usageList.kind.inbound_route'),
    time_condition: t('usageList.kind.time_condition'),
    ivr: t('usageList.kind.ivr'),
    ring_group: t('usageList.kind.ring_group'),
    queue: t('usageList.kind.queue'),
  };
  if (usages.length === 0) return null;
  return (
    <ul className="flex flex-col gap-1 rounded-md border border-line bg-surface-2/60 p-2.5 text-sm">
      {usages.map((u) => {
        const path = USAGE_PATH[u.kind];
        const label = <>{usageKindLabel[u.kind] ?? u.kind}: <span className="font-medium text-fg">{u.label}</span></>;
        return (
          <li key={`${u.kind}-${u.id}`}>
            {path ? <Link to={path} className="text-brand hover:underline">{label}</Link> : <span>{label}</span>}
          </li>
        );
      })}
    </ul>
  );
}
