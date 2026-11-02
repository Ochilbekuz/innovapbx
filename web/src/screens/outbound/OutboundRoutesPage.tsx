import { useEffect, useId, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, FlaskConical, Pencil, Phone, Plus, ShieldAlert, Trash2 } from 'lucide-react';
import {
  useCreateOutboundRoute, useDeleteOutboundRoute, useExtensions, useOutboundRoutes, useReorderOutboundRoutes,
  useSimulateOutboundRoute, useTrunks, useUpdateOutboundRoute,
} from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { CreateOutboundRoutePayload, OutboundExtensionRef, OutboundPattern, OutboundRoute, OutboundSimulateResult, Trunk } from '@/api/types';
import { useCanEdit } from '@/auth/permissions';
import { applyToast } from '@/lib/applyToast';
import { usagesOf } from '@/lib/usageError';
import { STEP_TEXT, validateOutboundForm } from '@/domain/outbound';
import { canonicalPattern } from '@/domain/pattern';
import { PatternEditor, type PatternRow } from '@/pbx/PatternEditor';
import { SortableList } from '@/pbx/SortableList';
import { UsageList } from '@/pbx/UsageList';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Drawer, Modal } from '@/ui/Dialog';
import { Field, Input, Select } from '@/ui/Field';
import { Badge, StatusPill, type Status } from '@/ui/Status';
import { Toggle } from '@/ui/Toggle';
import { useToast } from '@/ui/Toast';
import { newId } from '@/lib/browser';

const HEALTH_STATUS: Record<Trunk['health']['state'], Status> = { ok: 'online', unreachable: 'error', unknown: 'offline', disabled: 'disabled' };

function patternsToRows(patterns: OutboundPattern[]): PatternRow[] {
  return patterns.map((p) => ({ id: newId(), prepend: p.add_prefix, prefix: p.strip_prefix, pattern: p.pattern, callerId: p.callerid_match }));
}
function rowsToPatterns(rows: PatternRow[]): OutboundPattern[] {
  return rows.map((r) => ({ add_prefix: r.prepend.trim(), strip_prefix: r.prefix.trim(), pattern: canonicalPattern(r.pattern), callerid_match: r.callerId.trim() }));
}

/** S22 — Chiquvchi marshrutlar: ustunlik tartibi, naqshlar, trunk zahira ketma-ketligi, va simulyator. */
export function OutboundRoutesPage() {
  const { t } = useTranslation('outbound');
  const { data, isLoading, isError, refetch } = useOutboundRoutes();
  const { data: trunksData } = useTrunks();
  const { data: extensionsData } = useExtensions({ size: 200 });
  const canManage = useCanEdit('connect');
  const toast = useToast();
  const [editing, setEditing] = useState<OutboundRoute | 'new' | null>(null);
  const [deleting, setDeleting] = useState<OutboundRoute | null>(null);
  const [deleteErr, setDeleteErr] = useState<ReturnType<typeof usagesOf> | null>(null);

  const createM = useCreateOutboundRoute();
  const updateM = useUpdateOutboundRoute();
  const deleteM = useDeleteOutboundRoute();
  const reorderM = useReorderOutboundRoutes();
  const close = () => { setEditing(null); createM.reset(); updateM.reset(); };
  const mutation = editing === 'new' ? createM : updateM;

  const routes = useMemo(() => [...(data?.items ?? [])].sort((a, b) => a.priority - b.priority), [data]);
  const trunks = trunksData?.items ?? [];
  const extensions = extensionsData?.items ?? [];

  return (
    <AppShellPage title={t('title')}>
      {!canManage && (
        <p className="mb-3 flex items-center gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2 text-sm text-muted">
          <ShieldAlert aria-hidden className="size-4 shrink-0" />
          {t('readOnlyNotice')}
        </p>
      )}

      <div className="grid gap-5 lg:grid-cols-[1fr_380px] lg:items-start">
        <section aria-labelledby="outbound-list-h">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 id="outbound-list-h" className="text-base font-semibold text-fg">{t('listHeading')} <span className="num font-normal text-muted">({routes.length})</span></h2>
            {canManage && <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setEditing('new')}>{t('newRoute')}</Button>}
          </div>

          {isLoading ? (
            <p className="rounded-md border border-dashed border-line px-3 py-6 text-center text-sm text-muted">{t('loading')}</p>
          ) : isError ? (
            <div className="flex flex-col items-center gap-2 rounded-md border border-dashed border-line px-3 py-6 text-center text-sm text-muted">
              <p>{t('loadFailed')}</p>
              <Button size="sm" variant="secondary" onClick={() => void refetch()}>{t('retry')}</Button>
            </div>
          ) : routes.length === 0 ? (
            <div className="flex flex-col items-center gap-3 rounded-md border border-dashed border-line px-3 py-8 text-center">
              <p className="text-sm font-medium text-fg">{t('empty.title')}</p>
              <p className="max-w-sm text-sm text-muted">{t('empty.body')}</p>
              {canManage && <Button size="sm" onClick={() => setEditing('new')}>{t('empty.action')}</Button>}
            </div>
          ) : (
            <SortableList
              items={routes}
              onChange={(next) => canManage && reorderM.mutate({ ids: next.map((r) => r.id) })}
              itemId={(r) => r.id}
              itemLabel={(r) => r.name}
              label={t('listAriaLabel')}
              render={(r) => (
                <div className="flex min-w-0 flex-1 flex-wrap items-center gap-3 py-1">
                  <div className="min-w-[140px]">
                    <p className="truncate text-sm font-medium text-fg">{r.name}</p>
                    <p className="flex items-center gap-1.5 text-xs text-muted">
                      {!r.enabled && <Badge tone="neutral">{t('disabledBadge')}</Badge>}
                      {r.has_pin && <Badge tone="warning">{t('pinBadge')}</Badge>}
                      {r.international && <Badge tone="info">{t('internationalBadge')}</Badge>}
                      <span className="num">{t('patternsCount', { count: r.patterns.length })}</span>
                    </p>
                  </div>
                  <div className="flex min-w-0 flex-1 items-center gap-1 overflow-hidden text-xs">
                    {r.trunks.map((tr, i) => (
                      <span key={tr.trunk.id} className="flex items-center gap-1 whitespace-nowrap">
                        {i > 0 && <span className="text-muted">→</span>}
                        <StatusPill status={HEALTH_STATUS[tr.trunk.health_state]}>{tr.trunk.name}</StatusPill>
                      </span>
                    ))}
                  </div>
                  <span className="whitespace-nowrap text-xs text-muted">{r.extensions === 'all' ? t('allExtensions') : t('extensionsCount', { count: r.extensions.length })}</span>
                  {canManage && (
                    <div className="ml-auto flex gap-1">
                      <Button size="sm" variant="ghost" iconOnly icon={<Pencil />} aria-label={t('editAriaLabel', { name: r.name })} onClick={() => setEditing(r)} />
                      <Button size="sm" variant="danger-ghost" iconOnly icon={<Trash2 />} aria-label={t('deleteAriaLabel', { name: r.name })} onClick={() => setDeleting(r)} />
                    </div>
                  )}
                </div>
              )}
            />
          )}
        </section>

        <OutboundSimulator routes={routes} extensions={extensions} />
      </div>

      {editing && (
        <OutboundRouteDrawer
          route={editing === 'new' ? undefined : editing}
          trunks={trunks}
          extensions={extensions}
          pending={mutation.isPending}
          errorField={isApiError(mutation.error) ? mutation.error.field : undefined}
          errorMessage={isApiError(mutation.error) ? mutation.error.message : undefined}
          errorDetails={isApiError(mutation.error) ? mutation.error.details : undefined}
          onClose={close}
          onSubmit={(payload) => {
            if (editing === 'new') createM.mutate(payload, { onSuccess: (res) => { close(); toast(applyToast(res.apply, t('toast.added'))); } });
            else updateM.mutate({ id: editing.id, payload: { ...payload, updated_at: editing.updated_at } }, { onSuccess: (res) => { close(); toast(applyToast(res.apply, t('toast.saved'))); } });
          }}
        />
      )}

      <Modal
        open={!!deleting}
        onOpenChange={(v) => !v && (setDeleting(null), setDeleteErr(null))}
        title={deleting ? t('deleteModal.title', { name: deleting.name }) : ''}
        footer={
          <>
            <Button variant="ghost" onClick={() => { setDeleting(null); setDeleteErr(null); }}>{t('cancel')}</Button>
            {!deleteErr && (
              <Button
                variant="danger" loading={deleteM.isPending}
                onClick={() => deleting && deleteM.mutate(deleting.id, {
                  onSuccess: () => { toast({ kind: 'success', title: t('toast.deleted', { name: deleting.name }) }); setDeleting(null); },
                  onError: (e) => { if (isApiError(e) && e.code === 'in_use') setDeleteErr(usagesOf(e)); else toast({ kind: 'error', title: t('toast.deleteFailed'), description: e.message }); },
                })}
              >
                {t('delete')}
              </Button>
            )}
          </>
        }
      >
        {deleteErr ? (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-danger">{t('deleteModal.usagePrefix', { name: deleting?.name })}</p>
            <UsageList usages={deleteErr} />
          </div>
        ) : (
          <p className="text-sm text-muted">{t('deleteModal.body', { name: deleting?.name })}</p>
        )}
      </Modal>
    </AppShellPage>
  );
}

// ─────────────────────── Simulyator ───────────────────────

function OutboundSimulator({ routes, extensions }: { routes: OutboundRoute[]; extensions: { id: string; number: string; name: string }[] }) {
  const { t } = useTranslation('outbound');
  const id = useId();
  const [extensionId, setExtensionId] = useState(extensions[0]?.id ?? '');
  const [number, setNumber] = useState('998901234567');
  // Ro'yxat dastlabki render'da bo'sh bo'lishi mumkin (so'rov hali tugamagan) — yuklangach standart tanlovni to'ldiramiz.
  useEffect(() => {
    if (!extensionId && extensions[0]) setExtensionId(extensions[0].id);
  }, [extensionId, extensions]);
  const simulateM = useSimulateOutboundRoute();
  const run = () => {
    if (!extensionId || !number.trim()) return;
    simulateM.mutate({ extension: extensionId, number: number.trim() });
  };
  const result = simulateM.data;

  return (
    <aside className="flex flex-col gap-3 rounded-lg border border-brand/25 bg-accent-soft/30 p-4 shadow-card lg:sticky lg:top-20">
      <div className="flex items-center gap-2">
        <FlaskConical aria-hidden className="size-4 text-brand" />
        <h2 className="text-base font-semibold text-fg">{t('simulator.heading')}</h2>
      </div>
      <p className="text-sm text-muted">{t('simulator.intro')}</p>

      <Field label={t('simulator.fromExtension')}>
        {({ id: fid }) => (
          <Select
            id={fid} value={extensionId} onValueChange={setExtensionId}
            options={extensions.length ? extensions.map((e) => ({ value: e.id, label: `${e.name} (${e.number})` })) : [{ value: '', label: t('simulator.noExtensions') }]}
          />
        )}
      </Field>
      <Field label={t('simulator.dialedNumber')}>
        {(a) => <Input {...a} mono value={number} onChange={(e) => setNumber(e.target.value.replace(/\s/g, ''))} placeholder="998901234567" />}
      </Field>
      <Button variant="primary" loading={simulateM.isPending} disabled={!extensionId || !number.trim()} onClick={run}>{t('simulator.run')}</Button>

      {result && <SimResult result={result} />}

      <p className="text-xs text-muted">{t('simulator.checkedSummary', { count: routes.length })}</p>
      <output id={`${id}-live`} aria-live="polite" className="sr-only">
        {result ? (result.allowed ? t('simulator.allowedLive', { name: result.route?.name }) : t('simulator.rejectedLive', { reason: result.reason })) : ''}
      </output>
    </aside>
  );
}

function SimResult({ result }: { result: OutboundSimulateResult }) {
  const { t } = useTranslation('outbound');
  return (
    <div className="flex flex-col gap-3 rounded-md border border-line bg-surface p-3">
      {result.allowed ? (
        <div className="flex flex-col gap-1.5">
          <Badge tone="success">{t('simulator.allowed')}</Badge>
          <p className="text-sm text-fg">
            <span className="text-muted">{t('simulator.dialedLabel')} </span><span className="num font-medium">{result.dialed}</span>
          </p>
          {result.callerid && <p className="text-sm text-muted">{t('simulator.callerIdLabel')} <span className="num text-fg">{result.callerid}</span></p>}
          <div className="flex flex-wrap items-center gap-1 pt-1">
            {result.trunks.map((tr, i) => (
              <span key={tr.id} className="flex items-center gap-1 text-xs">
                {i > 0 && <span className="text-muted">→</span>}
                <StatusPill status={HEALTH_STATUS[tr.health_state]}>{tr.name}</StatusPill>
              </span>
            ))}
          </div>
        </div>
      ) : (
        <div className="flex items-start gap-2">
          <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0 text-danger" />
          <div>
            <p className="text-sm font-medium text-danger">{t('simulator.rejected')}</p>
            <p className="text-sm text-muted">{result.reason}</p>
          </div>
        </div>
      )}
      <ol className="flex flex-col gap-1 border-t border-line pt-2 text-xs text-muted">
        {result.steps.map((s, i) => (
          <li key={`${s.route}-${i}`} className="flex items-start gap-1.5">
            <span className="num shrink-0">{i + 1}.</span>
            <span><span className="font-medium text-fg">{s.route}</span> — {STEP_TEXT[s.result]}{s.detail ? ` (${s.detail})` : ''}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

// ─────────────────────── Drawer formasi ───────────────────────

type TrunkChainItem = { id: string; name: string; health_state: Trunk['health']['state'] };

function OutboundRouteDrawer({
  route, trunks, extensions, onClose, onSubmit, pending, errorField, errorMessage, errorDetails,
}: {
  route?: OutboundRoute;
  trunks: Trunk[];
  extensions: { id: string; number: string; name: string }[];
  onClose: () => void;
  onSubmit: (payload: CreateOutboundRoutePayload) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
  errorDetails?: Record<string, unknown>;
}) {
  const { t } = useTranslation('outbound');
  const [name, setName] = useState(route?.name ?? '');
  const [enabled, setEnabled] = useState(route?.enabled ?? true);
  const [patternRows, setPatternRows] = useState<PatternRow[]>(() => (route ? patternsToRows(route.patterns) : [{ id: newId(), prepend: '', prefix: '', pattern: '_998XXXXXXXXX', callerId: '' }]));
  const [chain, setChain] = useState<TrunkChainItem[]>(() => (route?.trunks ?? []).map((tc) => ({ id: tc.trunk.id, name: tc.trunk.name, health_state: tc.trunk.health_state })));
  const [callerid, setCallerid] = useState(route?.callerid ?? '');
  const [overrideCallerid, setOverrideCallerid] = useState(route?.override_extension_callerid ?? false);
  const [pinOn, setPinOn] = useState(route?.has_pin ?? false);
  const [pin, setPin] = useState('');
  const [international, setInternational] = useState(route?.international ?? false);
  const [extMode, setExtMode] = useState<'all' | 'selected'>(route?.extensions === 'all' || !route ? 'all' : 'selected');
  const [selectedExt, setSelectedExt] = useState<OutboundExtensionRef[]>(() => (route && route.extensions !== 'all' ? route.extensions : []));

  const patternIndexError = typeof errorDetails?.index === 'number' ? errorDetails.index : null;
  const availableTrunks = trunks.filter((tr) => !chain.some((c) => c.id === tr.id));
  const availableExt = extensions.filter((e) => !selectedExt.some((s) => s.id === e.id));
  const { valid, pinError } = validateOutboundForm({
    name, patternCount: patternRows.length, everyPatternFilled: patternRows.every((r) => r.pattern.trim().length > 0),
    chainLength: chain.length, pinOn, pin, hasExistingPin: !!route?.has_pin, extensionsMode: extMode, selectedExtensionCount: selectedExt.length,
  });

  const submit = () => {
    if (!valid) return;
    onSubmit({
      name: name.trim(), enabled, patterns: rowsToPatterns(patternRows), trunk_ids: chain.map((c) => c.id),
      callerid: callerid.trim() || null, override_extension_callerid: overrideCallerid, international,
      extensions: extMode === 'all' ? 'all' : selectedExt.map((e) => e.id),
      ...(pinOn ? (pin.trim() ? { pin: pin.trim() } : {}) : { pin: null }),
    });
  };

  return (
    <Drawer
      open
      onOpenChange={(v) => !v && onClose()}
      title={route ? t('form.editTitle', { name: route.name }) : t('form.newTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={submit}>{route ? t('save') : t('add')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errorMessage && errorField !== 'trunk_ids' && patternIndexError === null && <p className="text-sm text-danger">{errorMessage}</p>}

        <Field label={t('form.nameLabel')} required>
          {(a) => <Input {...a} autoFocus value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Toggle checked={enabled} onCheckedChange={setEnabled} label={t('form.enabledLabel')} />

        <PatternsField rows={patternRows} onChange={setPatternRows} indexError={patternIndexError} errorMessage={errorMessage} />

        <TrunkChainEditor chain={chain} onChange={setChain} available={availableTrunks} errorField={errorField} errorMessage={errorMessage} />

        <Field label={t('form.calleridLabel')} aside={t('form.calleridAside')} hint={t('form.calleridHint')}>
          {(a) => <Input {...a} mono value={callerid} onChange={(e) => setCallerid(e.target.value)} placeholder={t('form.calleridPlaceholder')} />}
        </Field>
        <Toggle checked={overrideCallerid} onCheckedChange={setOverrideCallerid} label={t('form.overrideCalleridLabel')} description={t('form.overrideCalleridDesc')} />

        <PinField pinOn={pinOn} onPinOnChange={setPinOn} pin={pin} onPinChange={setPin} error={pinError} hasExistingPin={route?.has_pin} />
        <InternationalField checked={international} onChange={setInternational} />

        <ExtensionsPicker mode={extMode} onModeChange={setExtMode} selected={selectedExt} onSelectedChange={setSelectedExt} available={availableExt} />
      </div>
    </Drawer>
  );
}

function PatternsField({ rows, onChange, indexError, errorMessage }: { rows: PatternRow[]; onChange: (rows: PatternRow[]) => void; indexError: number | null; errorMessage?: string }) {
  const { t } = useTranslation('outbound');
  return (
    <div>
      <p className="mb-2 text-sm font-medium text-fg">{t('patterns.heading')}</p>
      <PatternEditor rows={rows} onChange={onChange} />
      {indexError !== null && errorMessage && (
        <p className="mt-1.5 text-sm text-danger">{t('patterns.rowError', { row: indexError + 1, message: errorMessage })}</p>
      )}
    </div>
  );
}

function TrunkChainEditor({ chain, onChange, available, errorField, errorMessage }: {
  chain: TrunkChainItem[]; onChange: (items: TrunkChainItem[]) => void; available: Trunk[]; errorField?: string; errorMessage?: string;
}) {
  const { t } = useTranslation('outbound');
  return (
    <div>
      <p className="mb-2 text-sm font-medium text-fg">{t('trunkChain.heading')} <span className="text-muted">{t('trunkChain.headingHint')}</span></p>
      {chain.length === 0 ? (
        <p className="rounded-md border border-dashed border-line px-3 py-4 text-center text-sm text-muted">{t('trunkChain.noTrunks')}</p>
      ) : (
        <SortableList
          items={chain}
          onChange={onChange}
          itemId={(c) => c.id}
          itemLabel={(c) => c.name}
          label={t('trunkChain.listAriaLabel')}
          render={(c, i) => (
            <div className="flex min-w-0 flex-1 items-center justify-between gap-2">
              <span className="truncate text-sm">
                {i === 0 ? <Badge tone="accent">{t('trunkChain.primaryBadge')}</Badge> : <Badge tone="neutral">{t('trunkChain.backupBadge', { n: i })}</Badge>} {c.name}
              </span>
              <Button size="sm" variant="ghost" onClick={() => onChange(chain.filter((x) => x.id !== c.id))}>{t('trunkChain.remove')}</Button>
            </div>
          )}
        />
      )}
      {errorField === 'trunk_ids' && errorMessage && <p className="mt-1.5 text-sm text-danger">{errorMessage}</p>}
      {available.length > 0 && (
        <div className="mt-2">
          <Select
            aria-label={t('trunkChain.addAriaLabel')}
            value="__add" onValueChange={(v) => { const tr = available.find((x) => x.id === v); if (tr) onChange([...chain, { id: tr.id, name: tr.name, health_state: tr.health.state }]); }}
            options={[{ value: '__add', label: t('trunkChain.addOption') }, ...available.map((tr) => ({ value: tr.id, label: tr.name }))]}
          />
        </div>
      )}
    </div>
  );
}

function PinField({ pinOn, onPinOnChange, pin, onPinChange, error, hasExistingPin }: {
  pinOn: boolean; onPinOnChange: (v: boolean) => void; pin: string; onPinChange: (v: string) => void; error?: string | null; hasExistingPin?: boolean;
}) {
  const { t } = useTranslation('outbound');
  return (
    <>
      <Toggle checked={pinOn} onCheckedChange={onPinOnChange} label={t('form.pinLabel')} description={t('form.pinDesc')} />
      {pinOn && (
        <Field label={t('form.pinFieldLabel')} error={error} hint={hasExistingPin ? t('form.pinHintChange') : t('form.pinHintNew')}>
          {(a) => <Input {...a} mono inputMode="numeric" placeholder={hasExistingPin ? '••••' : undefined} value={pin} onChange={(e) => onPinChange(e.target.value.replace(/\D/g, ''))} />}
        </Field>
      )}
    </>
  );
}

function InternationalField({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  const { t } = useTranslation('outbound');
  return (
    <>
      <Toggle checked={checked} onCheckedChange={onChange} label={t('form.internationalLabel')} description={t('form.internationalDesc')} />
      {checked && (
        <p className="flex items-start gap-2 rounded-md border border-warning/30 bg-warning-soft px-3 py-2 text-sm text-on-warning-soft">
          <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0" />
          {t('form.internationalWarning')}
        </p>
      )}
    </>
  );
}

function ExtensionsPicker({ mode, onModeChange, selected, onSelectedChange, available }: {
  mode: 'all' | 'selected'; onModeChange: (m: 'all' | 'selected') => void;
  selected: OutboundExtensionRef[]; onSelectedChange: (xs: OutboundExtensionRef[]) => void; available: { id: string; number: string; name: string }[];
}) {
  const { t } = useTranslation('outbound');
  return (
    <div>
      <p className="mb-2 text-sm font-medium text-fg">{t('form.whoCanUse')}</p>
      <div className="flex gap-2">
        <Button size="sm" variant={mode === 'all' ? 'primary' : 'secondary'} onClick={() => onModeChange('all')}>{t('form.all')}</Button>
        <Button size="sm" variant={mode === 'selected' ? 'primary' : 'secondary'} onClick={() => onModeChange('selected')}>{t('form.selected')}</Button>
      </div>
      {mode === 'selected' && (
        <div className="mt-2 flex flex-col gap-2">
          {selected.length === 0 ? (
            <p className="rounded-md border border-dashed border-line px-3 py-3 text-center text-sm text-muted">{t('form.noExtensionsSelected')}</p>
          ) : (
            <ul className="flex flex-wrap gap-1.5">
              {selected.map((e) => (
                <li key={e.id}>
                  <Badge tone="accent">
                    <Phone aria-hidden className="size-3" /> {e.name} ({e.number})
                    <button type="button" className="ml-1 text-muted hover:text-fg" aria-label={t('form.removeExtensionAriaLabel', { name: e.name })} onClick={() => onSelectedChange(selected.filter((x) => x.id !== e.id))}>×</button>
                  </Badge>
                </li>
              ))}
            </ul>
          )}
          {available.length > 0 && (
            <Select
              aria-label={t('form.addExtensionAriaLabel')}
              value="__add" onValueChange={(v) => { const e = available.find((x) => x.id === v); if (e) onSelectedChange([...selected, e]); }}
              options={[{ value: '__add', label: t('form.addExtensionOption') }, ...available.map((e) => ({ value: e.id, label: `${e.name} (${e.number})` }))]}
            />
          )}
        </div>
      )}
    </div>
  );
}
