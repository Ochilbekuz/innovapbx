import { createElement, type ReactNode } from 'react';
import { hasPermission } from '@/auth/permissions';
import {
  Activity, ArrowRightLeft, AudioLines, Blocks, Cable, ChartNoAxesCombined, Gauge, Route, Settings2, UsersRound, BadgeCheck, BellRing, BookUser, CalendarClock, ChartNoAxesColumn, CircleUserRound,
  ClipboardCheck, Clock, DatabaseBackup, EthernetPort, Flame, Grid3x3, Hash, History, IdCard, KeyRound, LayoutDashboard, ListOrdered,
  Lock, Megaphone, Mic2, Network, ParkingSquare, PhoneIncoming, PhoneMissed, PhoneOutgoing, Plug, RadioTower, RefreshCw, ScrollText,
  ServerCog, Shuffle, ShieldCheck, ShieldOff, Smartphone, SunMoon, UserCog, Users, Voicemail, Waypoints,
} from 'lucide-react';

/**
 * Yagona manba: recon.md S01–S36 (S20 bundan tashqari — mobil ilova, doiradan tashqari).
 * Bu yerdan AppShell (sidebar) va router ikkisi ham o'qiydi — guruh/sarlavha bir joyda yashaydi.
 */
export type ScreenGroupId = 'overview' | 'users' | 'connect' | 'routing' | 'apps' | 'reports' | 'system';
export const GROUP_ORDER: ScreenGroupId[] = ['overview', 'users', 'connect', 'routing', 'apps', 'reports', 'system'];

export type ScreenDef = {
  id: string;
  reconId: string;
  path: string;
  icon: ReactNode;
  group: ScreenGroupId;
  /** M0 da to'liq qurilgan (boshqalari "tez orada" stub). */
  full?: boolean;
  count?: number;
  live?: boolean;
};

const icon = (I: typeof Activity) => createElement(I);

/**
 * Har asosiy guruhning belgisi va aksent rangi (token nomi, qiymati `replica/design/tokens.json` → `nav-*`).
 * `Record` — yangi guruh qo'shilsa, rangsiz qolib ketmaydi (kompilyator talab qiladi).
 */
export const GROUP_META: Record<ScreenGroupId, { icon: ReactNode; accent: `nav-${ScreenGroupId}` }> = {
  overview: { icon: icon(Gauge), accent: 'nav-overview' },
  users: { icon: icon(UsersRound), accent: 'nav-users' },
  connect: { icon: icon(Cable), accent: 'nav-connect' },
  routing: { icon: icon(Route), accent: 'nav-routing' },
  apps: { icon: icon(Blocks), accent: 'nav-apps' },
  reports: { icon: icon(ChartNoAxesCombined), accent: 'nav-reports' },
  system: { icon: icon(Settings2), accent: 'nav-system' },
};

export const SCREENS: ScreenDef[] = [
  { id: 'dashboard', reconId: 'S03', path: '/dashboard', icon: icon(LayoutDashboard), group: 'overview' },
  { id: 'live', reconId: 'S29', path: '/live', icon: icon(Activity), group: 'overview', live: true, full: true },

  { id: 'extensions', reconId: 'S04', path: '/extensions', icon: icon(Users), group: 'users', full: true },
  { id: 'devices', reconId: 'S35', path: '/devices', icon: icon(Smartphone), group: 'users', full: true },
  { id: 'portal', reconId: 'S30', path: '/me', icon: icon(CircleUserRound), group: 'users', full: true },

  { id: 'trunks', reconId: 'S06', path: '/trunks', icon: icon(Network), group: 'connect', full: true },
  { id: 'inbound', reconId: 'S07', path: '/inbound', icon: icon(PhoneIncoming), group: 'connect', full: true },
  { id: 'outbound', reconId: 'S22', path: '/outbound', icon: icon(PhoneOutgoing), group: 'connect', full: true },
  // M9: shartnomada S-raqam berilmagan — yangi qo'shilgan ekranlar (M8 bilan bir xil izoh).
  { id: 'pinsets', reconId: 'S42', path: '/pinsets', icon: icon(KeyRound), group: 'connect', full: true },
  { id: 'cidsources', reconId: 'S43', path: '/cidsources', icon: icon(IdCard), group: 'connect', full: true },

  { id: 'timegroups', reconId: 'S08', path: '/timegroups', icon: icon(CalendarClock), group: 'routing', full: true },
  { id: 'ivr', reconId: 'S09', path: '/ivr', icon: icon(Grid3x3), group: 'routing', full: true },
  { id: 'queues', reconId: 'S10', path: '/queues', icon: icon(ListOrdered), group: 'routing', full: true },
  { id: 'ringgroups', reconId: 'S21', path: '/ringgroups', icon: icon(Waypoints), group: 'routing', full: true },
  { id: 'misc', reconId: 'S28', path: '/misc', icon: icon(Shuffle), group: 'routing', full: true },
  // M9: shartnomada (m9-freepbx-gaps-contract.md) S-raqam berilmagan — recon ro'yxatiga yangi qo'shilgan ekran (M8 bilan bir xil izoh).
  { id: 'announcements', reconId: 'S39', path: '/announcements', icon: icon(Megaphone), group: 'routing', full: true },
  // M12 A1: shartnomada (m12-contract.md §A1) S-raqam berilmagan — yangi qo'shilgan ekran (M8/M9 bilan bir xil izoh).
  { id: 'day_night', reconId: 'S46', path: '/day-night', icon: icon(SunMoon), group: 'routing', full: true },

  { id: 'audio', reconId: 'S11', path: '/audio', icon: icon(AudioLines), group: 'apps', full: true },
  { id: 'voicemail', reconId: 'S23', path: '/voicemail', icon: icon(Voicemail), group: 'apps' },
  { id: 'conference', reconId: 'S25', path: '/conference', icon: icon(Mic2), group: 'apps', full: true },
  { id: 'parking', reconId: 'S26', path: '/parking', icon: icon(ParkingSquare), group: 'apps', full: true },
  { id: 'blacklist', reconId: 'S27', path: '/blacklist', icon: icon(ShieldOff), group: 'apps', full: true },
  { id: 'campaigns', reconId: 'S18', path: '/campaigns', icon: icon(Megaphone), group: 'apps', full: true },
  // M9: shartnomada S-raqam berilmagan — yangi qo'shilgan ekranlar (M8 bilan bir xil izoh).
  { id: 'paging', reconId: 'S40', path: '/paging', icon: icon(RadioTower), group: 'apps', full: true },
  { id: 'phonebook', reconId: 'S41', path: '/phonebook', icon: icon(BookUser), group: 'apps', full: true },
  // M10 C A2: shartnomada S-raqam berilmagan — yangi qo'shilgan ekran (M8/M9 bilan bir xil izoh).
  { id: 'missedcalls', reconId: 'S44', path: '/missed-calls', icon: icon(PhoneMissed), group: 'apps', full: true },
  // M12 A2: shartnomada (m12-contract.md §A2) S-raqam berilmagan — yangi qo'shilgan ekran (M8/M9 bilan bir xil izoh).
  { id: 'disa', reconId: 'S47', path: '/disa', icon: icon(Lock), group: 'apps', full: true },

  { id: 'cdr', reconId: 'S12', path: '/cdr', icon: icon(History), group: 'reports', full: true },
  { id: 'analytics', reconId: 'S13', path: '/analytics', icon: icon(ChartNoAxesColumn), group: 'reports', full: true },
  { id: 'quality', reconId: 'S14', path: '/quality', icon: icon(ClipboardCheck), group: 'reports', full: true },

  { id: 'sip', reconId: 'S32', path: '/settings/sip', icon: icon(ServerCog), group: 'system', full: true },
  { id: 'audit', reconId: 'S37', path: '/settings/audit', icon: icon(ScrollText), group: 'system', full: true },
  { id: 'security', reconId: 'S33', path: '/settings/security', icon: icon(ShieldCheck), group: 'system', full: true },
  { id: 'alerts', reconId: 'S33', path: '/settings/alerts', icon: icon(BellRing), group: 'system', full: true },
  { id: 'backup', reconId: 'S34', path: '/settings/backup', icon: icon(DatabaseBackup), group: 'system', full: true },
  // M5a: shartnomada (m5a-contract.md) S36 berilgan, lekin u allaqachon pastdagi `status` ekraniga
  // tayinlangan — mavjud kelishmovchilik, "status"ni o'zgartirish bu vazifa doirasidan tashqarida.
  { id: 'migration', reconId: 'S36', path: '/settings/migration', icon: icon(ArrowRightLeft), group: 'system', full: true },
  { id: 'status', reconId: 'S36', path: '/settings/status', icon: icon(ServerCog), group: 'system' },
  // M8: shartnomada (m8-network-contract.md §5) S-raqam berilmagan — recon ro'yxatiga yangi qo'shilgan ekran.
  { id: 'network', reconId: 'S38', path: '/settings/network', icon: icon(EthernetPort), group: 'system', full: true },
  { id: 'featurecodes', reconId: 'S24', path: '/settings/feature-codes', icon: icon(Hash), group: 'system', full: true },
  { id: 'integrations', reconId: 'S15', path: '/settings/integrations', icon: icon(Plug), group: 'system', full: true },
  { id: 'license', reconId: 'S19', path: '/settings/license', icon: icon(BadgeCheck), group: 'system' },
  { id: 'users', reconId: 'S31', path: '/settings/users', icon: icon(UserCog), group: 'system', full: true },
  // M11 — qarang ../../replica/m11-update-contract.md. S-raqam yo'q (M8 `network`dagi kabi yangi qo'shilgan).
  { id: 'update', reconId: 'S45', path: '/settings/update', icon: icon(RefreshCw), group: 'system', full: true },
  // M12 B1 — qarang ../../replica/m12-contract.md §B1. S-raqam yo'q (M8 `network`dagi kabi yangi qo'shilgan).
  { id: 'time', reconId: 'S48', path: '/settings/time', icon: icon(Clock), group: 'system' },
  // M12 B3 — qarang ../../replica/m12-contract.md §B3. S-raqam yo'q (M8 `network`dagi kabi yangi qo'shilgan).
  { id: 'firewall', reconId: 'S49', path: '/settings/firewall', icon: icon(Flame), group: 'system', full: true },
];

/** Sidebarda ko'rsatilmaydigan, lekin marshruti bo'lishi kerak bo'lgan ekranlar (recon'dagi qolgan ID'lar). */
export const EXTRA_ROUTES = [
  { reconId: 'S05', path: '/extensions/:id', titleKey: 'extensionCard' },
  { reconId: 'S16', path: '/softphone', titleKey: 'softphone' },
  { reconId: 'S17', path: '/settings/integrations/widget', titleKey: 'widget' },
];

/**
 * Operator roli faqat shaxsiy kabinet va o'z qo'ng'iroqlari tarixini ko'radi (M2b §4) — endi bu
 * `operator` rolining HAQIQIY ruxsatlari (`calls:read:own`) orqali `isScreenVisible` natijasi bilan
 * mos keladi, lekin eski (vaqtinchalik) selektorlar hali shu ro'yxatga tayanishi mumkin.
 */
export const OPERATOR_VISIBLE_IDS = ['portal', 'cdr'];

/** M7 §1 jadvali: ekran id → hudud. `system` guruhidagilar bu yerda yo'q — alohida (faqat `*`) tekshiriladi. */
export type Hudud = 'monitor' | 'extensions' | 'connect' | 'routing' | 'apps' | 'reports';
export const HUDUD_LIST: Hudud[] = ['monitor', 'extensions', 'connect', 'routing', 'apps', 'reports'];

export const SCREEN_HUDUD: Partial<Record<string, Hudud>> = {
  dashboard: 'monitor', live: 'monitor',
  extensions: 'extensions', devices: 'extensions', voicemail: 'extensions',
  trunks: 'connect', inbound: 'connect', outbound: 'connect', pinsets: 'connect', cidsources: 'connect',
  timegroups: 'routing', ivr: 'routing', queues: 'routing', ringgroups: 'routing', misc: 'routing', announcements: 'routing',
  day_night: 'routing',
  audio: 'apps', conference: 'apps', parking: 'apps', blacklist: 'apps', campaigns: 'apps', paging: 'apps', phonebook: 'apps',
  missedcalls: 'apps', disa: 'apps',
  cdr: 'reports', analytics: 'reports', quality: 'reports',
};

/** Hech qanday ruxsatsiz ham barcha foydalanuvchiga ko'rinadigan ekranlar (M7 §4 — "portal hammaga"). */
const ALWAYS_VISIBLE_IDS = ['portal'];

/**
 * Sof funksiya (M7 §1/§4): ekran berilgan `permissions` bilan ko'rinadimi. `cdr` maxsus — `reports:view`
 * (yoki `:edit`) HAMMA chaqiruvlarni, `calls:read:own` esa faqat o'zinikini ko'rsatadi, lekin ekran
 * darajasida ikkisi ham "ko'rinadi" deb hisoblanadi (filtrlash sahifa ichida). Xaritada yo'q
 * (`system` guruhi) ekranlar faqat `*` bilan ko'rinadi — fail-closed.
 */
export function isScreenVisible(screen: Pick<ScreenDef, 'id' | 'group'>, permissions: string[] | undefined): boolean {
  if (ALWAYS_VISIBLE_IDS.includes(screen.id)) return true;
  if (hasPermission(permissions, '*')) return true;
  if (screen.group === 'system') return false;
  if (screen.id === 'cdr') {
    return hasPermission(permissions, 'reports:view') || hasPermission(permissions, 'reports:edit') || hasPermission(permissions, 'calls:read:own');
  }
  const hudud = SCREEN_HUDUD[screen.id];
  if (!hudud) return false;
  return hasPermission(permissions, `${hudud}:view`) || hasPermission(permissions, `${hudud}:edit`);
}

/** Guruh ichidagi, joriy `permissions`ga ko'ra ko'rinadigan ekranlar (sidebar uchun). */
export const byGroup = (g: ScreenGroupId, permissions?: string[]) =>
  SCREENS.filter((s) => s.group === g && isScreenVisible(s, permissions));

/** `portal`dan tashqari, SCREENS tartibidagi birinchi ko'rinadigan ekran (bosh sahifa qoidasi uchun). */
export function firstVisibleScreen(permissions: string[] | undefined): ScreenDef | undefined {
  return SCREENS.find((s) => s.id !== 'portal' && isScreenVisible(s, permissions));
}
