// Sof draft<->kontrakt aylanish funksiyalari (M8 §5). React'siz — testlash va CRAP past ushlab turish uchun.
import { splitList } from '@/lib/validators';
import type {
  NetworkConfigIn, NetworkFieldError, NetworkInterface, NetworkInterfaceMode, NetworkStateOut, NetworkStaticRoute,
} from '@/api/types';

/** `managed` — interfeys `apply`ga yuboriladimi: allaqachon dhcp/static sozlangan yoki foydalanuvchi modalda saqlagan.
 *  Sozlanmagan/`manual` (masalan bond a'zosi) va tahrirlanmaydigan interfeyslar yuborilmaydi — netd ularga tegmaydi. */
export type InterfaceDraft = { name: string; mode: 'dhcp' | 'static'; address: string; gateway: string; mtu: string; managed: boolean };
export type RouteDraft = { key: string; destination: string; gateway: string; interface: string; metric: string };
export type NetworkDraft = {
  hostname: string;
  dnsServers: string;
  dnsSearch: string;
  interfaces: InterfaceDraft[];
  routes: RouteDraft[];
};

/** Shartnomada draft faqat `dhcp`/`static` tanlay oladi — `manual`/`unconfigured` holatini DHCP sifatida boshlaydi. */
function draftMode(mode: NetworkInterfaceMode): 'dhcp' | 'static' {
  return mode === 'static' ? 'static' : 'dhcp';
}

function interfaceStateToDraft(i: NetworkInterface): InterfaceDraft {
  return {
    name: i.name,
    mode: draftMode(i.config.mode),
    address: i.config.address ?? '',
    gateway: i.config.gateway ?? '',
    mtu: i.config.mtu != null ? String(i.config.mtu) : '',
    managed: i.editable && (i.config.mode === 'dhcp' || i.config.mode === 'static'),
  };
}

function routeStateToDraft(r: NetworkStaticRoute, index: number): RouteDraft {
  return {
    key: `seed-${index}`,
    destination: r.destination,
    gateway: r.gateway ?? '',
    interface: r.interface ?? '',
    metric: r.metric != null ? String(r.metric) : '',
  };
}

export function stateToDraft(state: NetworkStateOut): NetworkDraft {
  return {
    hostname: state.hostname,
    dnsServers: state.dns.servers.join(', '),
    dnsSearch: state.dns.search.join(', '),
    interfaces: state.interfaces.map(interfaceStateToDraft),
    routes: state.routes.static.map(routeStateToDraft),
  };
}

function interfaceDraftToConfig(i: InterfaceDraft): NetworkConfigIn['interfaces'][number] {
  return {
    name: i.name,
    mode: i.mode,
    address: i.mode === 'static' ? i.address.trim() || null : null,
    gateway: i.mode === 'static' ? i.gateway.trim() || null : null,
    mtu: i.mtu.trim() ? Number(i.mtu) : null,
  };
}

function routeDraftToConfig(r: RouteDraft): NetworkConfigIn['routes'][number] {
  return {
    destination: r.destination.trim(),
    gateway: r.gateway.trim() || null,
    interface: r.interface.trim() || null,
    metric: r.metric.trim() ? Number(r.metric) : null,
  };
}

export function draftToConfig(draft: NetworkDraft, timeoutS: number): NetworkConfigIn {
  return {
    hostname: draft.hostname.trim(),
    dns: { servers: splitList(draft.dnsServers), search: splitList(draft.dnsSearch) },
    interfaces: draft.interfaces.filter((i) => i.managed).map(interfaceDraftToConfig),
    routes: draft.routes.map(routeDraftToConfig),
    timeout_s: timeoutS,
  };
}

export function newRouteDraft(): RouteDraft {
  return { key: `new-${Math.random().toString(36).slice(2, 9)}`, destination: '', gateway: '', interface: '', metric: '' };
}

export const TIMEOUT_OPTIONS = [60, 120, 180, 300] as const;
export const DEFAULT_TIMEOUT_S = 180;

/** Berilgan dot-path'ga mos server xatosi (`parseNetworkFieldPath` bilan bogʻlangan konvensiya). */
export function fieldErrorIn(errors: NetworkFieldError[], field: string): string | undefined {
  return errors.find((e) => e.field === field)?.message;
}

/** `interfaces`/`routes` kabi "umumiy" (aniq maydonga bogʻlanmagan) xatolar — banner uchun. */
export function genericErrors(errors: NetworkFieldError[]): string[] {
  return errors.filter((e) => e.field === 'interfaces' || e.field === 'routes').map((e) => e.message);
}

/** netd xato yo'llari (`interfaces[0].address`, `routes[1].gateway`) → UI konvensiyasi
 *  (`interfaces.ens18.address`, `routes.1.gateway`). Indeks yuborilgan `config` ro'yxatiga tegishli. */
export function normalizeServerErrors(errors: NetworkFieldError[], config: NetworkConfigIn): NetworkFieldError[] {
  return errors.map((e) => {
    const m = /^(interfaces|routes)\[(\d+)\](.*)$/.exec(e.field);
    if (!m) return e;
    const [, list, idx, rest] = m;
    const name = list === 'interfaces' ? config.interfaces[Number(idx)]?.name : idx;
    return name === undefined ? e : { ...e, field: `${list}.${name}${rest}` };
  });
}

/** Jadvalda ko'rsatiladigan rejim: draft (modalda saqlangan) yoki fayldagi holat.
 *  Tahrirlanmaydigan va sozlanmagan interfeys uchun `null` — UI "—" ko'rsatadi
 *  (masalan netplan/NM ostidagi yoki bond a'zosi interfeys). */
export function displayMode(iface: NetworkInterface, draft: InterfaceDraft): NetworkInterfaceMode | null {
  const mode = draft.managed ? draft.mode : iface.config.mode;
  return !iface.editable && mode === 'unconfigured' ? null : mode;
}
