// Sof tarmoq validatsiya/diff mantiqi — M8 (../../replica/m8-network-contract.md §4). `src/api/fake.ts`
// (backend/netd'ni simulyatsiya qiladi) va `src/screens/network/*` shu yerdan foydalanadi — qoida bitta joyda
// yashaydi (dryer). Shartnomada `errors[].field` uchun aniq format berilmagan — "interfaces.<nom>.<maydon>" /
// "routes.<indeks>.<maydon>" shaklini o'zimiz tanladik (UI shu bo'yicha tegishli maydonni topadi).
import { isValidCidr, isValidHost, isValidIPv4 } from '@/lib/validators';
import type { NetworkConfigIn, NetworkFieldError, NetworkInterface, NetworkStaticRoute } from '@/api/types';

type KnownInterface = Pick<NetworkInterface, 'name' | 'editable' | 'config'>;
type CurrentNetworkSnapshot = { hostname: string; dns: { servers: string[]; search: string[] }; interfaces: NetworkInterface[]; routes: NetworkStaticRoute[] };

function ipToInt(ip: string): number {
  return ip.split('.').reduce((acc, octet) => (acc << 8) + Number(octet), 0) >>> 0;
}

/** CIDR manzilni {address, prefix}ga ajratadi — notoʻgʻri boʻlsa `null` (chaqiruvchi avval `isValidCidr` tekshiradi). */
function cidrParts(cidr: string): { address: string; prefix: number } {
  const [address, prefix] = cidr.split('/');
  return { address: address ?? '', prefix: Number(prefix ?? 0) };
}

/** Berilgan IP manzil shu CIDR tarmog'iga tushadimi (M8 §4: "gateway interfeys subnetida bo'lishi kerak"). */
export function addressInSubnet(ip: string, cidr: string): boolean {
  if (!isValidIPv4(ip) || !isValidCidr(cidr)) return false;
  const { address, prefix } = cidrParts(cidr);
  const mask = prefix === 0 ? 0 : (0xffffffff << (32 - prefix)) >>> 0;
  return (ipToInt(ip) & mask) === (ipToInt(address) & mask);
}

function validateHostname(hostname: string, errors: NetworkFieldError[]): void {
  if (!hostname.trim() || !isValidHost(hostname) || isValidIPv4(hostname)) {
    errors.push({ field: 'hostname', message: "Host nomi notoʻgʻri (RFC1123, IP emas)." });
  }
}

function validateInterfaces(config: NetworkConfigIn, known: KnownInterface[], errors: NetworkFieldError[]): void {
  const gateways: string[] = [];
  for (const ifc of config.interfaces) {
    const prefix = `interfaces.${ifc.name}`;
    const existing = known.find((k) => k.name === ifc.name);
    if (!existing) { errors.push({ field: prefix, message: 'Bunday interfeys topilmadi.' }); continue; }
    if (!existing.editable) { errors.push({ field: prefix, message: 'Bu interfeys tahrirlanmaydi.' }); continue; }
    if (ifc.mode !== 'static') continue;
    if (!ifc.address) { errors.push({ field: `${prefix}.address`, message: 'Statik rejimda manzil majburiy.' }); continue; }
    if (!isValidCidr(ifc.address)) { errors.push({ field: `${prefix}.address`, message: 'Manzil CIDR koʻrinishida boʻlishi kerak (masalan 192.168.1.10/24).' }); continue; }
    if (!ifc.gateway) continue;
    gateways.push(ifc.gateway);
    if (!isValidIPv4(ifc.gateway)) errors.push({ field: `${prefix}.gateway`, message: "Shlyuz manzili notoʻgʻri." });
    else if (!addressInSubnet(ifc.gateway, ifc.address)) errors.push({ field: `${prefix}.gateway`, message: 'Shlyuz shu interfeys tarmogʻida emas.' });
  }
  if (gateways.length > 1) errors.push({ field: 'interfaces', message: "Faqat bitta interfeysda standart shlyuz boʻlishi mumkin." });
  const stillAddressed = config.interfaces.some((i) => i.mode === 'dhcp' || (i.mode === 'static' && !!i.address && isValidCidr(i.address)));
  if (!stillAddressed) errors.push({ field: 'interfaces', message: 'Kamida bitta interfeys manzilga ega boʻlishi kerak.' });
}

function validateRoutes(config: NetworkConfigIn, errors: NetworkFieldError[]): void {
  const seen = new Set<string>();
  config.routes.forEach((route, index) => {
    const prefix = `routes.${index}`;
    if (route.destination === '0.0.0.0/0') errors.push({ field: `${prefix}.destination`, message: "Standart marshrut (0.0.0.0/0) bu yerda taqiqlangan — shlyuzni \"Umumiy\" boʻlimida belgilang." });
    else if (!isValidCidr(route.destination)) errors.push({ field: `${prefix}.destination`, message: 'Manzil CIDR koʻrinishida boʻlishi kerak.' });
    if (!route.gateway && !route.interface) errors.push({ field: `${prefix}.gateway`, message: 'Shlyuz yoki interfeys koʻrsatilishi kerak.' });
    if (route.gateway) {
      if (!isValidIPv4(route.gateway)) errors.push({ field: `${prefix}.gateway`, message: "Shlyuz manzili notoʻgʻri." });
      else if (!config.interfaces.some((i) => i.mode === 'static' && i.address && isValidCidr(i.address) && addressInSubnet(route.gateway!, i.address))) {
        errors.push({ field: `${prefix}.gateway`, message: 'Shlyuz birorta interfeys tarmogʻiga tushmaydi.' });
      }
    }
    const key = `${route.destination}|${route.metric ?? ''}`;
    if (seen.has(key)) errors.push({ field: `${prefix}.destination`, message: 'Takroriy marshrut (manzil + metrik).' });
    seen.add(key);
  });
}

/** To'liq server-tomoni validatsiya (M8 §4 qoidalari). `known` — hozirgi holatdagi interfeyslar (nom/editable). */
export function validateNetworkConfig(config: NetworkConfigIn, known: KnownInterface[]): NetworkFieldError[] {
  const errors: NetworkFieldError[] = [];
  validateHostname(config.hostname, errors);
  validateInterfaces(config, known, errors);
  validateRoutes(config, errors);
  return errors;
}

function describeInterface(mode: string, address: string | null): string {
  return address ? `${mode} ${address}` : mode;
}

/** Yuborilayotgan konfiguratsiya bilan joriy holat orasidagi inson-o'qiydigan farq roʻyxati (confirm modal + sticky bar hisoblagichi). */
export function buildNetworkDiff(next: NetworkConfigIn, current: CurrentNetworkSnapshot): string[] {
  const lines: string[] = [];
  if (next.hostname !== current.hostname) lines.push(`Host nomi: ${current.hostname} → ${next.hostname}`);
  if (next.dns.servers.join(',') !== current.dns.servers.join(',')) {
    lines.push(`DNS serverlar: ${current.dns.servers.join(', ') || '—'} → ${next.dns.servers.join(', ') || '—'}`);
  }
  if (next.dns.search.join(',') !== current.dns.search.join(',')) {
    lines.push(`Qidiruv domenlari: ${current.dns.search.join(', ') || '—'} → ${next.dns.search.join(', ') || '—'}`);
  }
  for (const ifc of next.interfaces) {
    const cur = current.interfaces.find((c) => c.name === ifc.name);
    if (!cur) continue;
    const curDesc = describeInterface(cur.config.mode, cur.config.address);
    const nextDesc = describeInterface(ifc.mode, ifc.address);
    if (curDesc !== nextDesc || cur.config.gateway !== ifc.gateway || cur.config.mtu !== ifc.mtu) {
      lines.push(`${ifc.name}: ${curDesc} → ${nextDesc}`);
    }
  }
  const routeKey = (r: { destination: string; gateway: string | null; interface: string | null; metric: number | null }) =>
    `${r.destination}|${r.gateway ?? ''}|${r.interface ?? ''}|${r.metric ?? ''}`;
  const curKeys = new Set(current.routes.map(routeKey));
  const nextKeys = new Set(next.routes.map(routeKey));
  next.routes.forEach((r) => { if (!curKeys.has(routeKey(r))) lines.push(`+ marshrut ${r.destination}`); });
  current.routes.forEach((r) => { if (!nextKeys.has(routeKey(r))) lines.push(`− marshrut ${r.destination}`); });
  return lines;
}

export type NetworkFieldPath =
  | { kind: 'hostname' }
  | { kind: 'interface'; name: string; sub: 'name' | 'address' | 'gateway' }
  | { kind: 'route'; index: number; sub: 'destination' | 'gateway' }
  | { kind: 'other' };

/** Server xato maydonini (`interfaces.ens18.address` / `routes.0.gateway`) UI qaysi inputga tegishli ekanini aniqlash uchun ajratadi. */
export function parseNetworkFieldPath(field: string): NetworkFieldPath {
  if (field === 'hostname') return { kind: 'hostname' };
  const ifaceMatch = /^interfaces\.([^.]+)\.(name|address|gateway)$/.exec(field);
  if (ifaceMatch) return { kind: 'interface', name: ifaceMatch[1]!, sub: ifaceMatch[2] as 'name' | 'address' | 'gateway' };
  const routeMatch = /^routes\.(\d+)\.(destination|gateway)$/.exec(field);
  if (routeMatch) return { kind: 'route', index: Number(routeMatch[1]), sub: routeMatch[2] as 'destination' | 'gateway' };
  return { kind: 'other' };
}

/** Oʻzgartirilayotgan interfeysga ulangan brauzer uzilib qolishi mumkinmi — ogohlantirish matni (M8 §4 "warning text template"). */
export function buildNetworkWarnings(config: NetworkConfigIn, current: NetworkInterface[], browserHost: string | null, timeoutS: number): string[] {
  if (!browserHost) return [];
  const warnings: string[] = [];
  for (const ifc of current) {
    const next = config.interfaces.find((i) => i.name === ifc.name);
    if (!next) continue;
    const currentAddr = ifc.live_ipv4[0]?.split('/')[0];
    if (!currentAddr || currentAddr !== browserHost) continue;
    const nextAddr = next.mode === 'static' ? next.address?.split('/')[0] ?? null : null;
    if (next.mode === 'static' && nextAddr && nextAddr !== currentAddr) {
      warnings.push(`Diqqat: siz ulangan manzil oʻzgaradi. ${timeoutS} soniya ichida http://${nextAddr}/ orqali kirib tasdiqlang, aks holda eski holatga qaytariladi.`);
    } else if (next.mode === 'dhcp') {
      warnings.push(`Diqqat: siz ulangan interfeys DHCPga oʻtadi, yangi manzil oldindan maʼlum emas. ${timeoutS} soniya ichida tasdiqlashni unutmang.`);
    }
  }
  return warnings;
}
