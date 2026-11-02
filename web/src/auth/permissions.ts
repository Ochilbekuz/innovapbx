import { useSession } from '@/api/session';
import type { Hudud } from '@/shell/screens';

const ALL = '*';

/**
 * Ro'yxatda aniq ruxsat BO'LMASA ham, "*" ("hammasi" — backend `admin` roli uchun shu tarzda
 * qaytaradi, qarang `api/app/core/permissions.py: ROLE_PERMISSIONS["admin"] = [ALL]`) bo'lsa — true.
 *
 * DIQQAT (haqiqiy backend bilan Playwright tekshiruvida topilgan haqiqiy xato): avval faqat
 * `.includes(perm)` ishlatilgan edi — bu `fake` klientdagi test ma'lumotlari ('pbx.manage' kabi
 * aniq satrlar ro'yxati) bilan ishlagan, lekin HAQIQIY backend admin uchun `["*"]` qaytaradi va
 * aniq satr hech qachon mos kelmasdi — natijada admin foydalanuvchi UIda "faqat ko'rish" rejimida
 * qolib ketgan edi (boshqarish tugmalari butunlay yashirin), garchi serverda to'liq ruxsati
 * bo'lsa ham.
 */
export function hasPermission(permissions: string[] | undefined, perm: string): boolean {
  if (!permissions) return false;
  return permissions.includes(ALL) || permissions.includes(perm);
}

/** Joriy foydalanuvchida berilgan ruxsat bor-yoʻqligi. Faqat UI uchun — server baribir oʻzi tekshiradi (403). */
export function usePermission(perm: string): boolean {
  return useSession((s) => hasPermission(s.user?.permissions, perm));
}

/** M7 §1: `<hudud>:edit` (yoki `*`) bo'lsa tahrirlash mumkin. */
export function canEditHudud(permissions: string[] | undefined, hudud: Hudud): boolean {
  return hasPermission(permissions, `${hudud}:edit`);
}

/** M7 §1: `<hudud>:view` YOKI `:edit` (edit ⇒ view) bo'lsa ko'rish mumkin. */
export function canViewHudud(permissions: string[] | undefined, hudud: Hudud): boolean {
  return hasPermission(permissions, `${hudud}:view`) || hasPermission(permissions, `${hudud}:edit`);
}

/**
 * Hudud sahifalarida «Yangi …»/tahrir/o'chirish tugmalarini ko'rsatish-yoʻq qilish uchun markaziy hook
 * (M7 §4). `*` ham edit hisoblanadi (`hasPermission` ichida).
 */
export function useCanEdit(hudud: Hudud): boolean {
  return useSession((s) => canEditHudud(s.user?.permissions, hudud));
}

/** Hudud ma'lumotini o'qish mumkinmi (masalan bosh sahifadagi park vidjeti `apps:view` talab qiladi). */
export function useCanView(hudud: Hudud): boolean {
  return useSession((s) => canViewHudud(s.user?.permissions, hudud));
}
