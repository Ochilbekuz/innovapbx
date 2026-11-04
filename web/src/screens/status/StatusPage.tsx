// S36 — Tizim holati: disk, tranklar, internet, SIP interfeysi + diskni tozalash. Qarang shartnoma (vazifa, 2026-11-02).
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Cable, Globe, HardDrive, Power as PowerIcon, Router, Trash2 } from 'lucide-react';
import { useCleanup, useExecutePower, usePreviewCleanup, useSystemPower, useSystemStatus } from '@/api/queries';
import type { CleanupIn, CleanupResult, DiskCategory, SystemStatus } from '@/api/types';
import { apiErrorMessage } from '@/api/errors';
import { formatBytes } from '@/screens/backup/backupForms';
import { closeOnOpenChange } from '@/lib/formHelpers';
import { diskLevel, trunkHealthLevel } from '@/lib/health';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Checkbox } from '@/ui/Toggle';
import { Field, Input } from '@/ui/Field';
import { Modal } from '@/ui/Dialog';
import type { HealthItem } from '@/ui/Health';
import { HealthList, healthLevelBarClass } from '@/ui/Health';
import { Badge } from '@/ui/Status';
import { useToast } from '@/ui/Toast';

/** S36 — faqat `*` ruxsatiga ko'rinadi (`screens.ts`, group `system`); shartnoma: GET/POST `/system/*`. */
export function StatusPage() {
  const { t } = useTranslation('status');
  const { data, isLoading, isError, refetch } = useSystemStatus();
  const [cleanupOpen, setCleanupOpen] = useState(false);

  if (isLoading || !data) {
    return (
      <AppShellPage title={t('title')}>
        {isError ? (
          <div className="flex flex-col items-center gap-2 rounded-md border border-dashed border-line px-3 py-6 text-center text-sm text-muted">
            <p>{t('loadFailed')}</p>
            <Button size="sm" variant="secondary" onClick={() => void refetch()}>{t('retry')}</Button>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {Array.from({ length: 4 }, (_, i) => <div key={i} className="skeleton h-40 rounded-lg" />)}
          </div>
        )}
      </AppShellPage>
    );
  }

  return (
    <AppShellPage title={t('title')}>
      <div className="grid gap-4 lg:grid-cols-2">
        <DiskCard disk={data.disk} onCleanupClick={() => setCleanupOpen(true)} />
        <TrunksCard trunks={data.trunks} />
        <InternetCard internet={data.internet} />
        <SipCard sip={data.sip} />
        <PowerCard />
      </div>
      <CleanupModal open={cleanupOpen} onClose={() => setCleanupOpen(false)} />
    </AppShellPage>
  );
}

function DiskCard({ disk, onCleanupClick }: { disk: SystemStatus['disk']; onCleanupClick: () => void }) {
  const { t } = useTranslation('status');
  const level = diskLevel(disk.used_pct);
  return (
    <section aria-label={t('disk.title')} className="overflow-hidden rounded-lg border border-line bg-surface shadow-card">
      <header className="flex items-center justify-between gap-2 border-b border-line px-4 py-2.5">
        <div className="flex items-center gap-2">
          <HardDrive aria-hidden className="size-4 text-brand" />
          <h3 className="font-display text-base font-semibold">{t('disk.title')}</h3>
        </div>
        <Button
          size="sm"
          variant={level === 'ok' ? 'secondary' : 'danger'}
          icon={<Trash2 />}
          onClick={onCleanupClick}
        >
          {t('disk.cleanButton')}
        </Button>
      </header>
      <div className="flex flex-col gap-3 px-4 py-3">
        <div>
          <div
            role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={disk.used_pct} aria-label={t('disk.title')}
            className="h-2 w-full overflow-hidden rounded-full bg-surface-2 ring-1 ring-inset ring-line"
          >
            <span className={`block h-full rounded-full transition-[width] duration-slow ${healthLevelBarClass(level)}`} style={{ width: `${disk.used_pct}%` }} />
          </div>
          <div className="num mt-1.5 flex items-center justify-between text-xs text-muted">
            <span>{t('disk.usedOf', { used: disk.used_gb, total: disk.total_gb })}</span>
            <span>{t('disk.free', { free: disk.free_gb })}</span>
          </div>
        </div>
        <ul className="divide-y divide-line">
          {disk.categories.map((c) => <DiskCategoryRow key={c.key} category={c} />)}
        </ul>
      </div>
    </section>
  );
}

function DiskCategoryRow({ category }: { category: DiskCategory }) {
  const { t } = useTranslation('status');
  return (
    <li className="flex items-center justify-between gap-3 py-2 text-sm">
      <span className="min-w-0 truncate text-fg">{t(`disk.category.${category.key}`)}</span>
      <span className="flex shrink-0 items-center gap-2">
        {!category.cleanable && <Badge tone="neutral">{t('disk.notCleanable')}</Badge>}
        <span className="num text-xs text-muted">{t('disk.categoryLine', { size: formatBytes(category.bytes), files: category.files })}</span>
      </span>
    </li>
  );
}

function TrunksCard({ trunks }: { trunks: SystemStatus['trunks'] }) {
  const { t } = useTranslation('status');
  if (trunks.length === 0) {
    return (
      <section aria-label={t('trunks.title')} className="overflow-hidden rounded-lg border border-line bg-surface shadow-card">
        <header className="flex items-center gap-2 border-b border-line px-4 py-2.5">
          <Cable aria-hidden className="size-4 text-brand" />
          <h3 className="font-display text-base font-semibold">{t('trunks.title')}</h3>
        </header>
        <p className="px-4 py-6 text-center text-sm text-muted">{t('trunks.empty')}</p>
      </section>
    );
  }
  const items: HealthItem[] = trunks.map((tr) => ({
    id: tr.id,
    label: tr.name,
    level: trunkHealthLevel(tr.state),
    reason: tr.reason ?? undefined,
  }));
  return <HealthList items={items} title={t('trunks.title')} />;
}

/** Yorliq + ok/fail holat — Internet kartasida ulanish va DNS qatorlari uchun bitta andoza. */
function StatusRow({ label, ok, okText, failText }: { label: string; ok: boolean; okText: string; failText: string }) {
  return (
    <li className="flex items-center justify-between gap-3 py-2 text-sm">
      <span className="text-fg">{label}</span>
      <Badge tone={ok ? 'success' : 'danger'}>{ok ? okText : failText}</Badge>
    </li>
  );
}

function InternetCard({ internet }: { internet: SystemStatus['internet'] }) {
  const { t } = useTranslation('status');
  return (
    <section aria-label={t('internet.title')} className="overflow-hidden rounded-lg border border-line bg-surface shadow-card">
      <header className="flex items-center gap-2 border-b border-line px-4 py-2.5">
        <Globe aria-hidden className="size-4 text-brand" />
        <h3 className="font-display text-base font-semibold">{t('internet.title')}</h3>
      </header>
      <ul className="divide-y divide-line px-4">
        <StatusRow label={t('internet.connectionLabel')} ok={internet.up} okText={t('internet.up')} failText={t('internet.down')} />
        <StatusRow label={t('internet.dnsLabel')} ok={internet.dns_ok} okText={t('internet.dnsOk')} failText={t('internet.dnsFail')} />
        {internet.latency_ms !== null && (
          <li className="num flex items-center justify-between gap-3 py-2 text-sm text-muted">{t('internet.latency', { ms: internet.latency_ms })}</li>
        )}
        <li className="num flex items-center justify-between gap-3 py-2 text-sm text-muted">{t('internet.target', { target: internet.target })}</li>
        {internet.error && <li className="py-2 text-sm text-danger">{internet.error}</li>}
      </ul>
    </section>
  );
}

function SipCard({ sip }: { sip: SystemStatus['sip'] }) {
  const { t } = useTranslation('status');
  return (
    <section aria-label={t('sip.title')} className="overflow-hidden rounded-lg border border-line bg-surface shadow-card">
      <header className="flex items-center justify-between gap-2 border-b border-line px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Router aria-hidden className="size-4 text-brand" />
          <h3 className="font-display text-base font-semibold">{t('sip.title')}</h3>
        </div>
        <Badge tone={sip.asterisk_up ? 'success' : 'danger'}>{sip.asterisk_up ? t('sip.asteriskUp') : t('sip.asteriskDown')}</Badge>
      </header>
      <div className="flex flex-col gap-3 px-4 py-3">
        <table className="num w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs text-muted">
              <th className="py-1.5 pr-3 font-medium">{t('sip.column.name')}</th>
              <th className="py-1.5 pr-3 font-medium">{t('sip.column.protocol')}</th>
              <th className="py-1.5 font-medium">{t('sip.column.bind')}</th>
            </tr>
          </thead>
          <tbody>
            {sip.transports.map((tr) => (
              <tr key={tr.name} className="border-b border-line last:border-0">
                <td className="py-1.5 pr-3 text-fg">{tr.name}</td>
                <td className="py-1.5 pr-3 text-muted">{tr.protocol.toUpperCase()}</td>
                <td className="py-1.5 text-muted">{tr.bind}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-sm text-muted">{t('sip.endpointsOnline', { online: sip.endpoints_online, total: sip.endpoints_total })}</p>
      </div>
    </section>
  );
}

type PowerAction = 'reboot' | 'poweroff';

/** Qayta yuklash/oʻchirish — M12 B2 (../../replica/m12-contract.md §B2). Oʻz `/system/power`ini oʻqiydi, `data`dan mustaqil. */
function PowerCard() {
  const { t } = useTranslation('status');
  const toast = useToast();
  const { data: power, isLoading } = useSystemPower();
  const [action, setAction] = useState<PowerAction | null>(null);
  const executeM = useExecutePower();

  if (isLoading || !power) {
    return (
      <section aria-label={t('power.title')} className="overflow-hidden rounded-lg border border-line bg-surface shadow-card">
        <div className="skeleton h-32" />
      </section>
    );
  }

  const locked = power.readonly_reason !== null;

  const handleConfirm = (confirm: string) => {
    if (!action) return;
    executeM.mutate({ action, confirm }, {
      onSuccess: (res) => { toast({ kind: 'success', title: t('power.scheduledToast', { delay: res.delay_s }) }); setAction(null); },
      onError: (e) => toast({ kind: 'error', title: apiErrorMessage(e) }),
    });
  };

  return (
    <section aria-label={t('power.title')} className="overflow-hidden rounded-lg border border-line bg-surface shadow-card">
      <header className="flex items-center gap-2 border-b border-line px-4 py-2.5">
        <PowerIcon aria-hidden className="size-4 text-brand" />
        <h3 className="font-display text-base font-semibold">{t('power.title')}</h3>
      </header>
      <div className="flex flex-col gap-3 px-4 py-3">
        {locked && (
          <div className="rounded-md border border-warning/30 bg-warning-soft px-3 py-2.5 text-sm text-on-warning-soft">
            {t('power.readonlyBanner', { reason: power.readonly_reason })}
          </div>
        )}
        {power.active_calls !== null && (
          <p className="num text-sm text-muted">{t('power.activeCalls', { count: power.active_calls })}</p>
        )}
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" disabled={locked} onClick={() => setAction('reboot')}>{t('power.rebootButton')}</Button>
          <Button size="sm" variant="danger" disabled={locked} onClick={() => setAction('poweroff')}>{t('power.poweroffButton')}</Button>
        </div>
      </div>
      <PowerConfirmModal
        action={action}
        hostname={power.hostname}
        loading={executeM.isPending}
        onConfirm={handleConfirm}
        onClose={() => setAction(null)}
      />
    </section>
  );
}

/** Hostname'ni qoʻlda yozdirib tasdiqlatadi (xato bosilib ketmasligi uchun) — `ConfirmUpdateModal` bilan bir xil andoza. */
function PowerConfirmModal({
  action, hostname, loading, onConfirm, onClose,
}: {
  action: PowerAction | null;
  hostname: string;
  loading: boolean;
  onConfirm: (confirm: string) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation('status');
  const [typed, setTyped] = useState('');
  const matches = typed.trim() === hostname;

  const close = () => { setTyped(''); onClose(); };
  const submit = () => { if (matches) onConfirm(typed.trim()); };

  return (
    <Modal
      open={action !== null}
      onOpenChange={(v) => closeOnOpenChange(v, close)}
      title={action ? t(`power.modalTitle.${action}`) : ''}
      footer={
        <>
          <Button variant="ghost" onClick={close}>{t('power.cancel')}</Button>
          <Button variant={action === 'poweroff' ? 'danger' : 'primary'} loading={loading} disabled={!matches} onClick={submit}>
            {t('power.confirm')}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {action && (
          <div className="rounded-md border border-warning/30 bg-warning-soft px-3 py-2.5 text-sm text-on-warning-soft">
            {t(`power.modalWarning.${action}`)}
          </div>
        )}
        <Field label={t('power.confirmHint')} error={typed && !matches ? t('power.confirmMismatch') : undefined}>
          {(a) => (
            <Input {...a} mono placeholder={t('power.confirmPlaceholder')} value={typed} onChange={(e) => setTyped(e.target.value)} autoFocus />
          )}
        </Field>
      </div>
    </Modal>
  );
}

const DEFAULT_RECORDINGS_DAYS = 180;
const DEFAULT_BACKUPS_KEEP_LAST = 3;

/** Checkbox holatlaridan shartnomaga mos `CleanupIn` quradi — belgilanmagan maydon `null`/`false`. */
function buildCleanupPayload(
  recordingsOn: boolean, recordingsDays: number, backupsOn: boolean, backupsKeepLast: number, migrations: boolean,
): CleanupIn {
  return {
    recordings_older_than_days: recordingsOn ? recordingsDays : null,
    backups_keep_last: backupsOn ? backupsKeepLast : null,
    migrations,
  };
}

/** Modal ochiq va kamida bitta band belgilangan bo'lsa, ~300ms debounce bilan preview so'raydi. */
function useCleanupPreview(open: boolean, nothingSelected: boolean, payload: CleanupIn) {
  const previewM = usePreviewCleanup();
  const [preview, setPreview] = useState<CleanupResult | null>(null);
  const active = open && !nothingSelected;

  useEffect(() => {
    if (!active) { setPreview(null); return; }
    const timer = setTimeout(() => previewM.mutate(payload, { onSuccess: setPreview }), 300);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, payload.recordings_older_than_days, payload.backups_keep_last, payload.migrations]);

  return { preview, setPreview, loading: previewM.isPending };
}

/** Oldindan ko'rish/xatolar bloki — hech narsa tanlanmagan/hisoblanmoqda/natija holatlarini ko'rsatadi. */
function CleanupPreviewBox({ nothingSelected, loading, preview }: { nothingSelected: boolean; loading: boolean; preview: CleanupResult | null }) {
  const { t } = useTranslation('status');
  if (nothingSelected) return <span className="text-muted">{t('cleanup.previewEmpty')}</span>;
  if (loading || !preview) return <span className="text-muted">{t('cleanup.previewLoading')}</span>;
  const files = preview.recordings.files + preview.backups.files + preview.migrations.files;
  return (
    <>
      <p className="num font-medium text-fg">{t('cleanup.previewResult', { size: formatBytes(preview.total_bytes), files })}</p>
      {preview.errors.length > 0 && (
        <div className="mt-1.5 text-danger">
          <p>{t('cleanup.errorsTitle')}</p>
          <ul className="list-inside list-disc">
            {preview.errors.map((err, i) => <li key={i}>{err}</li>)}
          </ul>
        </div>
      )}
    </>
  );
}

/** Diskni tozalash modali — har o'zgarishda (~300ms debounce) preview chaqiradi, keyin tasdiqlab o'chiradi. */
function CleanupModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useTranslation('status');
  const toast = useToast();
  const [recordingsOn, setRecordingsOn] = useState(true);
  const [recordingsDays, setRecordingsDays] = useState(DEFAULT_RECORDINGS_DAYS);
  const [backupsOn, setBackupsOn] = useState(true);
  const [backupsKeepLast, setBackupsKeepLast] = useState(DEFAULT_BACKUPS_KEEP_LAST);
  const [migrations, setMigrations] = useState(false);

  const cleanupM = useCleanup();
  const payload = buildCleanupPayload(recordingsOn, recordingsDays, backupsOn, backupsKeepLast, migrations);
  const nothingSelected = !recordingsOn && !backupsOn && !migrations;
  const { preview, setPreview, loading: previewLoading } = useCleanupPreview(open, nothingSelected, payload);

  const close = () => {
    setRecordingsOn(true); setRecordingsDays(DEFAULT_RECORDINGS_DAYS);
    setBackupsOn(true); setBackupsKeepLast(DEFAULT_BACKUPS_KEEP_LAST);
    setMigrations(false); setPreview(null);
    cleanupM.reset();
    onClose();
  };

  const submit = () => {
    cleanupM.mutate(payload, {
      onSuccess: (result) => { toast({ kind: 'success', title: t('cleanup.doneToast', { size: formatBytes(result.total_bytes) }) }); close(); },
      onError: (e) => toast({ kind: 'error', title: apiErrorMessage(e) }),
    });
  };

  return (
    <Modal
      open={open}
      onOpenChange={(v) => closeOnOpenChange(v, close)}
      title={t('cleanup.modalTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={close}>{t('cleanup.cancel')}</Button>
          <Button variant="danger" loading={cleanupM.isPending} disabled={nothingSelected} onClick={submit}>
            {t('cleanup.confirm')}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <label className="flex items-center gap-2 text-sm font-medium text-fg">
            <Checkbox checked={recordingsOn} onCheckedChange={(v) => setRecordingsOn(v === true)} aria-label={t('cleanup.recordingsLabel')} />
            {t('cleanup.recordingsLabel')}
          </label>
          <Field label={t('cleanup.recordingsDays')} className="max-w-[10rem]" aside={undefined}>
            {(a) => (
              <Input {...a} type="number" min={1} mono disabled={!recordingsOn} value={recordingsDays} onChange={(e) => setRecordingsDays(Number(e.target.value))} />
            )}
          </Field>
        </div>

        <div className="flex flex-col gap-2">
          <label className="flex items-center gap-2 text-sm font-medium text-fg">
            <Checkbox checked={backupsOn} onCheckedChange={(v) => setBackupsOn(v === true)} aria-label={t('cleanup.backupsLabel')} />
            {t('cleanup.backupsLabel')}
          </label>
          <Field label={t('cleanup.backupsKeepLast')} className="max-w-[10rem]">
            {(a) => (
              <Input {...a} type="number" min={0} mono disabled={!backupsOn} value={backupsKeepLast} onChange={(e) => setBackupsKeepLast(Number(e.target.value))} />
            )}
          </Field>
        </div>

        <label className="flex items-center gap-2 text-sm font-medium text-fg">
          <Checkbox checked={migrations} onCheckedChange={(v) => setMigrations(v === true)} aria-label={t('cleanup.migrationsLabel')} />
          {t('cleanup.migrationsLabel')}
        </label>

        <div className="rounded-md border border-line bg-surface-2 px-3 py-2.5 text-sm">
          <CleanupPreviewBox nothingSelected={nothingSelected} loading={previewLoading} preview={preview} />
        </div>
      </div>
    </Modal>
  );
}
