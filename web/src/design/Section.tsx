import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

export function Section({ id, index, title, lead, used, children, className }: {
  id: string; index: string; title: string; lead?: ReactNode; used?: string; children: ReactNode; className?: string;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className={cn('scroll-mt-20 border-t border-line pt-10', className)}>
      <header className="mb-6 grid gap-x-8 gap-y-2 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <div className="flex items-baseline gap-3">
          <span className="num text-sm text-brand">{index}</span>
          <h2 id={`${id}-h`} className="font-display text-xl text-fg">{title}</h2>
        </div>
        <div className="flex flex-col gap-1.5 lg:pt-1">
          {lead && <p className="max-w-[62ch] text-base text-muted">{lead}</p>}
          {used && <p className="num text-xs text-muted">Ekranlar: {used}</p>}
        </div>
      </header>
      {children}
    </section>
  );
}

/** Holat namunasi: kichik yorliq + namuna. */
export function Specimen({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div className={cn('flex flex-col gap-2', className)}>
      <span className="eyebrow">{label}</span>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </div>
  );
}

export function Panel({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('rounded-lg border border-line bg-surface p-5 shadow-card', className)}>{children}</div>;
}
