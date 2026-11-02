// Faqat «secure context» (HTTPS/localhost) da bor brauzer API'lari uchun yagona joy.
// Panel odatda http://<LAN-IP>/ da ochiladi: u yerda crypto.randomUUID va navigator.clipboard YO'Q,
// to'g'ridan-to'g'ri chaqiruv render paytida butun sahifani bo'sh qoldiradi.

/** UUID v4 — crypto.getRandomValues har qanday kontekstda mavjud. */
export function newId(): string {
  const b = crypto.getRandomValues(new Uint8Array(16));
  const [b6 = 0, b8 = 0] = [b[6], b[8]];
  b[6] = (b6 & 0x0f) | 0x40; // versiya 4
  b[8] = (b8 & 0x3f) | 0x80; // RFC 4122 varianti
  const h = Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

/** Matnni buferga nusxalaydi; muvaffaqiyatni qaytaradi, hech qachon otmaydi. */
export async function copyText(text: string): Promise<boolean> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // ruxsat berilmadi — eski usulni sinaymiz
    }
  }
  return copyViaTextarea(text);
}

function copyViaTextarea(text: string): boolean {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.setAttribute('readonly', '');
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  try {
    return document.execCommand('copy');
  } catch {
    return false;
  } finally {
    ta.remove();
  }
}
