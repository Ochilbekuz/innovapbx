import type { ReactNode } from 'react';
import { Hammer } from 'lucide-react';
import { AppShellPage } from './AppShellPage';

/**
 * M0 doirasidan tashqari ekranlar uchun bitta stub. Sarlavha va izoh recon.md dan — nom o'zbekcha, aniq.
 * Kelgusi bosqich (B1/B2/B3/B4) features.csv'dagi izohdan olinadi.
 */
export function ComingSoonPage({ title, reconId, note, crumbs, icon }: { title: string; reconId: string; note: string; crumbs?: string[]; icon?: ReactNode }) {
  return (
    <AppShellPage title={title} crumbs={crumbs}>
      <div className="flex min-h-[360px] flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-line-strong bg-surface px-6 py-16 text-center">
        <span aria-hidden className="grid size-12 place-items-center rounded-lg border border-line bg-surface-2 text-muted [&_svg]:size-6">
          {icon ?? <Hammer />}
        </span>
        <p className="font-display text-lg text-fg">{title} — tez orada</p>
        <p className="max-w-md text-sm text-muted">{note}</p>
        <p className="num text-xs text-disabled">{reconId}</p>
      </div>
    </AppShellPage>
  );
}
