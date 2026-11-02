// TLS sertifikat muddati — SipPage'dagi TLS kartasi uchun (../../replica/m1c-contract.md §3).

const WARNING_DAYS = 30;

/** `not_after`gacha qolgan to'liq kunlar (manfiy — muddati o'tgan). */
export function daysUntil(notAfter: string, now: Date = new Date()): number {
  return Math.ceil((new Date(notAfter).getTime() - now.getTime()) / 86_400_000);
}

/** Muddati tugagan bo'lsa `false` qaytaradi — bu holat alohida (`isExpired`) ko'rsatiladi. */
export function isExpiringSoon(notAfter: string, now: Date = new Date()): boolean {
  const days = daysUntil(notAfter, now);
  return days >= 0 && days < WARNING_DAYS;
}

export function isExpired(notAfter: string, now: Date = new Date()): boolean {
  return daysUntil(notAfter, now) < 0;
}
