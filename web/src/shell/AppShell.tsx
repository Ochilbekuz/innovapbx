import { useEffect, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import * as Popover from '@radix-ui/react-popover';
import { BookOpenText, ChevronDown, CircleCheck, CircleHelp, LoaderCircle, LogOut, Menu, Moon, RotateCcw, Search, Sun } from 'lucide-react';
import { cn } from '@/lib/cn';
import { LANGS, persistLanguage, type Lang } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';
import { apiClient, useSession } from '@/api';
import { useUpdateAvailableDot } from '@/api/queries';
import { hasPermission } from '@/auth/permissions';
import { Kbd } from '@/ui/Button';
import { Segmented } from '@/ui/Field';
import { HealthStrip, type HealthItem } from '@/ui/Health';
import { LiveDot } from '@/ui/Status';
import { SoftphoneChip, type CallState } from '@/pbx/Softphone';
import { SoftphoneWidget } from '@/softphone/SoftphoneWidget';
import { useSoftphoneStore } from '@/softphone/store';
import { loadCollapsedGroups, saveCollapsedGroups } from './navCollapse';
import { helpPathFor } from './helpLink';
import { byGroup, GROUP_ORDER, SCREENS, type ScreenDef, type ScreenGroupId } from './screens';

/** «Qo'llanma» — hamma rolga ko'rinadi (SCREENS'dan tashqarida: ruxsat filtri va hudud xaritasiga kirmaydi). */
const DOCS_NAV = { id: 'docs', path: '/docs', icon: <BookOpenText /> } satisfies NavEntry;

function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const chars = parts.slice(0, 2).map((w) => w[0]?.toUpperCase() ?? '');
  return chars.join('') || 'A';
}

/** Header'dagi foydalanuvchi belgisi — bosilganda ism/login va chiqish tugmasini ko'rsatadi. */
function UserMenu() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const user = useSession((s) => s.user);
  const refresh = useSession((s) => s.refresh);
  const clear = useSession((s) => s.clear);
  const [open, setOpen] = useState(false);
  const name = user?.full_name ?? t('defaultUserName');

  const handleLogout = async () => {
    setOpen(false);
    await useSoftphoneStore.getState().teardown();
    try {
      if (refresh) await apiClient.logout(refresh);
    } catch {
      // Chiqish baribir mahalliy — server bilan bog'lanib bo'lmasa ham.
    }
    clear();
    navigate('/login', { replace: true });
  };

  const triggerLabel = `${t('userMenu.title')}: ${name}`;
  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          type="button"
          aria-label={triggerLabel}
          className="grid size-ctl-md place-items-center rounded-md bg-fg font-display text-sm font-semibold text-bg transition-opacity duration-fast hover:opacity-90"
        >
          {initialsOf(name)}
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="end"
          sideOffset={8}
          className="z-popover w-56 overflow-hidden rounded-lg border border-line bg-raised shadow-pop data-[state=open]:animate-pop-in"
        >
          <div className="border-b border-line px-3 py-2.5">
            <p className="truncate text-sm font-medium text-fg">{name}</p>
            <p className="num truncate text-xs text-muted">{user?.login}</p>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-sm text-fg transition-colors duration-fast hover:bg-surface-2"
          >
            <LogOut aria-hidden className="size-4 text-muted" />
            {t('userMenu.logout')}
          </button>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

export function BrandMark({ compact, onDark = true }: { compact?: boolean; onDark?: boolean }) {
  const { t } = useTranslation();
  const brandWord = t('brandWord');
  const brandSuffix = t('brandSuffix');
  return (
    <span className="inline-flex items-center gap-2.5">
      <img src="/brand/innova-belgi-64.png" alt="" width={28} height={28} className="size-7" />
      {!compact && (
        <span className={cn('font-display text-[19px] font-semibold leading-none tracking-[-0.01em]', onDark ? 'text-sidebar-text' : 'text-fg')}>
          {brandWord} <span className={onDark ? 'text-brand-fire' : 'text-brand'}>{brandSuffix}</span>
        </span>
      )}
    </span>
  );
}

export type SystemInfo = { name: string; detail: string };

export type Revision = { number: number; state: 'applied' | 'applying' | 'rolled_back'; at: string };

/** Dialplan reviziyasi belgisi. Bizda «Apply Config» tugmasi yo'q — har saqlash darhol qo'llanadi; bu faqat holatni ko'rsatadi. */
export function RevisionBadge({ rev }: { rev: Revision }) {
  const { t } = useTranslation();
  const st = {
    applied: { icon: <CircleCheck />, cls: 'text-success', text: t('revision.applied') },
    applying: { icon: <LoaderCircle className="animate-spin" />, cls: 'text-muted', text: t('revision.applying') },
    rolled_back: { icon: <RotateCcw />, cls: 'text-danger', text: t('revision.rolledBack') },
  }[rev.state];
  return (
    <Link
      to="/settings/revisions"
      className={cn(
        'inline-flex h-ctl-md items-center gap-2 rounded-md border px-2.5 text-sm transition-colors duration-fast hover:bg-surface-2',
        rev.state === 'rolled_back' ? 'border-danger/40 bg-danger-soft' : 'border-line bg-surface',
      )}
      title={t('revisionHistoryTitle')}
    >
      <span aria-hidden className={cn('[&_svg]:size-4', st.cls)}>{st.icon}</span>
      <span className="text-muted">{t('dialplanLabel')}</span>
      <span className="num font-medium text-fg">r{rev.number}</span>
      <span className={cn('hidden text-sm xl:inline', rev.state === 'rolled_back' ? 'text-on-danger-soft' : 'text-muted')}>
        {st.text} <span className="num">{rev.at}</span>
      </span>
    </Link>
  );
}

type ShellProps = {
  /** Berilmasa — joriy marshrutdan avtomatik aniqlanadi (`/design` namunasida qo'lda beriladi). */
  active?: string;
  title: string;
  crumbs?: string[];
  health: HealthItem[];
  revision: Revision;
  /** Yon menyu pastidagi server/Asterisk ma'lumoti (`/system/health` dan). */
  system?: SystemInfo;
  /** Faqat /design namunasida (`embedded`) — demo holatni ko'rsatish uchun. */
  call?: CallState;
  children: ReactNode;
  /** /design sahifasida ramka ichida ko'rsatish uchun. */
  embedded?: boolean;
};

/** Guruh sarlavhasi — tugma (chevron, `aria-expanded`/`aria-controls`) + silliq balandlik animatsiyali ro'yxat (M8 §6). */
/** Yig'ilgan guruhdagi havola ko'rinmaydi — Tab bilan unga fokus tushmasligi uchun `tabIndex=-1`. */
/** Statik `it.live`/`it.count`dan farqli — faqat `update` elementi uchun, `/system/update`ni soʻrab dinamik
 *  hisoblanadi (M12 B4, ../../replica/m12-contract.md §B4). Oddiy (animatsiyasiz) nuqta — `ui/Tabs.tsx`dagi
 *  `invalid` uslubi bilan bir xil (`LiveDot`dan farqli, chunki bu "yangilanish bor" belgisi, jonli holat emas). */
function UpdateAvailableDot() {
  const { t } = useTranslation();
  return (
    <>
      <span aria-hidden className="size-1.5 rounded-full bg-danger" />
      <span className="sr-only">{t('updateAvailableDot')}</span>
    </>
  );
}

type NavEntry = Pick<ScreenDef, 'id' | 'path' | 'icon' | 'live' | 'count'>;

function NavItem({ item: it, on, focusable, showUpdateDot, onNavigate }: {
  item: NavEntry;
  on: boolean;
  focusable: boolean;
  showUpdateDot: boolean;
  onNavigate: () => void;
}) {
  const { t } = useTranslation();
  return (
    <li>
      <Link
        to={it.path}
        onClick={onNavigate}
        tabIndex={focusable ? undefined : -1}
        aria-current={on ? 'page' : undefined}
        className={cn(
          'relative flex h-8 items-center gap-2.5 rounded-sm px-2.5 text-base transition-colors duration-fast [&_svg]:size-4',
          on ? 'bg-sidebar-active font-medium text-sidebar-text' : 'text-sidebar-text/85 hover:bg-sidebar-surface hover:text-sidebar-text',
        )}
      >
        {on && <span aria-hidden className="absolute inset-y-1.5 -left-2 w-[3px] rounded-r bg-brand-fire" />}
        <span aria-hidden className={on ? 'text-brand-fire' : 'text-sidebar-muted'}>{it.icon}</span>
        <span className="flex-1 truncate">{t(`nav.${it.id}`)}</span>
        {it.live && <LiveDot />}
        {showUpdateDot && <UpdateAvailableDot />}
        {it.count !== undefined && <span className="num text-xs text-sidebar-muted">{it.count}</span>}
      </Link>
    </li>
  );
}

function NavGroup({ group, items, activeId, isOpen, onToggle, onNavigate, updateDotId }: {
  group: ScreenGroupId;
  items: ReturnType<typeof byGroup>;
  activeId: string | undefined;
  isOpen: boolean;
  onToggle: () => void;
  onNavigate: () => void;
  /** `showUpdateDot` ekranning `id`si (odatda `'update'`) — qarang `AppShell`. */
  updateDotId: string | null;
}) {
  const { t } = useTranslation();
  const hasLive = items.some((it) => it.live);
  const hasUpdateDot = updateDotId !== null && items.some((it) => it.id === updateDotId);
  const panelId = `nav-group-${group}`;
  return (
    <div className="mb-3">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={isOpen}
        aria-controls={panelId}
        className="flex w-full items-center gap-1.5 px-2.5 pb-1 text-2xs uppercase text-sidebar-muted transition-colors duration-fast hover:text-sidebar-text"
      >
        <ChevronDown aria-hidden className={cn('size-3 shrink-0 transition-transform duration-fast', !isOpen && '-rotate-90')} />
        <span className="flex-1 truncate text-left">{t(`groups.${group}`)}</span>
        {!isOpen && (hasLive || hasUpdateDot) && <LiveDot />}
      </button>
      <div
        id={panelId}
        className={cn('grid transition-[grid-template-rows] duration-base motion-reduce:transition-none', isOpen ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]')}
      >
        <ul className="overflow-hidden" aria-hidden={!isOpen || undefined}>
          {items.map((it) => (
            <NavItem key={it.id} item={it} on={it.id === activeId} focusable={isOpen} showUpdateDot={it.id === updateDotId} onNavigate={onNavigate} />
          ))}
        </ul>
      </div>
    </div>
  );
}

export function AppShell({ active, title, crumbs = [], health, revision, system, call, children, embedded }: ShellProps) {
  const { t, i18n } = useTranslation();
  const { theme, toggle } = useTheme();
  const [navOpen, setNavOpen] = useState(false);
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set(loadCollapsedGroups()));
  const location = useLocation();
  const permissions = useSession((s) => s.user?.permissions);
  const ownExt = useSession((s) => s.user?.extension);
  const initSoftphone = useSoftphoneStore((s) => s.init);
  // Tizim holati/reviziya — faqat `*` (operatorga 403); /design namunasida doim ko'rinadi.
  const showSystem = embedded || hasPermission(permissions, '*');
  const activeId = active ?? SCREENS.find((s) => location.pathname === s.path || location.pathname.startsWith(`${s.path}/`))?.id;
  const activeGroup = SCREENS.find((s) => s.id === activeId)?.group;
  const docsActive = location.pathname === DOCS_NAV.path || location.pathname.startsWith(`${DOCS_NAV.path}/`);
  // M12 B4 — `/system/update`ni faqat haqiqiy adminlarga (`embedded` demo'da emas) soʻraydi, qarang ../../replica/m12-contract.md §B4.
  const updateAvailable = useUpdateAvailableDot(!embedded && hasPermission(permissions, '*'));
  const updateDotId = updateAvailable ? 'update' : null;

  const toggleGroup = (g: ScreenGroupId) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(g)) next.delete(g); else next.add(g);
      saveCollapsedGroups([...next]);
      return next;
    });
  };

  // Idempotent: sahifalar o'rtasida AppShell qayta mount bo'lsa ham bir marta ulanadi; logout `teardown()` chaqiradi.
  useEffect(() => { if (!embedded) initSoftphone(); }, [embedded, initSoftphone]);

  return (
    <div className={cn('flex bg-bg text-fg', embedded ? 'h-full' : 'min-h-dvh')}>
      <aside
        aria-label={t('mainNavAriaLabel')}
        className={cn(
          'flex w-sidebar shrink-0 flex-col bg-sidebar-bg text-sidebar-text',
          embedded ? 'relative' : 'sticky top-0 h-dvh',
          'max-lg:fixed max-lg:inset-y-0 max-lg:left-0 max-lg:z-sidebar max-lg:transition-transform max-lg:duration-base',
          !navOpen && 'max-lg:-translate-x-full',
        )}
      >
        <div className="flex h-header items-center border-b border-sidebar-border px-4">
          <BrandMark />
        </div>
        <nav className="flex-1 overflow-y-auto px-2 py-3">
          {GROUP_ORDER.map((g) => {
            const items = byGroup(g, permissions);
            if (items.length === 0) return null;
            const isOpen = g === activeGroup || !collapsed.has(g);
            return (
              <NavGroup
                key={g}
                group={g}
                items={items}
                activeId={activeId}
                isOpen={isOpen}
                onToggle={() => toggleGroup(g)}
                onNavigate={() => setNavOpen(false)}
                updateDotId={updateDotId}
              />
            );
          })}
          <ul className="mt-1 border-t border-sidebar-border pt-3">
            <NavItem item={DOCS_NAV} on={docsActive} focusable showUpdateDot={false} onNavigate={() => setNavOpen(false)} />
          </ul>
        </nav>
        {showSystem && <div className="flex items-center justify-between gap-3 border-t border-sidebar-border px-4 py-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-sidebar-text">{system?.name ?? '—'}</p>
            <p className="num truncate text-xs text-sidebar-muted" title={system?.detail}>{system?.detail ?? t('systemLoadingStatus')}</p>
          </div>
          <HealthStrip items={health} />
        </div>}
      </aside>
      {navOpen && <button type="button" aria-label={t('closeNavAriaLabel')} className="fixed inset-0 z-10 bg-scrim/50 lg:hidden" onClick={() => setNavOpen(false)} />}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className={cn('z-header flex h-header shrink-0 items-center gap-3 border-b border-line bg-surface/85 px-4 backdrop-blur-md', !embedded && 'sticky top-0')}>
          <button type="button" className="grid size-ctl-md place-items-center rounded-md text-muted hover:bg-surface-2 lg:hidden" aria-label={t('openNavAriaLabel')} aria-expanded={navOpen} onClick={() => setNavOpen(true)}>
            <Menu aria-hidden className="size-5" />
          </button>
          <label className="relative hidden w-72 md:block">
            <span className="sr-only">{t('search')}</span>
            <Search aria-hidden className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
            <input placeholder={t('search')} className="h-ctl-md w-full rounded-md border border-line bg-surface-2 pl-8 pr-14 text-sm text-fg placeholder:text-muted focus-visible:border-focus-ring focus-visible:bg-surface focus-visible:outline-none" />
            <span className="absolute right-2 top-1/2 flex -translate-y-1/2 gap-0.5"><Kbd>{t('shortcutCtrl')}</Kbd><Kbd>K</Kbd></span>
          </label>
          <div className="ml-auto flex items-center gap-2">
            {showSystem && <RevisionBadge rev={revision} />}
            <Link
              to={helpPathFor(location.pathname, activeId)}
              aria-label={t('helpLink')}
              title={t('helpLink')}
              className="grid size-ctl-md place-items-center rounded-md border border-line bg-surface text-muted hover:bg-surface-2 hover:text-fg"
            >
              <CircleHelp aria-hidden className="size-4" />
            </Link>
            <Segmented<Lang>
              label={t('lang')}
              value={(LANGS.find((l) => l === i18n.language) ?? 'uz')}
              onChange={(l) => persistLanguage(l)}
              options={LANGS.map((l) => ({ value: l, label: l.toUpperCase() }))}
            />
            <button
              type="button"
              onClick={toggle}
              aria-label={theme === 'dark' ? t('theme.light') : t('theme.dark')}
              title={theme === 'dark' ? t('theme.light') : t('theme.dark')}
              className="grid size-ctl-md place-items-center rounded-md border border-line bg-surface text-muted hover:bg-surface-2 hover:text-fg"
            >
              {theme === 'dark' ? <Sun aria-hidden className="size-4" /> : <Moon aria-hidden className="size-4" />}
            </button>
            {embedded
              ? call && <SoftphoneChip state={call} number="101" />
              : ownExt && <SoftphoneWidget number={ownExt.number} />}
            <UserMenu />
          </div>
        </header>
        <main className="min-w-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-content px-6 py-5">
            {crumbs.length > 0 && (
              <nav aria-label={t('breadcrumbAriaLabel')} className="mb-1 text-sm text-muted">
                {crumbs.join(' / ')}
              </nav>
            )}
            <h1 className="font-display text-xl text-fg">{title}</h1>
            <div className="mt-5">{children}</div>
          </div>
        </main>
      </div>
    </div>
  );
}
