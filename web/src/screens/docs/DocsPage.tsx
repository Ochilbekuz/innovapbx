// «Qo'llanma» — `docs/qollanma/*.md` bo'limlari: mundarija + qidiruv (chapda), maqola, «Shu sahifada» (keng ekranda).
// Hamma rolga ochiq (menyuda SCREENS'dan tashqarida). Lazy chunk: matnlar asosiy bundle'ga kirmaydi (router.tsx).
import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useParams } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Search, X } from 'lucide-react';
import { cn } from '@/lib/cn';
import { AppShellPage } from '@/shell/AppShellPage';
import { Input } from '@/ui/Field';
import { catalogFor } from '@/docs/content';
import { neighbours, searchDocs, type Doc, type DocGroup } from '@/docs/catalog';
import { parseMarkdown, plainText, type Block } from '@/docs/markdown';
import { Blocks } from '@/docs/Markdown';

/** Interfeys tilidagi qo'llanma (tarjimasi yo'q bo'lim — uzbekcha). Til almashsa darhol qayta chiziladi. */
function useCatalog() {
  const { i18n } = useTranslation();
  return catalogFor(i18n.resolvedLanguage ?? i18n.language);
}

function useGroupLabel() {
  const { t } = useTranslation(['docs', 'shell']);
  return (g: DocGroup) => (g === 'start' || g === 'appendix' ? t(`docs:groups.${g}`) : t(`shell:groups.${g}`));
}

function Toc({ activeId }: { activeId?: string }) {
  const { t } = useTranslation('docs');
  const groupLabel = useGroupLabel();
  const catalog = useCatalog();
  return (
    <nav aria-label={t('tocLabel')} className="flex flex-col gap-4">
      {catalog.groups.map((g) => (
        <div key={g.id}>
          <p className="px-2 pb-1 text-2xs uppercase text-muted">{groupLabel(g.id)}</p>
          <ul>
            {g.docs.map((d) => (
              <li key={d.id}>
                <Link
                  to={`/docs/${d.id}`}
                  aria-current={d.id === activeId ? 'page' : undefined}
                  className={cn(
                    'block truncate rounded-sm px-2 py-1 text-sm transition-colors duration-fast',
                    d.id === activeId ? 'bg-accent-soft font-medium text-on-accent-soft' : 'text-fg/80 hover:bg-surface-2 hover:text-fg',
                  )}
                >
                  {d.title}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function SearchResults({ query }: { query: string }) {
  const { t } = useTranslation('docs');
  const catalog = useCatalog();
  const hits = useMemo(() => searchDocs(catalog, query), [catalog, query]);
  if (hits.length === 0) return <p className="px-2 text-sm text-muted">{t('noResults')}</p>;
  return (
    <div>
      <p role="status" className="px-2 pb-2 text-xs text-muted">{t('results', { count: hits.length })}</p>
      <ul className="flex flex-col gap-1">
        {hits.map(({ doc, snippet }) => (
          <li key={doc.id}>
            <Link to={`/docs/${doc.id}`} className="block rounded-sm px-2 py-1.5 hover:bg-surface-2">
              <span className="block text-sm font-medium text-fg">{doc.title}</span>
              <span className="line-clamp-2 text-xs text-muted">{snippet}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Sidebar({ activeId, hiddenOnMobile }: { activeId?: string; hiddenOnMobile: boolean }) {
  const { t } = useTranslation('docs');
  const [query, setQuery] = useState('');
  return (
    <aside className={cn('flex flex-col gap-4 lg:sticky lg:top-[calc(var(--layout-header)+1.25rem)] lg:max-h-[calc(100dvh-var(--layout-header)-2.5rem)] lg:self-start lg:overflow-y-auto', hiddenOnMobile && 'max-lg:hidden')}>
      <label>
        <span className="sr-only">{t('searchLabel')}</span>
        <Input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('searchPlaceholder')}
          leading={<Search />}
          trailing={query ? <button type="button" aria-label={t('clearSearch')} onClick={() => setQuery('')} className="flex hover:text-fg"><X /></button> : undefined}
        />
      </label>
      {query.trim() ? <SearchResults query={query} /> : <Toc activeId={activeId} />}
    </aside>
  );
}

function OnThisPage({ blocks }: { blocks: Block[] }) {
  const { t } = useTranslation('docs');
  const h2 = blocks.filter((b): b is Extract<Block, { t: 'heading' }> => b.t === 'heading' && b.level === 2);
  if (h2.length < 2) return null;
  return (
    <nav aria-label={t('onThisPage')} className="hidden xl:sticky xl:top-[calc(var(--layout-header)+1.25rem)] xl:block xl:self-start">
      <p className="pb-2 text-2xs uppercase text-muted">{t('onThisPage')}</p>
      <ul className="flex flex-col gap-1 border-l border-line">
        {h2.map((h) => (
          <li key={h.anchor}>
            <a href={`#${h.anchor}`} className="-ml-px block border-l border-transparent py-0.5 pl-3 text-sm text-muted hover:border-line-strong hover:text-fg">
              {plainText(h.c)}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function PrevNext({ id }: { id: string }) {
  const { t } = useTranslation('docs');
  const { prev, next } = neighbours(useCatalog(), id);
  const card = 'flex flex-1 flex-col gap-0.5 rounded-md border border-line px-4 py-3 hover:border-line-strong hover:bg-surface-2';
  return (
    <div className="mt-10 flex flex-col gap-3 border-t border-line pt-6 sm:flex-row">
      {prev ? (
        <Link to={`/docs/${prev.id}`} className={card}>
          <span className="flex items-center gap-1 text-xs text-muted"><ArrowLeft aria-hidden className="size-3" />{t('prev')}</span>
          <span className="text-sm font-medium text-fg">{prev.title}</span>
        </Link>
      ) : <span className="flex-1" />}
      {next && (
        <Link to={`/docs/${next.id}`} className={cn(card, 'sm:items-end sm:text-right')}>
          <span className="flex items-center gap-1 text-xs text-muted">{t('next')}<ArrowRight aria-hidden className="size-3" /></span>
          <span className="text-sm font-medium text-fg">{next.title}</span>
        </Link>
      )}
    </div>
  );
}

function Article({ doc, blocks }: { doc: Doc; blocks: Block[] }) {
  const { t } = useTranslation('docs');
  return (
    <article className="min-w-0 max-w-[46rem]">
      <div className="mb-4 flex flex-wrap items-center gap-3 lg:hidden">
        <Link to="/docs" className="inline-flex items-center gap-1 text-sm text-muted hover:text-fg"><ArrowLeft aria-hidden className="size-4" />{t('backToToc')}</Link>
      </div>
      {doc.path && (
        <Link to={doc.path} className="mb-4 inline-flex items-center gap-1 rounded-md border border-line px-2.5 py-1 text-sm text-fg hover:bg-surface-2">
          {t('openScreen')}<ArrowRight aria-hidden className="size-3.5" />
        </Link>
      )}
      <Blocks blocks={blocks} />
      <PrevNext id={doc.id} />
    </article>
  );
}

function Index() {
  const { t } = useTranslation('docs');
  const groupLabel = useGroupLabel();
  const catalog = useCatalog();
  return (
    <div className="min-w-0">
      <p className="max-w-[46rem] text-base leading-relaxed text-fg/90">{t('indexLead')}</p>
      <div className="mt-6 flex flex-col gap-7">
        {catalog.groups.map((g) => (
          <section key={g.id} aria-labelledby={`docs-g-${g.id}`}>
            <h2 id={`docs-g-${g.id}`} className="mb-2 font-display text-lg text-fg">{groupLabel(g.id)}</h2>
            <ul className="grid gap-2 sm:grid-cols-2 2xl:grid-cols-3">
              {g.docs.map((d) => (
                <li key={d.id}>
                  <Link to={`/docs/${d.id}`} className="flex h-full flex-col gap-1 rounded-md border border-line bg-surface px-4 py-3 hover:border-line-strong hover:bg-surface-2">
                    <span className="text-sm font-semibold text-fg">{d.title}</span>
                    <span className="text-sm text-muted">{d.summary}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}

/** Bo'lim almashganda tepaga, `#langar` bo'lsa — o'sha sarlavhaga. */
function useScrollOnNavigate(key: string | undefined) {
  const { hash } = useLocation();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const target = hash ? document.getElementById(decodeURIComponent(hash.slice(1))) : null;
    if (target) target.scrollIntoView?.({ block: 'start' });
    else {
      ref.current?.closest('main')?.scrollTo?.(0, 0);
      window.scrollTo?.(0, 0);
    }
  }, [key, hash]);
  return ref;
}

/** Ochilgan bo'lim va uning bloklari. Bo'lim sarlavhasi (`# ...`) sahifa sarlavhasiga ko'chadi — maqola ichida takrorlanmaydi. */
function useDoc(id: string | undefined): { doc?: Doc; body: Block[] } {
  const catalog = useCatalog();
  const doc = id ? catalog.byId.get(id) : undefined;
  const blocks = useMemo(() => (doc ? parseMarkdown(doc.body) : []), [doc]);
  const first = blocks[0];
  return { doc, body: first?.t === 'heading' && first.level === 1 ? blocks.slice(1) : blocks };
}

function Banners({ notFound }: { notFound: boolean }) {
  const { t } = useTranslation('docs');
  return (
    <>
      {notFound && <p role="alert" className="mb-4 rounded-md border border-warning/30 bg-warning-soft px-3 py-2 text-sm text-on-warning-soft">{t('notFound')}</p>}
    </>
  );
}

export function DocsPage() {
  const { t } = useTranslation('docs');
  const { id } = useParams();
  const { doc, body } = useDoc(id);
  const ref = useScrollOnNavigate(id);

  return (
    <AppShellPage title={doc?.title ?? t('title')} crumbs={doc ? [t('title')] : undefined}>
      <div ref={ref} className="grid gap-8 lg:grid-cols-[16rem_minmax(0,1fr)] xl:grid-cols-[16rem_minmax(0,1fr)_13rem]">
        <Sidebar activeId={doc?.id} hiddenOnMobile={Boolean(doc)} />
        <div className="min-w-0">
          <Banners notFound={Boolean(id) && !doc} />
          {doc ? <Article doc={doc} blocks={body} /> : <Index />}
        </div>
        {doc && <OnThisPage blocks={body} />}
      </div>
    </AppShellPage>
  );
}
