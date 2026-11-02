import type { ReactNode } from 'react';
import { useSystemHealth, useConfigRevisions } from '@/api/queries';
import type { HealthItem } from '@/ui/Health';
import { formatTime, formatUptime } from '@/lib/time';
import { useSession } from '@/api';
import { AppShell, type Revision, type SystemInfo } from './AppShell';

/** Haqiqiy sahifalar uchun: tizim holati va reviziyani o'zi yuklab, `AppShell`ga beradi. */
export function AppShellPage({ title, crumbs, children }: { title: string; crumbs?: string[]; children: ReactNode }) {
  const isAdmin = useSession((s) => s.user?.role) === 'admin';
  const { data: health } = useSystemHealth(isAdmin);
  const { data: revisions } = useConfigRevisions(1, isAdmin);

  const items: HealthItem[] = health
    ? [
        { id: 'asterisk', label: 'Asterisk', level: health.asterisk.up ? 'ok' : 'crit', value: health.asterisk.version ?? undefined, reason: health.asterisk.up ? undefined : 'Asterisk prosessi javob bermayapti' },
        { id: 'db', label: 'Baza', level: health.db.up ? 'ok' : 'crit', reason: health.db.up ? undefined : 'PostgreSQLga ulanmadi' },
      ]
    : [];

  const last = revisions?.items[0];
  const revision: Revision = {
    number: health?.revision ?? Number(last?.id ?? 0),
    state: last?.status === 'rolled_back' ? 'rolled_back' : 'applied',
    at: last ? formatTime(last.created_at) : '—',
  };

  const ast = health?.asterisk;
  const system: SystemInfo | undefined = ast && {
    name: 'Innova PBX',
    detail: ast.up ? [ast.version && `Asterisk ${ast.version}`, ast.uptime_s != null && formatUptime(ast.uptime_s)].filter(Boolean).join(' · ') : 'Asterisk ishlamayapti',
  };

  return (
    <AppShell title={title} crumbs={crumbs} health={items} revision={revision} system={system}>
      {children}
    </AppShell>
  );
}
