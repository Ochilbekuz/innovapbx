import { useEffect, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import * as Popover from '@radix-ui/react-popover';
import { CircleCheck, CircleHelp, LoaderCircle, LogOut, Menu, Moon, RotateCcw, Search, Sun } from 'lucide-react';
import { cn } from '@/lib/cn';
import { LANGS, persistLanguage, type Lang } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';
import { apiClient, useSession } from '@/api';
import { useUpdateAvailableDot } from '@/api/queries';
import { hasPermission } from '@/auth/permissions';
import { Kbd } from '@/ui/Button';
import { Segmented } from '@/ui/Field';
import { HealthStrip, type HealthItem } from '@/ui/Health';
import { SoftphoneChip, type CallState } from '@/pbx/Softphone';
import { SoftphoneWidget } from '@/softphone/SoftphoneWidget';
import { useSoftphoneStore } from '@/softphone/store';
import { helpPathFor } from './helpLink';
import { SCREENS } from './screens';
import { Sidebar } from './Sidebar';

export { BrandMark } from './BrandMark';

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

export type SystemInfo = { name: string; detail: string };

/** `zone` — `at` qaysi vaqt zonasida ekani: `label` «UTC+5», `name` IANA nomi «Asia/Tashkent» (tooltip'da). */
export type Revision = { number: number; state: 'applied' | 'applying' | 'rolled_back'; at: string; zone?: { label: string; name: string } };

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
        {rev.zone && <> <span className="num" title={rev.zone.name}>{rev.zone.label}</span></>}
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

const isUnder = (pathname: string, path: string) => pathname === path || pathname.startsWith(`${path}/`);

function SystemFooter({ system, health }: { system?: SystemInfo; health: HealthItem[] }) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-3">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-sidebar-text">{system?.name ?? '—'}</p>
        <p className="num truncate text-xs text-sidebar-muted" title={system?.detail}>{system?.detail ?? t('systemLoadingStatus')}</p>
      </div>
      <HealthStrip items={health} />
    </div>
  );
}

const HEADER_ICON_BTN = 'grid size-ctl-md place-items-center rounded-md border border-line bg-surface text-muted hover:bg-surface-2 hover:text-fg';

function ThemeToggle() {
  const { t } = useTranslation();
  const { theme, toggle } = useTheme();
  const dark = theme === 'dark';
  const label = dark ? t('theme.light') : t('theme.dark');
  return (
    <button type="button" onClick={toggle} aria-label={label} title={label} className={HEADER_ICON_BTN}>
      {dark ? <Sun aria-hidden className="size-4" /> : <Moon aria-hidden className="size-4" />}
    </button>
  );
}

function LangSwitch() {
  const { t, i18n } = useTranslation();
  return (
    <Segmented<Lang>
      label={t('lang')}
      value={(LANGS.find((l) => l === i18n.language) ?? 'uz')}
      onChange={(l) => persistLanguage(l)}
      options={LANGS.map((l) => ({ value: l, label: l.toUpperCase() }))}
    />
  );
}

/** /design namunasida — demo chip; haqiqiy sahifada — o'z ichki raqami bo'lsa brauzer telefoni. */
function PhoneSlot({ embedded, call }: { embedded?: boolean; call?: CallState }) {
  const ownExt = useSession((s) => s.user?.extension);
  if (embedded) return call ? <SoftphoneChip state={call} number="101" /> : null;
  return ownExt ? <SoftphoneWidget number={ownExt.number} /> : null;
}

function SearchBox() {
  const { t } = useTranslation();
  return (
    <label className="relative hidden w-72 md:block">
      <span className="sr-only">{t('search')}</span>
      <Search aria-hidden className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
      <input placeholder={t('search')} className="h-ctl-md w-full rounded-md border border-line bg-surface-2 pl-8 pr-14 text-sm text-fg placeholder:text-muted focus-visible:border-focus-ring focus-visible:bg-surface focus-visible:outline-none" />
      <span className="absolute right-2 top-1/2 flex -translate-y-1/2 gap-0.5"><Kbd>{t('shortcutCtrl')}</Kbd><Kbd>K</Kbd></span>
    </label>
  );
}

function ShellHeader({ embedded, navOpen, onOpenNav, revision, activeId, call }: {
  embedded?: boolean;
  navOpen: boolean;
  onOpenNav: () => void;
  /** Berilsa (faqat `*` yoki /design) — reviziya belgisi ko'rinadi. */
  revision: Revision | null;
  activeId: string | undefined;
  call?: CallState;
}) {
  const { t } = useTranslation();
  const location = useLocation();
  return (
    <header className={cn('z-header flex h-header shrink-0 items-center gap-3 border-b border-line bg-surface/85 px-4 backdrop-blur-md', !embedded && 'sticky top-0')}>
      <button type="button" className="grid size-ctl-md place-items-center rounded-md text-muted hover:bg-surface-2 lg:hidden" aria-label={t('openNavAriaLabel')} aria-expanded={navOpen} onClick={onOpenNav}>
        <Menu aria-hidden className="size-5" />
      </button>
      <SearchBox />
      <div className="ml-auto flex items-center gap-2">
        {revision && <RevisionBadge rev={revision} />}
        <Link to={helpPathFor(location.pathname, activeId)} aria-label={t('helpLink')} title={t('helpLink')} className={HEADER_ICON_BTN}>
          <CircleHelp aria-hidden className="size-4" />
        </Link>
        <LangSwitch />
        <ThemeToggle />
        <PhoneSlot embedded={embedded} call={call} />
        <UserMenu />
      </div>
    </header>
  );
}

function PageBody({ title, crumbs, children }: { title: string; crumbs: string[]; children: ReactNode }) {
  const { t } = useTranslation();
  return (
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
  );
}

/** Kim nimani ko'radi: tizim holati/reviziya — faqat `*` (operatorga 403); /design namunasida doim. */
function useShellAccess(embedded?: boolean) {
  const permissions = useSession((s) => s.user?.permissions);
  const isAdmin = hasPermission(permissions, '*');
  // M12 B4 — `/system/update`ni faqat haqiqiy adminlarga (`embedded` demo'da emas) soʻraydi, qarang ../../replica/m12-contract.md §B4.
  const updateAvailable = useUpdateAvailableDot(!embedded && isAdmin);
  return { permissions, showSystem: Boolean(embedded) || isAdmin, updateDotId: updateAvailable ? 'update' : null };
}

/** Idempotent: sahifalar o'rtasida AppShell qayta mount bo'lsa ham bir marta ulanadi; logout `teardown()` chaqiradi. */
function useSoftphoneBoot(embedded?: boolean) {
  const initSoftphone = useSoftphoneStore((s) => s.init);
  useEffect(() => { if (!embedded) initSoftphone(); }, [embedded, initSoftphone]);
}

function MobileScrim({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useTranslation();
  if (!open) return null;
  return <button type="button" aria-label={t('closeNavAriaLabel')} className="fixed inset-0 z-10 bg-scrim/50 lg:hidden" onClick={onClose} />;
}

const screenAt = (pathname: string) => SCREENS.find((s) => isUnder(pathname, s.path))?.id;

export function AppShell({ active, title, crumbs = [], health, revision, system, call, children, embedded }: ShellProps) {
  const [navOpen, setNavOpen] = useState(false);
  const { pathname } = useLocation();
  const { permissions, showSystem, updateDotId } = useShellAccess(embedded);
  const activeId = active ?? screenAt(pathname);
  const closeNav = () => setNavOpen(false);
  useSoftphoneBoot(embedded);

  return (
    <div className={cn('flex bg-bg text-fg', embedded ? 'h-full' : 'min-h-dvh')}>
      <Sidebar
        activeId={activeId}
        docsActive={isUnder(pathname, '/docs')}
        permissions={permissions}
        updateDotId={updateDotId}
        embedded={embedded}
        mobileOpen={navOpen}
        onNavigate={closeNav}
        footer={showSystem && <SystemFooter system={system} health={health} />}
      />
      <MobileScrim open={navOpen} onClose={closeNav} />

      <div className="flex min-w-0 flex-1 flex-col">
        <ShellHeader embedded={embedded} navOpen={navOpen} onOpenNav={() => setNavOpen(true)} revision={showSystem ? revision : null} activeId={activeId} call={call} />
        <PageBody title={title} crumbs={crumbs}>{children}</PageBody>
      </div>
    </div>
  );
}
