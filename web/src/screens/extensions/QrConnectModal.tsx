import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import QRCode from 'qrcode';
import { Copy, RefreshCw, ShieldCheck } from 'lucide-react';
import { useCreateQrProvisioning } from '@/api/queries';
import { apiErrorMessage, isApiError } from '@/api/errors';
import type { FollowMeTarget, QrProvisioning, SipTransport } from '@/api/types';
import { usePermission } from '@/auth/permissions';
import { cn } from '@/lib/cn';
import { Button } from '@/ui/Button';
import { Modal } from '@/ui/Dialog';
import { Badge } from '@/ui/Status';
import { useToast } from '@/ui/Toast';
import { copyText } from '@/lib/browser';

const QR_SIZE = 216;
const TTL_SECONDS = 15 * 60;
const STEPS = ['install', 'open', 'scan'] as const;

/** Muddatgacha qolgan soniya — har soniyada yangilanadi. */
function useSecondsLeft(expiresAt: string | undefined): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!expiresAt) return undefined;
    setNow(Date.now());
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [expiresAt]);
  return expiresAt ? Math.max(0, Math.ceil((Date.parse(expiresAt) - now) / 1000)) : 0;
}

export function formatCountdown(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
}

/** QR brauzerda yasaladi (havola tashqi xizmatga yuborilmaydi); tema qorong'i bo'lsa ham oq fonda — skanerlansin. */
function QrImage({ url, alt, faded }: { url: string; alt: string; faded: boolean }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    QRCode.toDataURL(url, { margin: 1, width: QR_SIZE * 2, errorCorrectionLevel: 'M' })
      .then((data) => { if (alive) setSrc(data); })
      .catch(() => { if (alive) setSrc(null); });
    return () => { alive = false; };
  }, [url]);
  return (
    <div className="rounded-lg border border-line bg-white p-2.5 shadow-card">
      {src
        ? <img src={src} alt={alt} width={QR_SIZE} height={QR_SIZE} data-testid="qr-image" className={cn('block transition duration-base', faded && 'opacity-15 blur-[3px]')} />
        : <div className="skeleton" style={{ width: QR_SIZE, height: QR_SIZE }} />}
    </div>
  );
}

/** M5b §2 — «Telefonga ulash»: bir martalik Linphone havolasi QR ko'rinishida, qolgan vaqt va ko'rsatma bilan. */
export function QrConnectModal({ target, number, open, onOpenChange }: {
  target: FollowMeTarget;
  number: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useTranslation('followme');
  const toast = useToast();
  const { mutate, reset, data, error, isPending } = useCreateQrProvisioning(target);
  const left = useSecondsLeft(data?.expires_at);
  const live = !!data && left > 0;

  // Ochilganda token olinadi; yopilganda havola xotiradan o'chiriladi.
  useEffect(() => { if (open) mutate(); else reset(); }, [open, mutate, reset]);

  const copy = (url: string) => void copyText(url).then((ok) => ok && toast({ kind: 'success', title: t('qr.copied') }));

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={t('qr.title', { number })}
      description={t('qr.description')}
      footer={
        <>
          {live && <Button variant="ghost" icon={<Copy />} onClick={() => copy(data.url)}>{t('qr.copy')}</Button>}
          <Button variant="secondary" icon={<RefreshCw />} loading={isPending} data-testid="qr-refresh" onClick={() => mutate()}>{t('qr.refresh')}</Button>
          <Button variant="primary" onClick={() => onOpenChange(false)}>{t('qr.close')}</Button>
        </>
      }
    >
      {error ? <QrError error={error} /> : (
        <div className="grid items-start gap-5 sm:grid-cols-[auto_1fr]">
          <QrPreview qr={data} left={left} number={number} />
          <QrSteps transport={data?.transport} />
        </div>
      )}
    </Modal>
  );
}

function QrError({ error }: { error: unknown }) {
  const { t } = useTranslation('followme');
  const canSettings = usePermission('system.manage');
  const needsHost = isApiError(error) && error.code === 'public_host_not_configured';
  return (
    <div className="flex flex-col gap-3 rounded-md border border-danger/30 bg-danger-soft px-3 py-3 text-sm text-on-danger-soft" role="alert" data-testid="qr-error">
      <p>{apiErrorMessage(error)}</p>
      {needsHost && canSettings && (
        <Link to="/settings/integrations" className="self-start font-medium underline underline-offset-2">{t('qr.openSettings')}</Link>
      )}
    </div>
  );
}

/** QR + qolgan vaqt; muddat tugasa QR xiralashadi va ustida «yangi QR oling» chiqadi. */
function QrPreview({ qr, left, number }: { qr: QrProvisioning | undefined; left: number; number: string }) {
  const { t } = useTranslation('followme');
  if (!qr) return <div className="skeleton rounded-lg" style={{ width: QR_SIZE + 22, height: QR_SIZE + 22 }} />;
  const expired = left === 0;
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative">
        <QrImage url={qr.url} alt={t('qr.imageAlt', { number })} faded={expired} />
        {expired && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 px-4 text-center">
            <p className="font-display text-base text-fg">{t('qr.expired')}</p>
            <p className="text-xs text-muted">{t('qr.expiredBody')}</p>
          </div>
        )}
      </div>
      {!expired && (
        <div className="flex w-full flex-col gap-1.5">
          <div className="h-1 overflow-hidden rounded-pill bg-surface-2">
            <div className="h-full rounded-pill bg-accent transition-[width] duration-base ease-linear" style={{ width: `${(left / TTL_SECONDS) * 100}%` }} />
          </div>
          <p className="num text-center text-xs text-muted" data-testid="qr-countdown">{t('qr.expiresIn', { time: formatCountdown(left) })}</p>
        </div>
      )}
    </div>
  );
}

function QrSteps({ transport }: { transport: SipTransport | undefined }) {
  const { t } = useTranslation('followme');
  return (
    <div className="flex flex-col gap-4">
      <ol className="flex flex-col gap-3">
        {STEPS.map((step, i) => (
          <li key={step} className="flex items-start gap-2.5">
            <span className="num flex size-6 shrink-0 items-center justify-center rounded-pill bg-accent-soft text-xs font-medium text-on-accent-soft">{i + 1}</span>
            <span className="pt-0.5 text-sm text-fg">{t(`qr.steps.${step}`)}</span>
          </li>
        ))}
      </ol>
      <p className="flex items-start gap-1.5 text-xs text-muted">
        <ShieldCheck aria-hidden className="mt-px size-3.5 shrink-0 text-success" />
        {t('qr.oneTime')}
      </p>
      {transport && <Badge tone="neutral" className="self-start">{t('qr.transport', { transport: transport.toUpperCase() })}</Badge>}
    </div>
  );
}
