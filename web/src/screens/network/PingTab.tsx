// "Ping" tab — SIP server / shlyuz / internetga ulanishni tekshirish (diagnostika,
// konfiguratsiyani o'zgartirmaydi — shuning uchun qulflangan holatda ham ishlaydi).
import { useMemo, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { apiErrorMessage } from '@/api/errors';
import { usePingHost, useTrunks } from '@/api/queries';
import type { PingResult } from '@/api/types';
import { buildPingPresets, isValidPingHost, PING_COUNT_DEFAULT, PING_COUNT_MAX, PING_COUNT_MIN, type PingPreset } from '@/domain/ping';
import { Button } from '@/ui/Button';
import { Field, Input } from '@/ui/Field';
import { StatusPill } from '@/ui/Status';

type TFunc = (k: string, v?: Record<string, unknown>) => string;

function clampCount(raw: string): number {
  const n = Number.parseInt(raw, 10);
  if (Number.isNaN(n)) return PING_COUNT_DEFAULT;
  return Math.min(PING_COUNT_MAX, Math.max(PING_COUNT_MIN, n));
}

function formatMs(value: number | null, t: TFunc): string {
  return value === null ? '—' : t('ping.ms', { value });
}

function presetLabel(preset: PingPreset, t: TFunc): string {
  const kind = t(`ping.preset.${preset.kind}`);
  return preset.name ? `${kind} · ${preset.name} · ${preset.host}` : `${kind} · ${preset.host}`;
}

function Presets({ presets, onPick, t }: { presets: PingPreset[]; onPick: (host: string) => void; t: TFunc }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm font-medium text-fg">{t('ping.presetsLabel')}</span>
      <div className="flex flex-wrap gap-2">
        {presets.map((p) => (
          <Button key={`${p.kind}-${p.host}`} type="button" variant="secondary" size="sm" onClick={() => onPick(p.host)}>
            {presetLabel(p, t)}
          </Button>
        ))}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="num text-sm font-medium text-fg">{value}</dd>
    </div>
  );
}

function PingResultView({ result, t }: { result: PingResult; t: TFunc }) {
  const rtt = [result.rtt_min_ms, result.rtt_avg_ms, result.rtt_max_ms].map((v) => formatMs(v, t)).join(' / ');
  return (
    <section aria-label={t('ping.resultTitle')} className="flex flex-col gap-3 rounded-md border border-line bg-surface-2 p-3">
      <div className="flex items-center gap-2">
        <StatusPill status={result.ok ? 'online' : 'error'}>{result.ok ? t('ping.reachable') : t('ping.unreachable')}</StatusPill>
        <span className="num text-sm text-fg">{result.host}</span>
      </div>
      <dl className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Metric label={t('ping.loss')} value={`${result.loss_pct}%`} />
        <Metric label={t('ping.packets')} value={`${result.transmitted} / ${result.received}`} />
        <Metric label={t('ping.rtt')} value={rtt} />
      </dl>
      <div className="flex flex-col gap-1">
        <span className="text-xs text-muted">{t('ping.output')}</span>
        <pre className="num max-h-72 overflow-auto whitespace-pre-wrap rounded-md border border-line bg-surface px-3 py-2 text-xs text-fg">{result.output}</pre>
      </div>
    </section>
  );
}

function DangerAlert({ children }: { children: string }) {
  return <div role="alert" className="rounded-md border border-danger/25 bg-danger-soft px-3 py-2.5 text-sm text-on-danger-soft">{children}</div>;
}

function PingForm({ presets, helperAvailable, loading, onRun, t }: {
  presets: PingPreset[]; helperAvailable: boolean; loading: boolean; onRun: (host: string, count: number) => void; t: TFunc;
}) {
  const [host, setHost] = useState('');
  const [count, setCount] = useState(String(PING_COUNT_DEFAULT));
  const trimmed = host.trim();
  const hostInvalid = trimmed !== '' && !isValidPingHost(trimmed);
  const canRun = helperAvailable && trimmed !== '' && !hostInvalid;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!canRun) return;
    const n = clampCount(count);
    setCount(String(n));
    onRun(trimmed, n);
  };

  return (
    <>
      <Presets presets={presets} onPick={setHost} t={t} />
      <form noValidate className="flex flex-wrap items-start gap-3" onSubmit={submit}>
        <Field label={t('ping.hostLabel')} error={hostInvalid ? t('ping.hostInvalid') : undefined} className="min-w-64 flex-1">
          {(a11y) => (
            <Input {...a11y} mono value={host} placeholder={t('ping.hostPlaceholder')} autoComplete="off" spellCheck={false}
              onChange={(e) => setHost(e.target.value)} />
          )}
        </Field>
        <Field label={t('ping.countLabel')} hint={t('ping.countHint')} className="w-36">
          {(a11y) => (
            <Input {...a11y} mono type="number" min={PING_COUNT_MIN} max={PING_COUNT_MAX} value={count}
              onChange={(e) => setCount(e.target.value)} />
          )}
        </Field>
        <Button type="submit" variant="primary" className="mt-6" loading={loading} disabled={!canRun}>{t('ping.run')}</Button>
      </form>
    </>
  );
}

function PingOutcome({ ping, t }: { ping: ReturnType<typeof usePingHost>; t: TFunc }) {
  if (ping.isError) return <DangerAlert>{apiErrorMessage(ping.error)}</DangerAlert>;
  if (!ping.data || ping.isPending) return null;
  return <PingResultView result={ping.data} t={t} />;
}

export function PingTab({ gateway, helperAvailable }: { gateway: string | null; helperAvailable: boolean }) {
  const { t } = useTranslation('network');
  const trunks = useTrunks();
  const ping = usePingHost();
  const presets = useMemo(() => buildPingPresets(gateway, trunks.data?.items ?? []), [gateway, trunks.data]);

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted">{t('ping.intro')}</p>
      {!helperAvailable && <DangerAlert>{t('ping.helperUnavailable')}</DangerAlert>}
      <PingForm presets={presets} helperAvailable={helperAvailable} loading={ping.isPending}
        onRun={(host, count) => ping.mutate({ host, count })} t={t} />
      <PingOutcome ping={ping} t={t} />
    </div>
  );
}
