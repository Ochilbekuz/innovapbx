import { useSession } from '@/api/session';

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
