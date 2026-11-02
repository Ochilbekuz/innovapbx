// IVR tekshiruvlari — sof, API'dan mustaqil. `fake.ts`/`real.ts`'ning server xatolarini simulyatsiya qilishi
// uchun ishlatiladi: 422 `duplicate_digit`, 422 `loop` (qarang ../../replica/m1a-contract.md).

export type IvrOption = { digit: string; targetId: string };

/** Bitta tugma ikki marta ishlatilsa — birinchi takrorlangan raqamni qaytaradi, aks holda null.
 * Faqat `digit` kerak — API kirish shakli (`target_id`) va domen shakli (`targetId`) ikkisi ham mos keladi. */
export function findDuplicateDigit(options: readonly { digit: string }[]): string | null {
  const seen = new Set<string>();
  for (const o of options) {
    if (seen.has(o.digit)) return o.digit;
    seen.add(o.digit);
  }
  return null;
}

export type IvrEdgeRef = { kind: string; id: string };
export type IvrEdges = { timeout: IvrEdgeRef | null; invalid: IvrEdgeRef | null };
export type IvrEdgeLookup = (ivrId: string) => IvrEdges | null;

const LOOP_EDGES = ['timeout', 'invalid'] as const;
export type LoopEdge = (typeof LOOP_EDGES)[number];
export type IvrLoop = { edge: LoopEdge; path: string[] };

/**
 * IVR → ... → IVR halqasini faqat `timeout`/`invalid` yo'lida qidiradi (shartnoma: tugma orqali o'z-o'ziga
 * qaytish — qo'ng'iroq qiluvchi tanlagani uchun ruxsat, bu yerda tekshirilmaydi). Chiqish (IVR bo'lmagan
 * manzil yoki yo'q edge) topilsa — halqa yo'q. Oldin ko'rilgan IVR'ga qaytsa — halqa, yo'l (id'lar) bilan.
 */
export function findIvrLoop(startId: string, lookup: IvrEdgeLookup): IvrLoop | null {
  for (const edge of LOOP_EDGES) {
    const path = [startId];
    const visited = new Set([startId]);
    let currentId = startId;
    for (;;) {
      const next = lookup(currentId)?.[edge] ?? null;
      if (!next || next.kind !== 'ivr') break;
      if (visited.has(next.id)) return { edge, path: [...path, next.id] };
      visited.add(next.id);
      path.push(next.id);
      currentId = next.id;
    }
  }
  return null;
}
