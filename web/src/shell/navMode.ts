/**
 * Yon menyu holati (desktop):
 *  - «pinned» (qotirilgan, sukut) — to'liq kenglik, kontentni suradi;
 *  - «rail» (yig'ilgan) — faqat ikonalar; sichqoncha/fokus kelsa kontent ustida vaqtincha ochiladi.
 * Faqat rejim saqlanadi; guruhlar akkordeoni har sahifada faol guruhdan boshlanadi (eski
 * `innova.nav.collapsed` kaliti endi o'qilmaydi).
 */
import type { ScreenGroupId } from './screens';

export type NavMode = 'pinned' | 'rail';

const KEY = 'innova.nav.mode';

/** Tashqi qiymatni (localStorage) bir marta, kirishda tekshiradi — noma'lum narsa «pinned». */
export function parseNavMode(raw: string | null): NavMode {
  return raw === 'rail' ? 'rail' : 'pinned';
}

export function loadNavMode(): NavMode {
  try {
    return parseNavMode(localStorage.getItem(KEY));
  } catch {
    return 'pinned';
  }
}

/** Xususiy rejim/kvota tolasa ham UI ishlashda davom etadi — holat shu sessiyada xotirada qoladi. */
export function saveNavMode(mode: NavMode): void {
  try {
    localStorage.setItem(KEY, mode);
  } catch {
    // Saqlab bo'lmadi — jim o'tamiz.
  }
}

/** Akkordeon: bosilgan guruh ochiladi (boshqasi yopiladi); allaqachon ochiq bo'lsa — yopiladi. */
export function accordionNext(open: ScreenGroupId | null, clicked: ScreenGroupId): ScreenGroupId | null {
  return open === clicked ? null : clicked;
}

function isTextEntry(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false;
  return target.closest('input, textarea, select, [contenteditable=""], [contenteditable="true"]') !== null;
}

/** Ctrl+B / ⌘B (klaviatura tartibidan qat'i nazar — `code`), matn kiritilayotgan joyda emas. */
export function isNavToggleShortcut(e: KeyboardEvent): boolean {
  const isB = e.code === 'KeyB' || e.key.toLowerCase() === 'b';
  const mod = (e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey;
  return isB && mod && !isTextEntry(e.target);
}
