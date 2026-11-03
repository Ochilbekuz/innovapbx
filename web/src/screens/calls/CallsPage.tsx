import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { daysAgo, formatDateTime, formatDurationSec, isoDate } from '@/lib/time';
import { ArrowLeftRight, Download, PhoneIncoming, PhoneMissed, PhoneOutgoing, ShieldOff, SlidersHorizontal } from 'lucide-react';
import { apiClient } from '@/api';
import { useCalls, useCreateBlacklistEntry } from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { Call, CallDirection, ListCallsParams } from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { RecordingList, recordingFileBase } from '@/pbx/RecordingList';
import { AppShellPage } from '@/shell/AppShellPage';
import { ClickToCallButton } from '@/softphone/ClickToCallButton';
import { Button } from '@/ui/Button';
import { Modal } from '@/ui/Dialog';
import { Field, Input, Select } from '@/ui/Field';
import { Badge, type Tone } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';
import { useToast } from '@/ui/Toast';
import { AdvancedSearchPanel } from './AdvancedSearchPanel';
import { buildAdvancedParams, countActiveFilters, EMPTY_ADVANCED_SEARCH, type AdvancedSearchForm } from './advancedSearch';
import { addSearchTemplate, loadSearchTemplates, removeSearchTemplate, saveSearchTemplates, type SearchTemplate } from './searchTemplates';

const DIRECTION_ICON: Record<CallDirection, typeof PhoneIncoming> = { in: PhoneIncoming, out: PhoneOutgoing, internal: ArrowLeftRight };
const DISPOSITION_TONE: Record<Call['disposition'], Tone> = { answered: 'success', no_answer: 'warning', busy: 'warning', failed: 'danger' };

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** S12 — qoʻngʻiroqlar tarixi: sana/yoʻnalish filtri, FreePBX «CDR Reports» uslubidagi kengaytirilgan
 * qidiruv (saqlanadigan shablonlar bilan), CSV eksport, qidirish, sahifalash, Asia/Tashkent vaqti. */
export function CallsPage() {
  const { t } = useTranslation('calls');
  const [from, setFrom] = useState(daysAgo(7));
  const [to, setTo] = useState(isoDate(new Date()));
  const [direction, setDirection] = useState<'all' | CallDirection>('all');
  const [blocking, setBlocking] = useState<Call | null>(null);
  const canManage = useCanEdit('apps');
  const canManageRecordings = useCanEdit('reports');

  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [draft, setDraft] = useState<AdvancedSearchForm>(EMPTY_ADVANCED_SEARCH);
  const [applied, setApplied] = useState<AdvancedSearchForm>(EMPTY_ADVANCED_SEARCH);
  const [templates, setTemplates] = useState<SearchTemplate[]>(() => loadSearchTemplates());
  const [exporting, setExporting] = useState(false);
  const toast = useToast();

  const baseParams: ListCallsParams = {
    from: `${from}T00:00:00.000Z`,
    to: `${to}T23:59:59.999Z`,
    direction: direction === 'all' ? undefined : direction,
    page: 1,
    size: 500,
  };
  const advancedParams = useMemo(() => buildAdvancedParams(applied), [applied]);
  const { data, isLoading, isError, refetch } = useCalls({ ...baseParams, ...advancedParams });

  const changeDraft = (patch: Partial<AdvancedSearchForm>) => setDraft((prev) => ({ ...prev, ...patch }));
  const clearAdvanced = () => { setDraft(EMPTY_ADVANCED_SEARCH); setApplied(EMPTY_ADVANCED_SEARCH); };
  const applyTemplate = (id: string) => {
    const found = templates.find((tpl) => tpl.id === id);
    if (!found) return;
    setDraft(found.form);
    setApplied(found.form);
  };
  const saveTemplate = (name: string) => {
    const next = addSearchTemplate(templates, name, draft);
    setTemplates(next);
    saveSearchTemplates(next);
    toast({ kind: 'success', title: t('advanced.templates.saved', { name: name.trim() }) });
  };
  const deleteTemplate = (id: string) => {
    const next = removeSearchTemplate(templates, id);
    setTemplates(next);
    saveSearchTemplates(next);
  };
  const exportCsv = () => {
    setExporting(true);
    void apiClient.exportCallsCsv({ ...baseParams, ...advancedParams })
      .then((blob) => downloadBlob(blob, 'calls.csv'))
      .finally(() => setExporting(false));
  };

  const directionLabel: Record<CallDirection, string> = { in: t('direction.in'), out: t('direction.out'), internal: t('direction.internal') };
  const dispositionLabel: Record<Call['disposition'], string> = {
    answered: t('disposition.answered'), no_answer: t('disposition.no_answer'), busy: t('disposition.busy'), failed: t('disposition.failed'),
  };

  const columns: Column<Call>[] = [
    { key: 'started_at', header: t('column.startedAt'), sortValue: (r) => r.started_at, cell: (r) => <span className="num text-sm">{formatDateTime(r.started_at)}</span>, width: '180px' },
    {
      key: 'direction', header: t('column.direction'), cell: (r) => {
        const Icon = DIRECTION_ICON[r.direction];
        return <span className="flex items-center gap-1.5 text-sm"><Icon aria-hidden className="size-3.5 text-muted" />{directionLabel[r.direction]}</span>;
      },
    },
    {
      key: 'src', header: t('column.src'), sortValue: (r) => r.src, cell: (r) => (
        <div className="flex flex-col gap-0.5">
          <span className="inline-flex items-center gap-1"><span className="num">{r.src}</span><ClickToCallButton number={r.src} /></span>
          {r.src_name ? <span className="text-xs text-muted">{r.src_name}</span> : null}
        </div>
      ),
    },
    { key: 'dst', header: t('column.dst'), sortValue: (r) => r.dst, cell: (r) => <span className="inline-flex items-center gap-1"><span className="num">{r.dst}</span><ClickToCallButton number={r.dst} /></span> },
    { key: 'did', header: t('column.did'), cell: (r) => <span className="num text-muted">{r.did ?? '—'}</span> },
    { key: 'disposition', header: t('column.disposition'), cell: (r) => <Badge tone={DISPOSITION_TONE[r.disposition]}>{r.disposition === 'no_answer' ? <PhoneMissed aria-hidden className="size-3" /> : null}{dispositionLabel[r.disposition]}</Badge> },
    { key: 'duration', header: t('column.duration'), align: 'right', sortValue: (r) => r.duration, cell: (r) => <span className="num">{formatDurationSec(r.duration)}</span> },
    { key: 'trunk', header: t('column.trunk'), cell: (r) => <span className="text-muted">{r.trunk ?? '—'}</span> },
    { key: 'account', header: t('column.account'), cell: (r) => <span className="text-muted">{r.pin_label ?? '—'}</span> },
    {
      key: 'actions', header: t('column.actions'), align: 'right', cell: (r) => r.direction === 'in' ? (
        <Button size="sm" variant="ghost" icon={<ShieldOff />} disabled={!canManage} aria-label={t('block.ariaLabel', { number: r.src })} onClick={() => setBlocking(r)}>
          {t('block.action')}
        </Button>
      ) : null,
    },
    // Oxirgi ustun — yozilgan qoʻngʻiroqni shu yerdan tinglash / yuklab olish.
    { key: 'recording', header: t('column.recording'), cell: (r) => <RecordingList recordings={r.recordings} canDelete={canManageRecordings} fileBase={recordingFileBase(r)} /> },
  ];

  const activeAdvancedCount = countActiveFilters(applied);

  return (
    <AppShellPage title={t('title')}>
      <div className="mb-4 flex flex-wrap items-end gap-3 rounded-lg border border-line bg-surface p-3 shadow-card">
        <Field label={t('filter.from')}>
          {(a) => <Input {...a} type="date" value={from} max={to} onChange={(e) => setFrom(e.target.value)} />}
        </Field>
        <Field label={t('filter.to')}>
          {(a) => <Input {...a} type="date" value={to} min={from} max={isoDate(new Date())} onChange={(e) => setTo(e.target.value)} />}
        </Field>
        <Field label={t('filter.direction')}>
          {(a) => (
            <Select
              {...a}
              value={direction}
              onValueChange={(v) => setDirection(v as typeof direction)}
              options={[
                { value: 'all', label: t('filter.all') },
                { value: 'in', label: t('direction.in') },
                { value: 'out', label: t('direction.out') },
                { value: 'internal', label: t('direction.internal') },
              ]}
            />
          )}
        </Field>

        <div className="ml-auto flex items-end gap-2">
          <Button variant={advancedOpen ? 'secondary' : 'ghost'} size="sm" icon={<SlidersHorizontal />} onClick={() => setAdvancedOpen((v) => !v)} aria-expanded={advancedOpen}>
            {t('advanced.toggle')}
            {activeAdvancedCount > 0 ? <Badge tone="accent" className="ml-1.5">{activeAdvancedCount}</Badge> : null}
          </Button>
          <Button variant="secondary" size="sm" icon={<Download />} loading={exporting} onClick={exportCsv}>{t('advanced.exportCsv')}</Button>
        </div>
      </div>

      {advancedOpen ? (
        <AdvancedSearchPanel
          draft={draft}
          onChange={changeDraft}
          onApply={() => setApplied(draft)}
          onClear={clearAdvanced}
          templates={templates}
          onApplyTemplate={applyTemplate}
          onSaveTemplate={saveTemplate}
          onDeleteTemplate={deleteTemplate}
        />
      ) : null}

      <div className="mt-4">
        <DataTable
          caption={t('caption')}
          rows={data?.items ?? []}
          columns={columns}
          rowId={(r) => r.uniqueid}
          searchText={(r) => `${r.src} ${r.dst} ${r.did ?? ''}`}
          state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
          onRetry={() => void refetch()}
          pageSize={15}
          empty={{ title: t('empty.title'), body: t('empty.body') }}
        />
      </div>

      <BlockCallModal call={blocking} onClose={() => setBlocking(null)} />
    </AppShellPage>
  );
}

function BlockCallModal({ call, onClose }: { call: Call | null; onClose: () => void }) {
  const { t } = useTranslation('calls');
  const toast = useToast();
  const createM = useCreateBlacklistEntry();
  const [reason, setReason] = useState('');

  const close = () => { setReason(''); createM.reset(); onClose(); };
  const submit = () => {
    if (!call) return;
    createM.mutate({ number: call.src, reason: reason.trim() || null }, {
      onSuccess: (res) => { toast({ kind: 'success', title: t('block.toast.added', { number: res.item.number }) }); close(); },
    });
  };

  const errorField = isApiError(createM.error) ? createM.error.field : undefined;
  const errorMessage = isApiError(createM.error) ? createM.error.message : undefined;

  return (
    <Modal
      open={!!call}
      onOpenChange={(v) => !v && close()}
      title={call ? t('block.modalTitle', { number: call.src }) : ''}
      footer={
        <>
          <Button variant="ghost" onClick={close}>{t('block.cancel')}</Button>
          <Button variant="primary" loading={createM.isPending} onClick={submit}>{t('block.add')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label={t('block.numberLabel')}>
          {(a) => <Input {...a} mono readOnly value={call?.src ?? ''} />}
        </Field>
        <Field label={t('block.reasonLabel')} aside={t('block.reasonAside')} error={errorField === 'reason' ? errorMessage : undefined}>
          {(a) => <Input {...a} autoFocus placeholder={t('block.reasonPlaceholder')} value={reason} onChange={(e) => setReason(e.target.value)} />}
        </Field>
        {errorMessage && errorField !== 'reason' ? <p className="text-sm text-danger">{errorMessage}</p> : null}
      </div>
    </Modal>
  );
}
