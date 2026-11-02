import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { CircleCheck, Link2Off, Repeat2, TriangleAlert } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/cn';
import { buildFlow, issueList, type FlowIssue, type FlowNode } from '@/domain/flow';
import { formatNumber, type DestKind, type Catalog, type Destination } from '@/domain/destination';
import { KIND_ICON, useKindLabel } from './kinds';

/** Oqim tugunini bosilganda qaysi ekranga o'tilsin — faqat o'z sahifasi bor turlar uchun. */
const NODE_PATH: Partial<Record<DestKind, string>> = {
  extension: '/extensions', ring_group: '/ringgroups', queue: '/queues', ivr: '/ivr', time_condition: '/timegroups',
};

/** DID dan boshlab qo'ng'iroq yo'li — mijoz tomonida (katalogdan) hisoblanadi. /design demo sahifasida ishlatiladi. */
export function CallFlow({ did, root, catalog }: { did: string; root: Destination | null; catalog: Catalog }) {
  return <CallFlowTree did={did} tree={buildFlow(root, catalog)} />;
}

/**
 * Tayyor daraxtni chizadi — server tomonidan hisoblangan oqim (`GET /flow/{id}`, `domain/flow.ts: fromApiFlow`) uchun ham ishlatiladi.
 * `layout="stacked"` — tor konteynerda (masalan Drawer, 480px) ikki ustunli joylashuvni majburan bitta ustunga yig'adi;
 * `lg:` sinflari sahifa (viewport) kengligiga qarab ishlaydi, konteyner kengligiga emas — Drawer doim ishonchli yig'ilishi uchun kerak.
 */
export function CallFlowTree({ did, tree, layout = 'auto' }: { did: string; tree: FlowNode; layout?: 'auto' | 'stacked' }) {
  const { t } = useTranslation('common');
  const issues = issueList(tree);
  const clean = issues.length === 0;
  const count = { broken: issues.filter((i) => i.state === 'broken').length, loops: issues.filter((i) => i.state === 'loop').length };
  return (
    <figure className="overflow-hidden rounded-lg border border-line bg-surface shadow-card">
      <figcaption className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2.5">
        <span className="font-display text-base font-semibold">{t('callFlow.title')}</span>
        <span role="status" className={cn('inline-flex items-center gap-1.5 text-sm font-medium [&_svg]:size-4', clean ? 'text-success' : 'text-danger')}>
          {clean ? <CircleCheck aria-hidden /> : <TriangleAlert aria-hidden />}
          {clean
            ? t('callFlow.clean')
            : [count.broken && t('callFlow.brokenCount', { n: count.broken }), count.loops && t('callFlow.loopCount', { n: count.loops })].filter(Boolean).join(', ')}
        </span>
      </figcaption>
      <div className={cn('grid', layout === 'auto' && 'lg:grid-cols-[minmax(0,1fr)_300px]')}>
        <div className="hairline-grid overflow-x-auto p-5">
          <ul aria-label={t('callFlow.pathAriaLabel', { did })} className="flex flex-col">
            <li>
              <NodeCard icon={KIND_ICON.did} kind={t('callFlow.incomingDid')} title={<span className="num">{did}</span>} tone="root" />
              <Branches nodes={[tree]} />
            </li>
          </ul>
        </div>
        <IssuePanel issues={issues} did={did} stacked={layout === 'stacked'} />
      </div>
    </figure>
  );
}

function IssuePanel({ issues, did, stacked }: { issues: FlowIssue[]; did: string; stacked: boolean }) {
  const { t } = useTranslation('common');
  return (
    <aside aria-label={t('callFlow.issuesAriaLabel')} className={cn('border-t border-line bg-surface-2/50 p-5', !stacked && 'lg:border-l lg:border-t-0')}>
      <p className="eyebrow">{t('callFlow.check')}</p>
      {issues.length === 0 ? (
        <p className="mt-2 text-sm text-muted">{t('callFlow.noIssues')}</p>
      ) : (
        <ol className="mt-3 space-y-3">
          {issues.map((i) => (
            <li key={i.key} className="flex gap-2.5 text-sm">
              <span aria-hidden className={cn('mt-0.5 [&_svg]:size-4', i.state === 'broken' ? 'text-danger' : 'text-warning')}>
                {i.state === 'broken' ? <Link2Off /> : <Repeat2 />}
              </span>
              <span>
                <span className="block font-medium text-fg">{i.state === 'broken' ? t('callFlow.brokenLabel') : t('callFlow.loopLabel')}</span>
                <span className="block text-xs text-muted"><span className="num">{did}</span>{i.path.map((p) => ` → ${p}`).join('')}</span>
                <span className="mt-0.5 block text-muted">
                  {i.state === 'broken' ? t('callFlow.brokenDetail') : t('callFlow.loopDetail')}
                </span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </aside>
  );
}

/** Vertikal daraxt: chuqurlik koʻpaysa ham sigʻadi. Ulagichlar — 1px chiziqlar (CSS). */
function Branches({ nodes }: { nodes: FlowNode[] }) {
  if (nodes.length === 0) return null;
  return (
    <ul className="ml-[22px] flex flex-col">
      {nodes.map((n, i) => (
        <li
          key={n.key}
          className={cn(
            'relative pl-6 pt-2',
            'before:absolute before:left-0 before:top-0 before:w-px before:bg-line-strong',
            i === nodes.length - 1 ? 'before:h-[30px]' : 'before:bottom-0',
            'after:absolute after:left-0 after:top-[30px] after:h-px after:w-6 after:bg-line-strong',
          )}
        >
          <FlowItem node={n} />
        </li>
      ))}
    </ul>
  );
}

function FlowItem({ node }: { node: FlowNode }) {
  const { t } = useTranslation('common');
  const kindLabel = useKindLabel();
  const r = node.resolved;
  const card =
    node.state === 'broken' && r.state === 'broken' ? (
      <NodeCard icon={<Link2Off />} kind={kindLabel[r.kind]} title={t('callFlow.deletedObject')} meta={`#${r.targetId}`} tone="broken" edge={node.edgeLabel} />
    ) : node.state === 'loop' && r.state === 'ok' ? (
      <NodeCard icon={<Repeat2 />} kind={t('callFlow.loopLabel')} title={t('callFlow.loopBackTo', { label: r.label })} meta={r.number} tone="loop" edge={node.edgeLabel} />
    ) : r.state === 'ok' ? (
      <NodeCard
        icon={KIND_ICON[r.kind]} kind={kindLabel[r.kind]}
        title={r.kind === 'external' ? <span className="num">{formatNumber(r.number ?? '')}</span> : r.label}
        meta={r.kind === 'external' ? undefined : r.number} tone={r.kind === 'hangup' || r.kind === 'busy' ? 'end' : 'ok'}
        edge={node.edgeLabel} href={r.target ? NODE_PATH[r.kind] : undefined}
      />
    ) : (
      <NodeCard icon={<TriangleAlert />} kind={t('callFlow.unselectedKind')} title={t('callFlow.unselectedTitle')} tone="broken" edge={node.edgeLabel} />
    );
  return (
    <>
      {card}
      <Branches nodes={node.children} />
    </>
  );
}

type Tone = 'root' | 'ok' | 'end' | 'loop' | 'broken';
const TONE: Record<Tone, string> = {
  root: 'border-fg bg-fg text-bg',
  ok: 'border-line-strong bg-surface',
  end: 'border-line bg-surface-2 text-muted',
  loop: 'border-dashed border-warning bg-warning-soft',
  broken: 'border-danger bg-danger-soft',
};

function NodeCard({ icon, kind, title, meta, tone, edge, href }: { icon: ReactNode; kind: string; title: ReactNode; meta?: string; tone: Tone; edge?: string; href?: string }) {
  const boxClassName = cn(
    'flex h-11 min-w-[200px] max-w-[320px] items-center gap-2.5 rounded-md border px-2.5 shadow-card',
    href && 'transition-[border-color,box-shadow] duration-200 ease-[cubic-bezier(.22,1,.36,1)] hover:border-brand focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand',
    TONE[tone],
  );
  const content = (
    <>
      <span
        aria-hidden
        className={cn(
          'grid size-6 shrink-0 place-items-center rounded-sm [&_svg]:size-3.5',
          tone === 'root' ? 'bg-brand text-on-accent' : tone === 'broken' ? 'text-danger' : tone === 'loop' ? 'text-warning' : 'bg-surface-2 text-fg',
        )}
      >
        {icon}
      </span>
      <span className="min-w-0 leading-tight">
        <span className={cn('block text-2xs uppercase', tone === 'root' ? 'text-bg/70' : tone === 'broken' ? 'text-on-danger-soft' : tone === 'loop' ? 'text-on-warning-soft' : 'text-muted')}>{kind}</span>
        <span className={cn('block truncate text-sm font-medium', tone === 'broken' ? 'text-on-danger-soft' : tone === 'loop' ? 'text-on-warning-soft' : '')}>
          {title}
          {meta && <span className="num ml-1.5 text-xs font-normal opacity-80">{meta}</span>}
        </span>
      </span>
    </>
  );
  return (
    <div className="flex items-center">
      {edge !== undefined && (
        <span className={cn(/^[\d*#]+$/.test(edge) && 'num', 'relative z-10 -ml-2 mr-2 inline-flex h-5 min-w-5 items-center justify-center whitespace-nowrap rounded-xs border border-line-strong bg-surface px-1.5 text-xs text-fg')}>
          {edge}
        </span>
      )}
      {href ? (
        <Link to={href} className={boxClassName}>{content}</Link>
      ) : (
        <div className={boxClassName}>{content}</div>
      )}
    </div>
  );
}
