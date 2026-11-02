// 1.0.4 — brauzer `getUserMedia` (mikrofon) FAQAT "xavfsiz kontekst"da ishlaydi: https:,
// yoki `localhost`/`127.0.0.1`/`::1` (bular http:// bo'lsa ham xavfsiz hisoblanadi — brauzer
// qoidasi). Softfon shu holatni aniqlab, HTTPS'ga o'tish ogohlantirishini ko'rsatadi (IdleScreen).

/** Faqat test uchun — haqiqiy chaqiruv `isPageInsecure()` orqali `window.location`ni ishlatadi. */
export function isInsecureLocation(location: { protocol: string; hostname: string }): boolean {
  if (location.protocol === 'https:') return false;
  const host = location.hostname;
  return host !== 'localhost' && host !== '127.0.0.1' && host !== '::1';
}

export function isPageInsecure(): boolean {
  if (typeof window === 'undefined') return false;
  return isInsecureLocation(window.location);
}
