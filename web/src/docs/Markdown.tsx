// `markdown.ts` AST'ini React elementlariga aylantiradi. HTML satr ishlatilmaydi; havolalar `safeHref`dan o'tadi.
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { ExternalLink, Info, Lightbulb, OctagonAlert, TriangleAlert } from 'lucide-react';
import { cn } from '@/lib/cn';
import { safeHref, type Block, type CalloutKind, type Inline, type ListItem, type SubList } from './markdown';

function InlineLink({ href, children }: { href: string; children: ReactNode }) {
  const safe = safeHref(href);
  const cls = 'font-medium text-accent underline decoration-accent/30 underline-offset-2 hover:decoration-accent';
  if (!safe) return <span>{children}</span>;
  if (safe.startsWith('/')) return <Link to={safe} className={cls}>{children}</Link>;
  if (safe.startsWith('#')) return <a href={safe} className={cls}>{children}</a>;
  return (
    <a href={safe} target="_blank" rel="noopener noreferrer" className={cn(cls, 'inline-flex items-baseline gap-0.5')}>
      {children}<ExternalLink aria-hidden className="size-3 self-center" />
    </a>
  );
}

export function Inlines({ nodes }: { nodes: Inline[] }) {
  return (
    <>
      {nodes.map((n, i) => {
        switch (n.t) {
          case 'text': return n.v;
          case 'strong': return <strong key={i} className="font-semibold text-fg"><Inlines nodes={n.c} /></strong>;
          case 'em': return <em key={i}><Inlines nodes={n.c} /></em>;
          case 'code': return <code key={i} className="num rounded-sm border border-line bg-surface-2 px-1 py-px text-[0.92em] text-fg">{n.v}</code>;
          case 'link': return <InlineLink key={i} href={n.href}><Inlines nodes={n.c} /></InlineLink>;
        }
      })}
    </>
  );
}

const CALLOUT: Record<CalloutKind, { cls: string; icon: ReactNode }> = {
  note: { cls: 'border-info/30 bg-info-soft text-on-info-soft', icon: <Info /> },
  tip: { cls: 'border-success/30 bg-success-soft text-on-success-soft', icon: <Lightbulb /> },
  warning: { cls: 'border-warning/30 bg-warning-soft text-on-warning-soft', icon: <TriangleAlert /> },
  caution: { cls: 'border-danger/25 bg-danger-soft text-on-danger-soft', icon: <OctagonAlert /> },
};

function Callout({ kind, blocks }: { kind: CalloutKind; blocks: Block[] }) {
  const { t } = useTranslation('docs');
  const c = CALLOUT[kind];
  return (
    <aside className={cn('flex gap-3 rounded-md border px-4 py-3 text-sm', c.cls)}>
      <span aria-hidden className="mt-0.5 shrink-0 [&_svg]:size-4">{c.icon}</span>
      <div className="min-w-0 [&_p]:text-inherit [&_strong]:text-inherit">
        <p className="mb-1 font-semibold">{t(`callout.${kind}`)}</p>
        <Blocks blocks={blocks} />
      </div>
    </aside>
  );
}

function SubListView({ list }: { list: SubList }) {
  const Tag = list.ordered ? 'ol' : 'ul';
  return (
    <Tag className={cn('mt-1.5 flex flex-col gap-1 pl-5', list.ordered ? 'list-decimal' : 'list-[circle]')}>
      {list.items.map((c, i) => <li key={i}><Inlines nodes={c} /></li>)}
    </Tag>
  );
}

function ListView({ ordered, items }: { ordered: boolean; items: ListItem[] }) {
  const Tag = ordered ? 'ol' : 'ul';
  return (
    <Tag className={cn('flex flex-col gap-1.5 pl-5 text-base leading-relaxed text-fg/90 marker:text-muted', ordered ? 'list-decimal' : 'list-disc')}>
      {items.map((it, i) => <li key={i} className="pl-1"><Inlines nodes={it.c} />{it.sub && <SubListView list={it.sub} />}</li>)}
    </Tag>
  );
}

const HEADING_CLS = {
  1: 'font-display text-2xl text-fg',
  2: 'mt-4 border-b border-line pb-2 font-display text-lg text-fg',
  3: 'mt-2 text-md font-semibold text-fg',
} as const;

function BlockView({ block: b }: { block: Block }) {
  switch (b.t) {
    case 'heading': {
      // Sahifa sarlavhasi (h1) — AppShell'da; hujjat ichidagi darajalar bittaga pastga suriladi.
      const Tag = ({ 1: 'h2', 2: 'h3', 3: 'h4' } as const)[b.level];
      return <Tag id={b.anchor} className={cn('scroll-mt-20', HEADING_CLS[b.level])}><Inlines nodes={b.c} /></Tag>;
    }
    case 'para':
      return <p className="text-base leading-relaxed text-fg/90"><Inlines nodes={b.c} /></p>;
    case 'list':
      return <ListView ordered={b.ordered} items={b.items} />;
    case 'table':
      return (
        <div className="overflow-x-auto rounded-md border border-line">
          <table className="w-full border-collapse text-sm">
            <thead className="bg-surface-2 text-left">
              <tr>{b.head.map((c, i) => <th key={i} scope="col" className="border-b border-line px-3 py-2 font-semibold text-fg"><Inlines nodes={c} /></th>)}</tr>
            </thead>
            <tbody>
              {b.rows.map((row, r) => (
                <tr key={r} className="border-b border-line last:border-0 align-top">
                  {row.map((c, i) => <td key={i} className="px-3 py-2 text-fg/90"><Inlines nodes={c} /></td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    case 'code':
      return (
        <pre className="num overflow-x-auto rounded-md border border-line bg-surface-2 px-4 py-3 text-sm leading-relaxed text-fg">
          <code>{b.v}</code>
        </pre>
      );
    case 'callout':
      return <Callout kind={b.kind} blocks={b.blocks} />;
    case 'quote':
      return <blockquote className="border-l-2 border-line-strong pl-4 text-muted"><Blocks blocks={b.blocks} /></blockquote>;
  }
}

export function Blocks({ blocks }: { blocks: Block[] }) {
  return <div className="flex flex-col gap-3">{blocks.map((b, i) => <BlockView key={i} block={b} />)}</div>;
}
