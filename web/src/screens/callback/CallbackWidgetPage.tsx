import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Copy, Pencil, Plus, RotateCw, ShieldAlert, Trash2 } from 'lucide-react';
import {
  useCallbackRequests, useCallbackWidgets, useCreateCallbackWidget, useDeleteCallbackWidget,
  useRotateCallbackWidgetKey, useTargets, useTimeGroups, useUpdateCallbackWidget,
} from '@/api/queries';
import { isApiError } from '@/api/errors';
import type {
  CallbackOffhoursMode, CallbackRequestStatus, CallbackWidget, WidgetAppearance, WidgetAppearanceText,
} from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { applyToast } from '@/lib/applyToast';
import { copyText } from '@/lib/browser';
import { formatDateTimeShort } from '@/lib/time';
import type { Catalog, Destination } from '@/domain/destination';
import { toCatalog } from '@/pbx/catalog';
import { ChipListField } from '@/pbx/ChipListField';
import { DestinationPicker } from '@/pbx/DestinationPicker';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Drawer, Modal } from '@/ui/Dialog';
import { Field, Input, Select } from '@/ui/Field';
import { Badge, type Tone } from '@/ui/Status';
import { DataTable, type Column } from '@/ui/Table';
import { Tabs } from '@/ui/Tabs';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';

const WIDGET_TARGET_KINDS = ['extension', 'queue', 'ring_group', 'ivr'] as const;
const DEFAULT_COLOR = '#0f766e';
const LANGS = ['uz', 'ru', 'en'] as const;

const REQUEST_STATUS_TONE: Record<CallbackRequestStatus, Tone> = {
  pending: 'neutral', dialing: 'info', connected: 'success', failed: 'danger', rejected: 'warning', cancelled: 'neutral',
};

/** S17 — qayta qoʻngʻiroq vidjeti: saytga joylashtiriladigan tugma + operatorga avtomatik ulanish (M10 C A1). */
export function CallbackWidgetPage() {
  const { t } = useTranslation('callback');
  const canManage = useCanEdit('connect');
  return (
    <AppShellPage title={t('title')}>
      {!canManage && (
        <p className="mb-3 flex items-center gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2 text-sm text-muted">
          <ShieldAlert aria-hidden className="size-4 shrink-0" />
          {t('readOnlyNotice')}
        </p>
      )}
      <Tabs
        label={t('title')}
        items={[
          { value: 'widgets', label: t('tabs.widgets'), content: <WidgetsTab canManage={canManage} /> },
          { value: 'requests', label: t('tabs.requests'), content: <RequestsTab /> },
        ]}
      />
    </AppShellPage>
  );
}

type FormPayload = {
  name: string;
  target_id: string;
  allowed_origins: string[];
  time_group_id: string | null;
  offhours_mode: CallbackOffhoursMode;
  max_attempts: number;
  retry_interval_s: number;
  callerid_prefix: string | null;
  allow_international: boolean;
  appearance: WidgetAppearance;
  enabled: boolean;
};

function WidgetsTab({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('callback');
  const { data, isLoading, isError, refetch } = useCallbackWidgets();
  const { data: targets } = useTargets({ kind: WIDGET_TARGET_KINDS.join(',') });
  const toast = useToast();
  const [editing, setEditing] = useState<CallbackWidget | 'new' | null>(null);
  const [deleting, setDeleting] = useState<CallbackWidget | null>(null);
  const [rotating, setRotating] = useState<CallbackWidget | null>(null);

  const createM = useCreateCallbackWidget();
  const updateM = useUpdateCallbackWidget();
  const deleteM = useDeleteCallbackWidget();
  const rotateM = useRotateCallbackWidgetKey();
  const close = () => { setEditing(null); createM.reset(); updateM.reset(); };
  const mutation = editing === 'new' ? createM : updateM;
  const catalog: Catalog = useMemo(() => toCatalog(targets?.items ?? []), [targets]);

  const copySnippet = (w: CallbackWidget) => {
    if (!w.embed_snippet) return;
    void copyText(w.embed_snippet);
    toast({ kind: 'success', title: t('copied') });
  };

  const columns: Column<CallbackWidget>[] = [
    { key: 'name', header: t('column.name'), sortValue: (w) => w.name, cell: (w) => <span className="font-medium">{w.name}</span> },
    { key: 'target', header: t('column.target'), cell: (w) => <span className="truncate text-sm text-muted">{w.target.label}</span> },
    { key: 'origins', header: t('column.origins'), cell: (w) => <Badge tone={w.allowed_origins.length ? 'neutral' : 'warning'} mono>{w.allowed_origins.length}</Badge> },
    {
      key: 'enabled', header: t('column.enabled'), cell: (w) => (
        w.enabled ? <span className="text-fg">✓</span> : <span className="text-muted">—</span>
      ),
    },
    {
      key: 'actions', header: '', align: 'right', cell: (w) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" iconOnly icon={<Copy />} disabled={!w.embed_snippet} aria-label={t('copyAriaLabel', { name: w.name })} onClick={() => copySnippet(w)} />
          <Button size="sm" variant="ghost" iconOnly icon={<RotateCw />} disabled={!canManage} aria-label={t('rotateAriaLabel', { name: w.name })} onClick={() => setRotating(w)} />
          <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} disabled={!canManage} aria-label={t('editAriaLabel', { name: w.name })} onClick={() => setEditing(w)} />
          <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} disabled={!canManage} aria-label={t('deleteAriaLabel', { name: w.name })} onClick={() => setDeleting(w)} />
        </div>
      ),
    },
  ];

  return (
    <div>
      <DataTable
        caption={t('caption')}
        rows={data?.items ?? []}
        columns={columns}
        rowId={(w) => w.id}
        searchText={(w) => `${w.name} ${w.target.label}`}
        state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
        onRetry={() => void refetch()}
        onRowOpen={canManage ? (w) => setEditing(w) : undefined}
        empty={{ title: t('empty.title'), body: t('empty.body'), action: canManage ? <Button size="sm" onClick={() => setEditing('new')}>{t('empty.action')}</Button> : undefined }}
        toolbar={canManage ? <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setEditing('new')}>{t('newWidget')}</Button> : undefined}
      />

      {editing && (
        <WidgetForm
          item={editing === 'new' ? undefined : editing}
          catalog={catalog}
          pending={mutation.isPending}
          errorMessage={isApiError(mutation.error) ? mutation.error.message : undefined}
          onClose={close}
          onSubmit={(payload) => {
            if (editing === 'new') {
              createM.mutate(payload, { onSuccess: (res) => { close(); toast(applyToast(res.apply, t('toast.added'))); } });
            } else {
              updateM.mutate({ id: editing.id, payload: { ...payload, updated_at: editing.updated_at } }, {
                onSuccess: (res) => { close(); toast(applyToast(res.apply, t('toast.saved'))); },
              });
            }
          }}
        />
      )}

      <Modal
        open={!!deleting}
        onOpenChange={(v) => !v && setDeleting(null)}
        title={deleting ? t('deleteModal.title', { name: deleting.name }) : ''}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleting(null)}>{t('cancel')}</Button>
            <Button
              variant="danger" loading={deleteM.isPending}
              onClick={() => deleting && deleteM.mutate(deleting.id, {
                onSuccess: () => { toast({ kind: 'success', title: t('toast.deleted', { name: deleting.name }) }); setDeleting(null); },
                onError: (e) => toast({ kind: 'error', title: t('toast.deleteFailed'), description: e.message }),
              })}
            >
              {t('delete')}
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted">{t('deleteModal.body')}</p>
      </Modal>

      <Modal
        open={!!rotating}
        onOpenChange={(v) => !v && setRotating(null)}
        title={rotating ? t('rotateModal.title', { name: rotating.name }) : ''}
        footer={
          <>
            <Button variant="ghost" onClick={() => setRotating(null)}>{t('cancel')}</Button>
            <Button
              variant="primary" loading={rotateM.isPending}
              onClick={() => rotating && rotateM.mutate(rotating.id, {
                onSuccess: () => { toast({ kind: 'success', title: t('toast.rotated') }); setRotating(null); },
                onError: (e) => toast({ kind: 'error', title: t('toast.rotateFailed'), description: e.message }),
              })}
            >
              {t('rotateModal.confirm')}
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted">{t('rotateModal.body')}</p>
      </Modal>
    </div>
  );
}

function WidgetForm({
  item, catalog, onClose, onSubmit, pending, errorMessage,
}: {
  item?: CallbackWidget;
  catalog: Catalog;
  onClose: () => void;
  onSubmit: (payload: FormPayload) => void;
  pending: boolean;
  errorMessage?: string;
}) {
  const { t } = useTranslation('callback');
  const { data: timeGroups } = useTimeGroups();
  const [name, setName] = useState(item?.name ?? '');
  const [dest, setDest] = useState<Destination | null>(item ? { kind: item.target.kind, targetId: item.target.id } : null);
  const [origins, setOrigins] = useState<string[]>(item?.allowed_origins ?? []);
  const [timeGroupId, setTimeGroupId] = useState<string>(item?.time_group_id ?? '');
  const [offhoursMode, setOffhoursMode] = useState<CallbackOffhoursMode>(item?.offhours_mode ?? 'schedule');
  const [maxAttempts, setMaxAttempts] = useState(String(item?.max_attempts ?? 2));
  const [retryIntervalS, setRetryIntervalS] = useState(String(item?.retry_interval_s ?? 120));
  const [callerIdPrefix, setCallerIdPrefix] = useState(item?.callerid_prefix ?? '');
  const [allowIntl, setAllowIntl] = useState(item?.allow_international ?? false);
  const [enabled, setEnabled] = useState(item?.enabled ?? true);
  const [color, setColor] = useState(item?.appearance.color ?? DEFAULT_COLOR);
  const [position, setPosition] = useState<'left' | 'right'>(item?.appearance.position ?? 'right');
  const [titleText, setTitleText] = useState<WidgetAppearanceText>(item?.appearance.title ?? { uz: '', ru: '', en: '' });
  const [buttonText, setButtonText] = useState<WidgetAppearanceText>(item?.appearance.button ?? { uz: '', ru: '', en: '' });
  const [successText, setSuccessText] = useState<WidgetAppearanceText>(item?.appearance.success ?? { uz: '', ru: '', en: '' });

  const valid = name.trim().length > 0 && dest !== null && dest.kind !== 'external';

  const submit = () => {
    if (!dest || dest.kind === 'external') return;
    onSubmit({
      name: name.trim(),
      target_id: dest.targetId,
      allowed_origins: origins,
      time_group_id: timeGroupId || null,
      offhours_mode: offhoursMode,
      max_attempts: Number(maxAttempts) || 2,
      retry_interval_s: Number(retryIntervalS) || 120,
      callerid_prefix: callerIdPrefix.trim() || null,
      allow_international: allowIntl,
      appearance: { color, position, title: titleText, button: buttonText, success: successText },
      enabled,
    });
  };

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={item ? t('form.editTitle', { name: item.name }) : t('form.newTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={submit}>{item ? t('save') : t('add')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-5">
        {errorMessage && <p className="text-sm text-danger">{errorMessage}</p>}

        <Field label={t('form.nameLabel')} required>
          {(a) => <Input {...a} autoFocus value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>

        <DestinationPicker
          label={t('form.targetLabel')} required kinds={[...WIDGET_TARGET_KINDS]} value={dest} onChange={setDest} catalog={catalog}
        />

        <ChipListField
          items={origins} onChange={setOrigins}
          label={t('form.originsLabel')} hint={t('form.originsHint')} emptyLabel={t('form.originsEmpty')}
          placeholder={t('form.originsPlaceholder')} addLabel={t('form.originsAdd')}
          removeAriaLabel={(origin) => t('form.originsRemoveAriaLabel', { origin })}
        />

        <div className="grid grid-cols-2 gap-4">
          <Field label={t('form.timeGroupLabel')}>
            {(a) => (
              <Select
                {...a} value={timeGroupId} onValueChange={setTimeGroupId}
                placeholder={t('form.timeGroupNone')}
                options={(timeGroups?.items ?? []).map((g) => ({ value: g.id, label: g.name }))}
              />
            )}
          </Field>
          <Field label={t('form.offhoursLabel')}>
            {(a) => (
              <Select
                {...a} value={offhoursMode} disabled={!timeGroupId} onValueChange={(v) => setOffhoursMode(v as CallbackOffhoursMode)}
                options={[{ value: 'schedule', label: t('form.offhours.schedule') }, { value: 'reject', label: t('form.offhours.reject') }]}
              />
            )}
          </Field>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Field label={t('form.maxAttemptsLabel')}>
            {(a) => <Input {...a} type="number" min={1} max={5} className="num" value={maxAttempts} onChange={(e) => setMaxAttempts(e.target.value)} />}
          </Field>
          <Field label={t('form.retryIntervalLabel')}>
            {(a) => <Input {...a} type="number" min={60} max={1800} className="num" value={retryIntervalS} onChange={(e) => setRetryIntervalS(e.target.value)} />}
          </Field>
        </div>

        <Field label={t('form.callerIdPrefixLabel')} hint={t('form.callerIdPrefixHint')}>
          {(a) => <Input {...a} value={callerIdPrefix} onChange={(e) => setCallerIdPrefix(e.target.value)} />}
        </Field>

        <Toggle checked={allowIntl} onCheckedChange={setAllowIntl} label={t('form.allowInternationalLabel')} />
        <Toggle checked={enabled} onCheckedChange={setEnabled} label={t('column.enabled')} />

        <section className="flex flex-col gap-3 rounded-lg border border-line bg-surface p-4">
          <h3 className="font-display text-base font-semibold">{t('form.appearanceTitle')}</h3>
          <div className="grid grid-cols-2 gap-4">
            <Field label={t('form.colorLabel')}>
              {(a) => (
                <div className="flex items-center gap-2">
                  <span aria-hidden className="size-8 shrink-0 rounded-md border border-line" style={{ backgroundColor: color }} />
                  <Input {...a} mono value={color} onChange={(e) => setColor(e.target.value)} />
                </div>
              )}
            </Field>
            <Field label={t('form.positionLabel')}>
              {(a) => (
                <Select
                  {...a} value={position} onValueChange={(v) => setPosition(v as 'left' | 'right')}
                  options={[{ value: 'right', label: t('form.position.right') }, { value: 'left', label: t('form.position.left') }]}
                />
              )}
            </Field>
          </div>

          <LangTextGroup label={t('form.titleTextLabel')} value={titleText} onChange={setTitleText} />
          <LangTextGroup label={t('form.buttonTextLabel')} value={buttonText} onChange={setButtonText} />
          <LangTextGroup label={t('form.successTextLabel')} value={successText} onChange={setSuccessText} />

          <WidgetPreview color={color} position={position} buttonText={buttonText.uz} titleText={titleText.uz} />
        </section>

        <EmbedSnippetSection item={item} />
      </div>
    </Drawer>
  );
}

function LangTextGroup({ label, value, onChange }: { label: string; value: WidgetAppearanceText; onChange: (v: WidgetAppearanceText) => void }) {
  const { t } = useTranslation('callback');
  const langLabel: Record<(typeof LANGS)[number], string> = { uz: t('form.langUz'), ru: t('form.langRu'), en: t('form.langEn') };
  return (
    <div>
      <p className="mb-1.5 text-sm font-medium text-fg">{label}</p>
      <div className="grid grid-cols-3 gap-2">
        {LANGS.map((lang) => (
          <Field key={lang} label={langLabel[lang]}>
            {(a) => <Input {...a} value={value[lang]} onChange={(e) => onChange({ ...value, [lang]: e.target.value })} />}
          </Field>
        ))}
      </div>
    </div>
  );
}

function WidgetPreview({ color, position, buttonText, titleText }: { color: string; position: 'left' | 'right'; buttonText: string; titleText: string }) {
  const { t } = useTranslation('callback');
  return (
    <div className="flex flex-col gap-2">
      <p className="eyebrow">{t('form.previewTitle')}</p>
      <div className={`relative flex h-28 items-end rounded-md border border-dashed border-line bg-surface-2/60 p-3 ${position === 'left' ? 'justify-start' : 'justify-end'}`}>
        <div className="flex flex-col items-end gap-2">
          {titleText && (
            <div className="max-w-[180px] rounded-lg border border-line bg-surface px-3 py-2 text-xs text-fg shadow-card">{titleText}</div>
          )}
          <button
            type="button" tabIndex={-1}
            className="rounded-full px-4 py-2 text-sm font-medium text-white shadow-card"
            style={{ backgroundColor: color }}
          >
            {buttonText || '—'}
          </button>
        </div>
      </div>
    </div>
  );
}

function EmbedSnippetSection({ item }: { item?: CallbackWidget }) {
  const { t } = useTranslation('callback');
  const toast = useToast();
  if (!item) return null;
  return (
    <section className="flex flex-col gap-2 rounded-lg border border-line bg-surface p-4">
      <h3 className="font-display text-base font-semibold">{t('form.embedTitle')}</h3>
      <p className="text-xs text-muted">{t('form.embedHint')}</p>
      {item.embed_snippet ? (
        <>
          <pre className="num overflow-x-auto rounded-md bg-surface-2/60 p-2.5 text-xs text-fg">{item.embed_snippet}</pre>
          <div>
            <Button
              size="sm" variant="secondary" icon={<Copy />}
              onClick={() => { void copyText(item.embed_snippet as string); toast({ kind: 'success', title: t('copied') }); }}
            >
              {t('form.embedCopy')}
            </Button>
          </div>
        </>
      ) : (
        <p className="text-sm text-warning">{t('form.embedMissing')}</p>
      )}
    </section>
  );
}

function RequestsTab() {
  const { t } = useTranslation('callback');
  const { data, isLoading, isError, refetch } = useCallbackRequests({ page: 1, page_size: 100 });

  const rows = data?.items ?? [];

  const cols: Column<typeof rows[number]>[] = [
    { key: 'created_at', header: t('requests.column.created'), sortValue: (r) => r.created_at, cell: (r) => <span className="num text-sm text-muted">{formatDateTimeShort(r.created_at)}</span> },
    { key: 'widget_name', header: t('requests.column.widget'), cell: (r) => <span className="truncate text-sm">{r.widget_name}</span> },
    { key: 'phone', header: t('requests.column.phone'), cell: (r) => <span className="num">{r.phone}</span> },
    { key: 'name', header: t('requests.column.name'), cell: (r) => <span className="text-muted">{r.name ?? '—'}</span> },
    { key: 'status', header: t('requests.column.status'), cell: (r) => <Badge tone={REQUEST_STATUS_TONE[r.status]}>{t(`requests.status.${r.status}`)}</Badge> },
    { key: 'attempts', header: t('requests.column.attempts'), align: 'right', cell: (r) => <span className="num">{r.attempts}</span> },
    { key: 'last_error', header: t('requests.column.error'), cell: (r) => <span className="truncate text-sm text-muted">{r.last_error ?? '—'}</span> },
  ];

  return (
    <DataTable
      caption={t('requests.caption')}
      rows={rows}
      columns={cols}
      rowId={(r) => r.id}
      searchText={(r) => `${r.widget_name} ${r.phone} ${r.name ?? ''}`}
      state={isLoading ? 'loading' : isError ? 'error' : 'ready'}
      onRetry={() => void refetch()}
      empty={{ title: t('requests.empty'), body: '' }}
      pageSize={10}
    />
  );
}
