// Pending banner uchun mahalliy sanoq — qasddan QrConnectModal'dan import qilinmaydi (dryer: scope boshqa,
// bu yerda faqat `expires_at` ISO satrini kuzatish kerak).
import { useEffect, useState } from 'react';

/** `expiresAt` ga qolgan soniyalar — har soniyada yangilanadi. `undefined` bo'lsa 0. */
export function useSecondsLeft(expiresAt: string | undefined): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!expiresAt) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [expiresAt]);
  if (!expiresAt) return 0;
  return Math.max(0, Math.ceil((Date.parse(expiresAt) - now) / 1000));
}

export function formatCountdown(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}
