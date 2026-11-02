// IPv4/CIDR yordamchilari — S33 xavfsizlik sahifasi (ishonchli tarmoqlar, qo'lda bloklash). Sof funksiyalar — fake.ts va testlar ishlatadi.

function ipToInt(ip: string): number {
  const parts = ip.split('.').map(Number);
  return ((parts[0]! << 24) | (parts[1]! << 16) | (parts[2]! << 8) | parts[3]!) >>> 0;
}

/** `ip` berilgan `cidr` ichida tursa — true. Noto'g'ri CIDR — false (chaqiruvchi oldindan isValidCidr bilan tekshirsin). */
export function ipInCidr(ip: string, cidr: string): boolean {
  const slash = cidr.indexOf('/');
  if (slash < 0) return false;
  const base = cidr.slice(0, slash);
  const bits = Number(cidr.slice(slash + 1));
  if (!Number.isFinite(bits) || bits < 0 || bits > 32) return false;
  if (bits === 0) return true;
  const mask = bits === 32 ? 0xffffffff : (0xffffffff << (32 - bits)) >>> 0;
  return (ipToInt(ip) & mask) === (ipToInt(base) & mask);
}

/** 127.0.0.0/8 har doim ishonchli (m2c-contract.md §0) — `trustedNets` bo'sh bo'lsa ham avtomatik bloklanmaydi. */
export function isTrustedIp(ip: string, trustedNets: readonly string[]): boolean {
  return ipInCidr(ip, '127.0.0.0/8') || trustedNets.some((net) => ipInCidr(ip, net));
}
