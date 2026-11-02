// Formalar oʻrtasida ulashiladigan kichik sof yordamchi funksiyalar — JSX ichidagi `?:`/`&&`/`??`
// shoxlaridan chiqarish CRAP'ni tushiradi (crapper nested callback'larni enclosing komponentga qoʻshadi).

/** Berilgan maydonga tegishli xatoni qaytaradi — aks holda `undefined` (xato boshqa maydonda yoki yoʻq). */
export function fieldError(errorField: string | undefined, field: string, message: string | undefined): string | undefined {
  return errorField === field ? message : undefined;
}

/** Berilgan roʻyxatdagi maydonlarga tegishli boʻlmagan qolgan mutatsiya xatosi — ular allaqachon
 * oʻz joyida koʻrsatiladi; `stale` holatida umumiy banner yetarli, bu yerda hech nima chiqmaydi. */
export function otherFieldError(
  errorMessage: string | undefined, stale: boolean, errorField: string | undefined, knownFields: string[],
): string | null {
  if (!errorMessage || stale) return null;
  return knownFields.includes(errorField ?? '') ? null : errorMessage;
}

/** Radix `Dialog.onOpenChange` — faqat yopilayotganda (`open` false boʻlsa) `close()` chaqiradi. */
export function closeOnOpenChange(open: boolean, close: () => void): void {
  if (!open) close();
}

/** `{ items: T[] } | undefined` dan xavfsiz roʻyxat olish — soʻrov hali yuklanmagan boʻlsa boʻsh massiv. */
export function itemsOrEmpty<T>(data: { items: T[] } | undefined): T[] {
  return data?.items ?? [];
}
