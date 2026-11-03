import { useEffect, useState } from 'react';
import QRCode from 'qrcode';
import { cn } from '@/lib/cn';

/** QR brauzerda yasaladi (havola tashqi xizmatga yuborilmaydi); tema qorong'i bo'lsa ham oq fonda — skanerlansin. */
export function QrImage({ url, alt, size = 216, faded = false }: { url: string; alt: string; size?: number; faded?: boolean }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    QRCode.toDataURL(url, { margin: 1, width: size * 2, errorCorrectionLevel: 'M' })
      .then((data) => { if (alive) setSrc(data); })
      .catch(() => { if (alive) setSrc(null); });
    return () => { alive = false; };
  }, [url, size]);
  return (
    <div className="rounded-lg border border-line bg-white p-2.5 shadow-card">
      {src
        ? <img src={src} alt={alt} width={size} height={size} data-testid="qr-image" className={cn('block transition duration-base', faded && 'opacity-15 blur-[3px]')} />
        : <div className="skeleton" style={{ width: size, height: size }} />}
    </div>
  );
}
