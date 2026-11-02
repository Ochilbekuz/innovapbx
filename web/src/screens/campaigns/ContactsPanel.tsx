import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronLeft, ChevronRight, Download, Search } from 'lucide-react';
import { apiClient } from '@/api';
import { apiErrorMessage } from '@/api/errors';
import { useCampaignContacts } from '@/api/queries';
import { CAMPAIGN_CONTACT_STATUSES, type Campaign, type CampaignContact, type CampaignContactStatus } from '@/api/types';
import { formatDateTimeShort } from '@/lib/time';
import { Button } from '@/ui/Button';
import { Input, Select } from '@/ui/Field';
import { Badge, type Tone } from '@/ui/Status';
import { useToast } from '@/ui/Toast';

const PAGE_SIZE = 25;
const ALL = 'all';

export const CONTACT_TONE: Record<CampaignContactStatus, Tone> = {
  pending: 'neutral', dialing: 'accent', retry: 'warning', done: 'success', failed: 'danger', skipped: 'neutral',
};

async function downloadCsv(campaign: Campaign) {
  const blob = await apiClient.exportCampaignCsv(campaign.id);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `campaign-${campaign.id}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

type T = (key: string, opts?: Record<string, unknown>) => string;

/** Qator ostidagi izoh: natija · bosilgan tugma · davomiylik · urinishlar (bo'shlari tushib qoladi). */
export function contactDetails(c: CampaignContact, t: T): string {
  return [
    c.result && t(`result.${c.result}`, { defaultValue: c.result }),
    c.key && t('detail.pressed', { key: c.key }),
    c.billsec && t('detail.billsec', { sec: c.billsec }),
    c.attempts > 0 && t('detail.attempts', { count: c.attempts }),
  ].filter(Boolean).join(' · ');
}

function ContactRow({ c }: { c: CampaignContact }) {
  const { t } = useTranslation('campaigns');
  const details = contactDetails(c, t);
  const nextAt = c.status === 'retry' ? c.next_attempt_at : null;
  return (
    <li className="flex items-center gap-3 px-3 py-2">
      <div className="min-w-0 flex-1">
        <p className="flex items-baseline gap-2">
          <span className="num text-sm text-fg">{c.number}</span>
          {c.name && <span className="truncate text-sm text-muted">{c.name}</span>}
        </p>
        {details && <p className="truncate text-xs text-muted">{details}</p>}
        {nextAt && <p className="text-xs text-muted">{t('detail.nextAttempt', { at: formatDateTimeShort(nextAt) })}</p>}
      </div>
      <Badge tone={CONTACT_TONE[c.status]}>{t(`contactStatus.${c.status}`)}</Badge>
    </li>
  );
}

function Pager({ page, total, onPage }: { page: number; total: number; onPage: (p: number) => void }) {
  const { t } = useTranslation('campaigns');
  if (total <= PAGE_SIZE) return null;
  const from = (page - 1) * PAGE_SIZE + 1;
  const to = Math.min(page * PAGE_SIZE, total);
  return (
    <div className="flex items-center justify-end gap-1">
      <span className="num mr-2 text-xs text-muted">{t('detail.pageOf', { from, to, total })}</span>
      <Button size="sm" variant="ghost" iconOnly icon={<ChevronLeft />} aria-label={t('detail.prev')} disabled={page === 1} onClick={() => onPage(page - 1)} />
      <Button size="sm" variant="ghost" iconOnly icon={<ChevronRight />} aria-label={t('detail.next')} disabled={to >= total} onClick={() => onPage(page + 1)} />
    </div>
  );
}

/** Kontaktlar: holat filtri, qidiruv, sahifalash (server tomonida), CSV eksport. */
export function ContactsPanel({ campaign }: { campaign: Campaign }) {
  const { t } = useTranslation('campaigns');
  const toast = useToast();
  const [status, setStatus] = useState<CampaignContactStatus | typeof ALL>(ALL);
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const params = { status: status === ALL ? undefined : status, q: q.trim() || undefined, page, page_size: PAGE_SIZE };
  const { data, isLoading } = useCampaignContacts(campaign.id, params, campaign.status === 'running');
  const total = data?.total ?? 0;

  return (
    <section className="flex flex-col gap-2.5" aria-labelledby="campaign-contacts-title">
      <div className="flex items-center justify-between gap-3">
        <h3 id="campaign-contacts-title" className="text-sm font-semibold text-fg">{t('detail.contactsTitle')}</h3>
        <Button
          size="sm" variant="ghost" icon={<Download />} disabled={campaign.stats.total === 0}
          onClick={() => void downloadCsv(campaign).catch((e) => toast({ kind: 'error', title: t('toast.exportFailed'), description: apiErrorMessage(e) }))}
        >
          {t('detail.export')}
        </Button>
      </div>
      <div className="grid grid-cols-[1fr_auto] gap-2">
        <Input
          size="sm" leading={<Search aria-hidden />} aria-label={t('detail.searchPlaceholder')} placeholder={t('detail.searchPlaceholder')}
          value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }}
        />
        <Select
          size="sm" aria-label={t('detail.filterLabel')} value={status}
          onValueChange={(v) => { setStatus(v as CampaignContactStatus | typeof ALL); setPage(1); }}
          options={[{ value: ALL, label: t('detail.filterAll') }, ...CAMPAIGN_CONTACT_STATUSES.map((s) => ({ value: s, label: t(`contactStatus.${s}`) }))]}
        />
      </div>
      <div className="rounded-md border border-line bg-surface">
        {!isLoading && total === 0 ? (
          <p className="px-3 py-6 text-center text-sm text-muted">{t('detail.contactsEmpty')}</p>
        ) : (
          <ul className="divide-y divide-line" aria-busy={isLoading}>
            {(data?.items ?? []).map((c) => <ContactRow key={c.id} c={c} />)}
          </ul>
        )}
      </div>
      <Pager page={page} total={total} onPage={setPage} />
    </section>
  );
}
