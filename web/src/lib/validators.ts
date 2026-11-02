// Umumiy validatorlar — Setup (S01) va Trunk (S06) formalarida tarmoq maydonlari uchun bir xil qoida.

export const CIDR_RE = /^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\/(\d{1,2})$/;
export const IPV4_RE = /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/;
const HOSTNAME_RE = /^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$/i;

export const isValidIPv4 = (v: string) => IPV4_RE.test(v) && v.split('.').every((o) => Number(o) <= 255);
export const isValidCidr = (v: string) => {
  const m = CIDR_RE.exec(v);
  return !!m && isValidIPv4(m[1] ?? '') && Number(m[2]) <= 32;
};
export const isValidHost = (v: string) => isValidIPv4(v) || HOSTNAME_RE.test(v);

/** Vergul/qator bilan ajratilgan roʻyxatni satrlarga ajratadi, boʻsh qatorlarni olib tashlaydi. */
export function splitList(raw: string): string[] {
  return raw.split(/[\n,]/).map((s) => s.trim()).filter(Boolean);
}
