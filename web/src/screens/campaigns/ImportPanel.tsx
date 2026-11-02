import { useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { FileUp, Upload } from 'lucide-react';
import { apiErrorMessage } from '@/api/errors';
import { useImportCampaignContacts } from '@/api/queries';
import type { Campaign, ImportCampaignContactsResult } from '@/api/types';
import { parseContactsCsv, type ParsedCsv } from '@/domain/campaigns';
import { Button } from '@/ui/Button';
import { Textarea } from '@/ui/Field';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

function Preview({ preview }: { preview: ParsedCsv }) {
  const { t } = useTranslation('campaigns');
  return (
    <div className="flex flex-col gap-1 text-sm">
      <p className="num text-fg">{t('detail.preview', { valid: preview.rows.length, duplicates: preview.duplicates, invalid: preview.invalid_count })}</p>
      {preview.invalid.slice(0, 3).map((r) => (
        <p key={r.line} className="num text-danger">{t('detail.previewInvalid', { line: r.line, value: r.value })}</p>
      ))}
    </div>
  );
}

/** Yashirin fayl tanlagich — matnni o'qib qaytaradi. */
function FilePicker({ onText }: { onText: (text: string) => void }) {
  const { t } = useTranslation('campaigns');
  const fileRef = useRef<HTMLInputElement>(null);
  const pick = async (file: File | undefined) => {
    if (file) onText(await file.text());
  };
  return (
    <>
      <Button size="sm" variant="ghost" icon={<FileUp />} onClick={() => fileRef.current?.click()}>{t('detail.importFile')}</Button>
      <input ref={fileRef} type="file" accept=".csv,.txt,text/csv,text/plain" className="sr-only" tabIndex={-1} onChange={(e) => void pick(e.target.files?.[0])} />
    </>
  );
}

function ReplaceToggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  const { t } = useTranslation('campaigns');
  return <Toggle checked={checked} onCheckedChange={onChange} label={t('detail.importReplace')} description={checked ? t('detail.importReplaceHint') : undefined} />;
}

function ImportReport({ report }: { report: ImportCampaignContactsResult | null }) {
  const { t } = useTranslation('campaigns');
  if (!report) return null;
  return (
    <p role="status" className="num rounded-md border border-success/25 bg-success-soft px-3 py-2 text-sm text-on-success-soft">
      {t('detail.importDone', { added: report.added, skipped: report.skipped, duplicates: report.duplicates, invalid: report.invalid_count })}
    </p>
  );
}

/** CSV matni yoki fayl → oldindan ko'rish (brauzerda, backend bilan bir xil qoida) → yuklash. */
export function ImportPanel({ campaign }: { campaign: Campaign }) {
  const { t } = useTranslation('campaigns');
  const toast = useToast();
  const [csv, setCsv] = useState('');
  const [replace, setReplace] = useState(false);
  const [report, setReport] = useState<ImportCampaignContactsResult | null>(null);
  const importM = useImportCampaignContacts();
  const preview = useMemo(() => (csv.trim() ? parseContactsCsv(csv) : null), [csv]);
  const running = campaign.status === 'running';

  const submit = () => importM.mutate({ id: campaign.id, payload: { csv, replace: replace && !running } }, {
    onSuccess: (res) => { setReport(res); setCsv(''); setReplace(false); toast({ kind: 'success', title: t('toast.imported') }); },
    onError: (e) => toast({ kind: 'error', title: t('toast.failed'), description: apiErrorMessage(e) }),
  });

  return (
    <section className="flex flex-col gap-2.5" aria-labelledby="campaign-import-title">
      <div className="flex items-baseline justify-between gap-3">
        <h3 id="campaign-import-title" className="text-sm font-semibold text-fg">{t('detail.importTitle')}</h3>
        <FilePicker onText={setCsv} />
      </div>
      <p className="text-sm text-muted">{t('detail.importHint')}</p>
      <Textarea
        aria-label={t('detail.importTitle')} className="num min-h-28 text-sm" spellCheck={false}
        placeholder={t('detail.importPlaceholder')} value={csv} onChange={(e) => setCsv(e.target.value)}
      />
      {preview && <Preview preview={preview} />}
      <div className="flex flex-wrap items-center justify-between gap-3">
        {!running && <ReplaceToggle checked={replace} onChange={setReplace} />}
        <Button size="sm" variant="primary" icon={<Upload />} className="ml-auto" loading={importM.isPending} disabled={!preview?.rows.length} onClick={submit}>
          {t('detail.importButton')}
        </Button>
      </div>
      <ImportReport report={report} />
    </section>
  );
}
