import { useTranslation } from 'react-i18next';
import { Download, FileCode } from 'lucide-react';
import { apiClient } from '@/api';
import { useOneCSamples } from '@/api/queries';
import type { OneCSample } from '@/api/types';
import { Button } from '@/ui/Button';

async function downloadSample(sample: OneCSample) {
  const blob = await apiClient.fetchOneCSample(sample.name);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = sample.name;
  a.click();
  URL.revokeObjectURL(url);
}

/** M3b — 1C uchun tayyor BSL namunalar: koʻrsatma + yuklab olish roʻyxati. Alohida server kerak emas. */
export function OneCTab() {
  const { t } = useTranslation('integrations');
  const { data, isLoading, isError } = useOneCSamples();

  return (
    <section className="flex max-w-2xl flex-col gap-4">
      <h3 className="font-display text-base font-semibold">{t('onec.title')}</h3>
      <p className="text-sm text-muted">{t('onec.desc')}</p>
      <p className="whitespace-pre-line rounded-md border border-line bg-surface-2/60 px-3 py-2.5 text-sm text-fg">{t('onec.instructions')}</p>

      <div>
        <h4 className="mb-2 text-sm font-medium text-fg">{t('onec.downloads')}</h4>
        {isLoading ? (
          <p className="text-sm text-muted">…</p>
        ) : isError || !data || data.items.length === 0 ? (
          <p className="text-sm text-muted">{t('onec.empty')}</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {data.items.map((s) => (
              <li key={s.name} className="flex items-center justify-between gap-2 rounded-md border border-line bg-surface px-3 py-2 shadow-card">
                <span className="flex items-center gap-2 text-sm"><FileCode aria-hidden className="size-4 text-muted" />{s.title}</span>
                <Button size="sm" variant="ghost" icon={<Download />} onClick={() => void downloadSample(s)}>{t('onec.download')}</Button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <p className="text-xs text-muted">{t('onec.reviewNote')}</p>
    </section>
  );
}
