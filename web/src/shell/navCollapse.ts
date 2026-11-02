/**
 * Sidebar guruhlarining yig'ilgan/ochiq holatini saqlash (M8 §6). Faqat guruh id'lari — kontent
 * emas, shu uchun versiyalar orasida eskirib qolmaydi.
 */
const KEY = 'innova.nav.collapsed';

/** Buzilgan/yo'q qiymat — xavfsiz bo'sh ro'yxat (hammasi ochiq) qaytaradi. */
export function loadCollapsedGroups(): string[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((g): g is string => typeof g === 'string') : [];
  } catch {
    return [];
  }
}

/** Xususiy rejim/kvota tolasa ham UI ishlashda davom etadi — holat shu sessiyada xotirada qoladi. */
export function saveCollapsedGroups(groups: string[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(groups));
  } catch {
    // Saqlab bo'lmadi — jim o'tamiz.
  }
}
