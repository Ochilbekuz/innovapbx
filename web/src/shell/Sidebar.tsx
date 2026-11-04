import { useCallback, useEffect, useRef, useState, type CSSProperties, type FocusEvent, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { BookOpenText, ChevronDown, PanelLeftClose, Pin } from 'lucide-react';
import { cn } from '@/lib/cn';
import { LiveDot } from '@/ui/Status';
import { BrandMark } from './BrandMark';
import { accordionNext, isNavToggleShortcut, loadNavMode, saveNavMode, type NavMode } from './navMode';
import { byGroup, GROUP_META, GROUP_ORDER, SCREENS, type ScreenDef, type ScreenGroupId } from './screens';

/**
 * Yon menyu (desktop ikki rejim + mobil drawer). Kompozitsiya:
 *  - tashqi «joy egasi» kontentni suradi: qotirilganda 248px, rail'da 60px;
 *  - ichidagi `<aside>` absolut — rail'da sichqoncha/klaviatura fokusi kelsa 248px'gacha kengayib kontent
 *    ustiga chiqadi (layout siljimaydi). Ikonalar ikkala holatda ham bir xil x-o'qda turadi — kenglik
 *    o'zgarganda faqat matn kesiladi/so'nadi, hech narsa sakramaydi.
 * Guruh rangi `--nav-accent` orqali ichkariga uzatiladi (`text-nav`, `bg-nav/15` ...).
 */

/** «Qo'llanma» — hamma rolga ko'rinadi (SCREENS'dan tashqarida: ruxsat filtri va hudud xaritasiga kirmaydi). */
const DOCS_NAV = { id: 'docs', path: '/docs', icon: <BookOpenText /> } satisfies NavEntry;

/** Rail ustiga kelganda ochilish/yopilish kechikishi: tasodifiy o'tishda miltillamasin. */
const PEEK_OPEN_MS = 120;
const PEEK_CLOSE_MS = 280;

type NavEntry = Pick<ScreenDef, 'id' | 'path' | 'icon' | 'live' | 'count'>;

const accentStyle = (token: string) => ({ '--nav-accent': `var(--c-${token})` }) as CSSProperties;

/** Statik `it.live`/`it.count`dan farqli — faqat `update` elementi uchun, `/system/update`ni so'rab dinamik
 *  hisoblanadi (M12 B4, ../../replica/m12-contract.md §B4). Oddiy (animatsiyasiz) nuqta — `ui/Tabs.tsx`dagi
 *  `invalid` uslubi bilan bir xil. */
function UpdateAvailableDot() {
  const { t } = useTranslation();
  return (
    <>
      <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-danger rail:hidden" />
      <span className="sr-only">{t('updateAvailableDot')}</span>
    </>
  );
}

/** Rail rejimida matn kesilgan bo'lishi mumkin — nom `aria-label`/`title`ga ko'chadi (qo'shimcha belgi bilan). */
function railName(rail: boolean, label: string, extra: string): string | undefined {
  if (!rail) return undefined;
  return extra ? `${label}, ${extra}` : label;
}

/** Faol element: guruh rangidagi chap chiziq + rangli ikona. */
function ItemIcon({ icon, on }: { icon: ReactNode; on: boolean }) {
  return (
    <>
      {on && <span aria-hidden className="absolute inset-y-1.5 -left-[7px] w-[3px] rounded-full bg-nav" />}
      <span aria-hidden className={cn('shrink-0 transition-colors duration-fast', on ? 'text-nav' : 'text-sidebar-muted group-hover/item:text-sidebar-text')}>{icon}</span>
    </>
  );
}

function ItemBadges({ item: it, showUpdateDot }: { item: NavEntry; showUpdateDot: boolean }) {
  return (
    <>
      {it.live && <LiveDot className="rail:hidden" />}
      {showUpdateDot && <UpdateAvailableDot />}
      {it.count !== undefined && <span className="num text-xs text-sidebar-muted rail:hidden">{it.count}</span>}
    </>
  );
}

function NavItem({ item: it, on, focusable, rail, showUpdateDot, onNavigate }: {
  item: NavEntry;
  on: boolean;
  /** Yopiq guruhdagi havolaga Tab bilan fokus tushmasin. */
  focusable: boolean;
  /** Rail rejimida matn ko'rinmasligi mumkin — nom `aria-label` va tooltip (`title`) orqali. */
  rail: boolean;
  showUpdateDot: boolean;
  onNavigate: () => void;
}) {
  const { t } = useTranslation();
  const label = t(`nav.${it.id}`);
  const named = railName(rail, label, showUpdateDot ? t('updateAvailableDot') : '');
  return (
    <li className="first:mt-0.5 last:mb-2">
      <Link
        to={it.path}
        onClick={onNavigate}
        tabIndex={focusable ? undefined : -1}
        aria-current={on ? 'page' : undefined}
        aria-label={named}
        title={named}
        className={cn(
          'group/item relative flex h-8 items-center gap-3.5 whitespace-nowrap rounded-md px-3 text-base transition-colors duration-fast [&_svg]:size-4',
          on ? 'bg-nav/15 font-medium text-sidebar-text' : 'text-sidebar-text/85 hover:bg-sidebar-surface hover:text-sidebar-text',
        )}
      >
        <ItemIcon icon={it.icon} on={on} />
        <span className="min-w-0 flex-1 truncate transition-opacity duration-base rail:opacity-0">{label}</span>
        <ItemBadges item={it} showUpdateDot={showUpdateDot} />
      </Link>
    </li>
  );
}

function GroupChip({ group, open, marked }: { group: ScreenGroupId; open: boolean; marked: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        'relative grid size-6 shrink-0 place-items-center rounded-[7px] text-nav transition-colors duration-fast [&_svg]:size-3.5',
        open ? 'bg-nav/20' : 'bg-nav/10 group-hover/hd:bg-nav/20',
        marked && 'ring-1 ring-inset ring-nav/60',
      )}
    >
      {GROUP_META[group].icon}
      {marked && <span className="absolute -right-[3px] -top-[3px] size-2 rounded-full bg-nav ring-2 ring-sidebar-bg" />}
    </span>
  );
}

function GroupHeader({ group, count, isOpen, holdsActive, hasSignal, rail, panelId, onToggle }: {
  group: ScreenGroupId;
  count: number;
  isOpen: boolean;
  /** Faol sahifa shu guruhda — yopiq bo'lsa ham sarlavhada belgilanadi. */
  holdsActive: boolean;
  /** Ichida jonli/yangilanish belgisi bor — yopiqda sarlavhaga chiqariladi. */
  hasSignal: boolean;
  rail: boolean;
  panelId: string;
  onToggle: () => void;
}) {
  const { t } = useTranslation();
  const label = t(`groups.${group}`);
  const marked = holdsActive && !isOpen;
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={isOpen}
      aria-controls={panelId}
      title={rail ? label : undefined}
      className="group/hd flex h-9 w-full items-center gap-2.5 whitespace-nowrap rounded-md px-2 text-left transition-colors duration-fast hover:bg-sidebar-surface"
    >
      <GroupChip group={group} open={isOpen} marked={marked} />
      <span className={cn(
        'min-w-0 flex-1 truncate font-display text-[15px] font-semibold leading-5 tracking-[0.005em] transition-[opacity,color] duration-base rail:opacity-0',
        isOpen || holdsActive ? 'text-sidebar-text' : 'text-sidebar-text/70 group-hover/hd:text-sidebar-text',
      )}>
        {label}
        {marked && <span className="sr-only">, {t('navActiveGroup')}</span>}
      </span>
      {!isOpen && <ClosedGroupHint count={count} hasSignal={hasSignal} />}
      <ChevronDown aria-hidden className={cn('size-3.5 shrink-0 text-sidebar-muted transition-transform duration-base rail:hidden', !isOpen && '-rotate-90')} />
    </button>
  );
}

function ClosedGroupHint({ count, hasSignal }: { count: number; hasSignal: boolean }) {
  return (
    <>
      {hasSignal && <LiveDot className="rail:hidden" />}
      <span aria-hidden className="num min-w-4 text-right text-xs text-sidebar-muted rail:hidden">{count}</span>
    </>
  );
}

function NavGroup({ group, items, activeId, isOpen, rail, onToggle, onNavigate, updateDotId }: {
  group: ScreenGroupId;
  items: ScreenDef[];
  activeId: string | undefined;
  isOpen: boolean;
  rail: boolean;
  onToggle: () => void;
  onNavigate: () => void;
  updateDotId: string | null;
}) {
  const panelId = `nav-group-${group}`;
  return (
    <div className="relative" style={accentStyle(GROUP_META[group].accent)}>
      <GroupHeader
        group={group}
        count={items.length}
        isOpen={isOpen}
        holdsActive={items.some((it) => it.id === activeId)}
        hasSignal={items.some((it) => it.live || it.id === updateDotId)}
        rail={rail}
        panelId={panelId}
        onToggle={onToggle}
      />
      <div
        id={panelId}
        className={cn('relative grid transition-[grid-template-rows] duration-base ease-out motion-reduce:transition-none', isOpen ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]')}
      >
        <span aria-hidden className={cn('pointer-events-none absolute inset-y-1 -left-1.5 w-px rounded-full bg-nav/40 transition-opacity duration-base', isOpen ? 'opacity-100' : 'opacity-0')} />
        <ul className="min-h-0 overflow-hidden" aria-hidden={!isOpen || undefined}>
          {items.map((it) => (
            <NavItem key={it.id} item={it} on={it.id === activeId} focusable={isOpen} rail={rail} showUpdateDot={it.id === updateDotId} onNavigate={onNavigate} />
          ))}
        </ul>
      </div>
    </div>
  );
}

/** Akkordeon: bitta guruh ochiq. Faol sahifa boshqa guruhga o'tsa — o'sha guruh ochiladi (render paytida sinxron). */
function useAccordion(activeGroup: ScreenGroupId | undefined) {
  const [open, setOpen] = useState<ScreenGroupId | null>(activeGroup ?? null);
  const [synced, setSynced] = useState(activeGroup);
  if (activeGroup !== synced) {
    setSynced(activeGroup);
    if (activeGroup) setOpen(activeGroup);
  }
  const toggle = useCallback((g: ScreenGroupId) => setOpen((cur) => accordionNext(cur, g)), []);
  return [open, toggle] as const;
}

/** Rejim (pinned/rail) — localStorage'ga yoziladi; `shortcut` bo'lsa Ctrl/⌘+B almashtiradi. */
function useNavMode(shortcut: boolean) {
  const [mode, setMode] = useState<NavMode>(loadNavMode);
  const toggle = useCallback(() => setMode((m) => (m === 'pinned' ? 'rail' : 'pinned')), []);
  useEffect(() => saveNavMode(mode), [mode]);
  useEffect(() => {
    if (!shortcut) return undefined;
    const onKey = (e: KeyboardEvent) => {
      if (!isNavToggleShortcut(e)) return;
      e.preventDefault();
      toggle();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [shortcut, toggle]);
  return [mode, toggle] as const;
}

/** Sichqoncha bosganda emas, faqat klaviatura fokusida ochiladi — aks holda bosilgan havola menyuni ochiq ushlab qoladi. */
function isKeyboardFocus(el: EventTarget): boolean {
  try {
    return el instanceof Element && el.matches(':focus-visible');
  } catch {
    return true;
  }
}

/** Rail ustiga sichqoncha (kechikish bilan) yoki klaviatura fokusi kelganda vaqtincha ochish. */
function useRailPeek(enabled: boolean) {
  const [hover, setHover] = useState(false);
  const [focused, setFocused] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  const later = (value: boolean, ms: number) => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setHover(value), ms);
  };
  const close = useCallback(() => {
    window.clearTimeout(timer.current);
    setHover(false);
  }, []);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  const handlers = {
    onPointerEnter: () => later(true, PEEK_OPEN_MS),
    onPointerLeave: () => later(false, PEEK_CLOSE_MS),
    onFocus: (e: FocusEvent<HTMLElement>) => setFocused(isKeyboardFocus(e.target)),
    onBlur: (e: FocusEvent<HTMLElement>) => {
      if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setFocused(false);
    },
  };
  return { peek: enabled && (hover || focused), handlers, close };
}

/** Joy egasi: kontentni faqat qotirilgan kenglikka suradi; ochilgan rail overlay'i uchun z-indeks ko'tariladi. */
function spacerClass(rail: boolean, peek: boolean, embedded?: boolean): string {
  return cn(
    'shrink-0 lg:transition-[width] lg:duration-base lg:ease-out',
    rail ? 'lg:w-sidebar-collapsed' : 'lg:w-sidebar',
    embedded ? 'lg:relative' : 'lg:sticky lg:top-0 lg:h-dvh',
    peek ? 'lg:z-drawer' : 'lg:z-sidebar',
  );
}

/** Desktop: absolut panel (60 ↔ 248px). Mobil: avvalgidek chapdan chiqadigan drawer. */
function asideClass(compact: boolean, peek: boolean, mobileOpen: boolean): string {
  return cn(
    'flex w-sidebar flex-col overflow-hidden bg-sidebar-bg text-sidebar-text',
    'lg:absolute lg:inset-y-0 lg:left-0 lg:transition-[width,box-shadow] lg:duration-base lg:ease-out',
    compact ? 'lg:w-sidebar-collapsed' : 'lg:w-sidebar',
    peek && 'lg:shadow-modal',
    'max-lg:fixed max-lg:inset-y-0 max-lg:left-0 max-lg:z-sidebar max-lg:transition-transform max-lg:duration-base',
    !mobileOpen && 'max-lg:-translate-x-full',
  );
}

/** Qotirilgan: «yig'ish» (rail'ga). Rail (ochilganda ko'rinadi): «qotirish». Faqat desktop. */
function ModeToggle({ rail, onToggle }: { rail: boolean; onToggle: () => void }) {
  const { t } = useTranslation();
  const label = rail ? t('navMode.pin') : t('navMode.collapse');
  const Icon = rail ? Pin : PanelLeftClose;
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={label}
      aria-keyshortcuts="Control+B Meta+B"
      title={t('navMode.hint', { label })}
      className="ml-auto grid size-7 shrink-0 place-items-center rounded-md text-sidebar-muted transition-colors duration-fast hover:bg-sidebar-surface hover:text-sidebar-text max-lg:hidden rail:opacity-0"
    >
      <Icon aria-hidden className="size-4" />
    </button>
  );
}

export type SidebarProps = {
  activeId: string | undefined;
  docsActive: boolean;
  permissions: string[] | undefined;
  /** `showUpdateDot` ekranning `id`si (odatda `'update'`) yoki `null`. */
  updateDotId: string | null;
  /** /design namunasida — ramka ichida, global Ctrl+B ulanmaydi. */
  embedded?: boolean;
  /** Mobil drawer ochiqmi (desktop'da e'tiborsiz). */
  mobileOpen: boolean;
  onNavigate: () => void;
  footer?: ReactNode;
};

export function Sidebar({ activeId, docsActive, permissions, updateDotId, embedded, mobileOpen, onNavigate, footer }: SidebarProps) {
  const { t } = useTranslation();
  const [mode, toggleMode] = useNavMode(!embedded);
  const rail = mode === 'rail';
  const { peek, handlers, close } = useRailPeek(rail);
  const compact = rail && !peek;
  const [openGroup, toggleGroup] = useAccordion(SCREENS.find((s) => s.id === activeId)?.group);
  // Rejim almashganda «osilib qolgan» hover'ni tozalaymiz — yig'ish bosilganda menyu darhol yig'ilsin.
  useEffect(close, [mode, close]);

  return (
    <div className={spacerClass(rail, peek, embedded)}>
      <aside aria-label={t('mainNavAriaLabel')} data-compact={compact} {...handlers} className={asideClass(compact, peek, mobileOpen)}>
        <div className="flex h-header shrink-0 items-center gap-2 border-b border-sidebar-border pl-4 pr-2.5">
          <BrandMark wordClassName="transition-opacity duration-base rail:opacity-0" />
          <ModeToggle rail={rail} onToggle={toggleMode} />
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto overflow-x-hidden px-2.5 py-3 [scrollbar-width:thin]">
          {GROUP_ORDER.map((g) => {
            const items = byGroup(g, permissions);
            if (items.length === 0) return null;
            return (
              <NavGroup
                key={g}
                group={g}
                items={items}
                activeId={activeId}
                isOpen={openGroup === g}
                rail={rail}
                onToggle={() => toggleGroup(g)}
                onNavigate={onNavigate}
                updateDotId={updateDotId}
              />
            );
          })}
          <ul className="!mt-2 border-t border-sidebar-border pt-2.5" style={accentStyle('brand-fire')}>
            <NavItem item={DOCS_NAV} on={docsActive} focusable rail={rail} showUpdateDot={false} onNavigate={onNavigate} />
          </ul>
        </nav>
        {footer && <div className="shrink-0 border-t border-sidebar-border transition-opacity duration-base rail:invisible rail:opacity-0">{footer}</div>}
      </aside>
    </div>
  );
}
