// Manzil (destination) — FreePBX'ning markaziy tushunchasi, bizda tiplangan.
// Kind satrlari backend shartnomasiga mos (snake_case) — qarang ../../replica/m1a-contract.md.
// Faqat tashqi raqam (external) obyektga bog'lanmaydi; qolgan barcha turlar katalogdagi obyektga id orqali bog'lanadi.

export const TARGET_KINDS = [
  'extension',
  'ring_group',
  'queue',
  'ivr',
  'time_condition',
  'conference',
  'hangup',
  'busy',
  'voicemail',
  'announcement',
  'misc',
] as const;
export type TargetKind = (typeof TARGET_KINDS)[number];
export type DestKind = TargetKind | 'external';

export type Destination =
  | { kind: 'external'; number: string }
  | { kind: TargetKind; targetId: string };

export type FlowEdge = { label: string; dest: Destination };

export type Target = {
  id: string;
  kind: TargetKind;
  name: string;
  number?: string;
  /** Oqim grafigi uchun chiquvchi tarmoqlar (IVR tugmalari, ish vaqti mos/mos emas, navbat failover...). */
  next?: FlowEdge[];
};

export type Catalog = Readonly<Record<string, Target>>;

export type Resolved =
  | { state: 'empty' }
  | { state: 'ok'; kind: DestKind; label: string; number?: string; target?: Target }
  | { state: 'broken'; kind: TargetKind; targetId: string }
  | { state: 'invalid'; kind: 'external'; number: string };

const EXTERNAL = /^\+?\d{3,15}$/;
export const normalizeNumber = (raw: string) => raw.replace(/[\s()-]/g, '');

export function isTargetKind(kind: DestKind): kind is TargetKind {
  return (TARGET_KINDS as readonly string[]).includes(kind);
}

export function resolveDestination(dest: Destination | null, catalog: Catalog): Resolved {
  if (!dest) return { state: 'empty' };
  if (dest.kind === 'external') {
    const number = normalizeNumber(dest.number);
    // label — raqamning o'zi: "kind" nomi (Tashqi raqam/External number/...) KIND_LABEL orqali alohida tarjima qilinadi.
    return EXTERNAL.test(number)
      ? { state: 'ok', kind: 'external', label: number, number }
      : { state: 'invalid', kind: 'external', number: dest.number };
  }
  const target = catalog[dest.targetId];
  if (!target || target.kind !== dest.kind) return { state: 'broken', kind: dest.kind, targetId: dest.targetId };
  return { state: 'ok', kind: target.kind, label: target.name, number: target.number, target };
}

/** Koʻrsatish uchun: +998 XX XXX XX XX. Boshqa raqamlar oʻzgarmaydi (saqlanadigan qiymat — normalizeNumber). */
export function formatNumber(raw: string): string {
  const m = /^\+?998(\d{2})(\d{3})(\d{2})(\d{2})$/.exec(normalizeNumber(raw));
  return m ? `+998 ${m.slice(1).join(' ')}` : raw;
}
