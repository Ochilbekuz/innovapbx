// S19 — /settings/license: Bitrix24 OAuth litsenziyasining to'liq holati (sinov/faol/imtiyoz/tugagan/
// bloklangan, sanalar, tariflar). Qisqa belgi CrmTab'da (`crm.bitrix24.oauth.license.*`), bu — to'liq
// karta. Qarang bitrix-oauth-shartnoma.md §1 ("litsenziya" obyekti) va `domain/crm.ts` (umumiy mantiq).
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { BadgeCheck } from 'lucide-react';
import { useBitrix24License } from '@/api/queries';
import type { Bitrix24License } from '@/api/types';
import { BITRIX_LICENSE_TONE } from '@/screens/integrations/CrmTab';
import { bitrix24LicenseStateArgs } from '@/domain/crm';
import { formatDateShort } from '@/lib/time';
import { AppShellPage } from '@/shell/AppShellPage';
import { Badge } from '@/ui/Status';
import { Button } from '@/ui/Button';

/** `sinov_tugash` sinov boshlanishidan 14 kun keyin — shu yerdan orqaga hisoblab boshlanish sanasini topamiz (API alohida bermaydi). */
function addDaysBack(license: Bitrix24License): string {
  const d = new Date(`${license.sinov_tugash}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - 14);
  return d.toISOString().slice(0, 10);
}

/**
 * `license:card.state.*` kalitlari bilan holat belgisi matni. `crm.bitrix24.oauth.license.*`
 * (CrmTab'dagi `bitrix24LicenseLabel`) `integrations` nomfazosiga tegishli — bu yerda ALMASHTIRILMAYDI,
 * chunki shu sahifaning `t`'si `license` nomfazosiga bog'langan.
 */
function licenseStateLabel(t: (key: string, opts?: Record<string, unknown>) => string, license: Bitrix24License): string {
  const a = bitrix24LicenseStateArgs(license);
  if (a.state === 'sinov') return t('card.state.sinov', { days: a.days });
  if (a.state === 'faol') return t('card.state.faol', { date: formatDateShort(a.date!) });
  return t(`card.state.${a.state}`);
}

function LicenseCard({ license }: { license: Bitrix24License }) {
  const { t } = useTranslation('license');
  const a = bitrix24LicenseStateArgs(license);
  return (
    <div data-testid="license-card" className="flex flex-col gap-4 rounded-lg border border-line bg-surface p-5 shadow-card">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h2 className="font-display text-lg font-semibold">{t('card.title')}</h2>
          <p className="text-sm text-muted">{t('card.domain', { domain: license.domain })}</p>
        </div>
        <Badge tone={BITRIX_LICENSE_TONE[license.holat]}>{licenseStateLabel(t, license)}</Badge>
      </div>

      <ul className="flex flex-col gap-1 text-sm text-muted">
        <li>{t('card.trialStarted', { date: formatDateShort(addDaysBack(license)) })}</li>
        <li>{t('card.trialEndsAt', { date: formatDateShort(license.sinov_tugash) })}</li>
        <li>{license.tolov_tugash ? t('card.paidUntil', { date: formatDateShort(license.tolov_tugash) }) : t('card.paidNone')}</li>
      </ul>

      <div className="flex flex-col gap-2 border-t border-line pt-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">{t('card.tariffsTitle')}</h3>
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {license.tariflar.map((tarif) => <li key={tarif.kod}>{t(`card.tariff.${tarif.kod}`)}</li>)}
        </ul>
      </div>

      {(a.state === 'imtiyoz' || a.state === 'tugagan' || a.state === 'bloklangan') && (
        <p className="rounded-md border border-warning/30 bg-warning-soft px-3 py-2.5 text-sm text-on-warning-soft">{t('card.contactInnova')}</p>
      )}
    </div>
  );
}

function NotConnectedCard() {
  const { t } = useTranslation('license');
  return (
    <div data-testid="license-not-connected" className="flex flex-col items-start gap-3 rounded-lg border border-dashed border-line bg-surface p-6 text-center sm:items-center">
      <span className="flex size-10 items-center justify-center rounded-md bg-accent-soft text-on-accent-soft"><BadgeCheck aria-hidden className="size-5" /></span>
      <div>
        <h2 className="font-display text-base font-semibold">{t('card.notConnectedTitle')}</h2>
        <p className="mt-0.5 text-sm text-muted">{t('card.notConnectedDesc')}</p>
      </div>
      <Link
        to="/settings/integrations"
        className="inline-flex h-ctl-sm items-center gap-1.5 rounded-md border border-line-strong bg-surface px-2.5 text-sm font-medium shadow-card hover:bg-surface-2 hover:border-input active:translate-y-px"
      >
        {t('card.goToIntegrations')}
      </Link>
    </div>
  );
}

function LicenseLoadError({ onRetry }: { onRetry: () => void }) {
  const { t } = useTranslation('license');
  return (
    <div className="flex flex-col items-center gap-2 rounded-md border border-dashed border-line px-3 py-6 text-center text-sm text-muted">
      <p>{t('card.loadError')}</p>
      <Button size="sm" variant="secondary" onClick={onRetry}>{t('card.retry')}</Button>
    </div>
  );
}

/** Soʻrov holatini bitta tanlovga toʻplaydi — JSX'da shoxlanish (`&&`/ternary) emas, bitta render. */
function LicenseBody({ data, isLoading, isError, onRetry }: {
  data: { connected: boolean; license: Bitrix24License | null } | undefined;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}) {
  if (isLoading) return <div className="skeleton h-48 rounded-lg" />;
  if (isError) return <LicenseLoadError onRetry={onRetry} />;
  if (data?.connected && data.license) return <LicenseCard license={data.license} />;
  return <NotConnectedCard />;
}

/** S19 — faqat admin ko'radi (`screens.ts`, group `system` + `full: true` => fail-closed). */
export function LicensePage() {
  const { t } = useTranslation('license');
  const { data, isLoading, isError, refetch } = useBitrix24License(true);

  return (
    <AppShellPage title={t('title')}>
      <div className="mx-auto flex w-full max-w-xl flex-col gap-4">
        <LicenseBody data={data} isLoading={isLoading} isError={isError} onRetry={() => void refetch()} />
      </div>
    </AppShellPage>
  );
}
