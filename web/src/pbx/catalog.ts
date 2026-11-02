// API Target[] → domain Catalog. Generic — DestinationPicker/CallFlow bir xil shakl bilan ishlaydi.
import type { Target as ApiTarget } from '@/api/types';
import type { Catalog } from '@/domain/destination';

/** Buzilgan (`broken: true`) nishonlar katalogga qo'shilmaydi — havola qilinganda domen qatlami
 * buni avtomatik "broken" deb aniqlaydi (topilmadi), alohida belgi kerak emas. */
export function toCatalog(items: readonly ApiTarget[]): Catalog {
  const catalog: Record<string, Catalog[string]> = {};
  for (const t of items) {
    if (t.broken) continue;
    catalog[t.id] = { id: t.id, kind: t.kind, name: t.label, number: t.number ?? undefined };
  }
  return catalog;
}
