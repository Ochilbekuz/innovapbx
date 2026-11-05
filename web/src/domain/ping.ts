/**
 * «Ping» tabi — sof yordamchilar. Host qoidasi backend bilan bir xil
 * (`api/app/netd/executor.py::ping_host_kind`): IPv4/IPv6 (zona `%`siz) yoki
 * domen nomi; boshida `-` yoki bo'sh joy — yo'q.
 */
export type PingPresetKind = 'gateway' | 'sip' | 'internet' | 'dns';
export type PingPreset = { kind: PingPresetKind; host: string; name?: string };

export const PING_COUNT_MIN = 1;
export const PING_COUNT_MAX = 10;
export const PING_COUNT_DEFAULT = 4;

const NAME_RE = /^[A-Za-z0-9]([A-Za-z0-9-]{0,62})(\.[A-Za-z0-9-]{1,63})*$/;
const IPV4_RE = /^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$/;
const IPV6_RE = /^[0-9A-Fa-f:.]+$/;

function isIpv6(host: string): boolean {
  if (!host.includes(':') || !IPV6_RE.test(host)) return false;
  try {
    new URL(`http://[${host}]/`);
    return true;
  } catch {
    return false;
  }
}

export function isValidPingHost(raw: string): boolean {
  const host = raw.trim();
  if (IPV4_RE.test(host) || isIpv6(host)) return true;
  return host.length <= 253 && NAME_RE.test(host);
}

const FIXED_PRESETS: PingPreset[] = [
  { kind: 'internet', host: '1.1.1.1' },
  { kind: 'internet', host: '8.8.8.8' },
  { kind: 'dns', host: 'google.com' },
];

/** Shlyuz -> SIP trunk hostlari (takrorsiz, yaroqlilari) -> internet -> DNS nomi. */
export function buildPingPresets(gateway: string | null, trunks: ReadonlyArray<{ name: string; host: string }>): PingPreset[] {
  const presets: PingPreset[] = gateway ? [{ kind: 'gateway', host: gateway }] : [];
  const seen = new Set<string>();
  for (const trunk of trunks) {
    if (seen.has(trunk.host) || !isValidPingHost(trunk.host)) continue;
    seen.add(trunk.host);
    presets.push({ kind: 'sip', host: trunk.host, name: trunk.name });
  }
  return [...presets, ...FIXED_PRESETS];
}
