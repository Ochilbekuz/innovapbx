import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, Bell, Lock, RotateCw, Send, ShieldAlert, Upload, Wand2 } from 'lucide-react';
import {
  useCreateSelfSignedTls, useNotifySettings, useRestartAsterisk, useSipSettings, useSipTls, useTestNotify,
  useUpdateNotifySettings, useUpdateSipSettings, useUploadSipTlsCertificate,
} from '@/api/queries';
import { isApiError } from '@/api/errors';
import type { NotifyChannel, NotifySettings } from '@/api/types';
import { usePermission } from '@/auth/permissions';
import { applyToast } from '@/lib/applyToast';
import { cn } from '@/lib/cn';
import { daysUntil, isExpired, isExpiringSoon } from '@/lib/certExpiry';
import { formatDateTimeShort } from '@/lib/time';
import { isValidCidr, splitList } from '@/lib/validators';
import { AppShellPage } from '@/shell/AppShellPage';
import { Button } from '@/ui/Button';
import { Modal } from '@/ui/Dialog';
import { Field, Input, Segmented, Select, Textarea } from '@/ui/Field';
import { Badge } from '@/ui/Status';
import { useToast } from '@/ui/Toast';

const CODECS = ['ulaw', 'alaw', 'g722', 'opus'] as const;

function badCertificateReason(e: unknown): string | undefined {
  return isApiError(e) && e.code === 'bad_certificate' ? (e.details?.reason as string | undefined) : undefined;
}

/** S32 — SIP va tarmoq: tashqi IP/portlar/RTP/kodeklar, TLS sertifikati va bildirishnoma sozlamalari. */
export function SipPage() {
  const { t } = useTranslation('sip');
  const { data, isLoading, isError, refetch } = useSipSettings();
  const { data: tls } = useSipTls();
  const canManage = usePermission('*');
  const toast = useToast();
  const updateM = useUpdateSipSettings();
  const restartM = useRestartAsterisk();
  const [confirmForce, setConfirmForce] = useState(false);

  if (isLoading || !data) {
    return (
      <AppShellPage title={t('title')}>
        <p className="rounded-md border border-dashed border-line px-3 py-6 text-center text-sm text-muted">{isError ? t('loadFailed') : t('loading')}</p>
        {isError && <Button size="sm" variant="secondary" className="mt-2" onClick={() => void refetch()}>{t('retry')}</Button>}
      </AppShellPage>
    );
  }

  const restartRequired = data.restart_required || (tls?.restart_required ?? false);
  const doRestart = (force: boolean) => restartM.mutate(force, {
    onSuccess: () => { toast({ kind: 'success', title: t('restartedTitle') }); setConfirmForce(false); },
    onError: (e) => {
      if (isApiError(e) && e.code === 'active_calls') setConfirmForce(true);
      else toast({ kind: 'error', title: t('restartFailedTitle'), description: e.message });
    },
  });

  return (
    <AppShellPage title={t('title')}>
      {!canManage && (
        <p className="mb-3 flex items-center gap-2 rounded-md border border-line bg-surface-2/60 px-3 py-2 text-sm text-muted">
          <ShieldAlert aria-hidden className="size-4 shrink-0" />
          {t('readOnlyNotice')}
        </p>
      )}

      {restartRequired && (
        <div className="mb-4 flex flex-wrap items-center gap-3 rounded-md border border-warning/30 bg-warning-soft px-3 py-2.5 text-sm text-on-warning-soft">
          <AlertTriangle aria-hidden className="size-4 shrink-0" />
          <span className="flex-1">{t('restartRequired')}</span>
          {canManage && <Button size="sm" variant="primary" icon={<RotateCw />} loading={restartM.isPending} onClick={() => doRestart(false)}>{t('restart')}</Button>}
        </div>
      )}

      <div className="flex max-w-2xl flex-col gap-6">
        <SipForm
          settings={data} canManage={canManage} pending={updateM.isPending}
          errorField={isApiError(updateM.error) ? updateM.error.field : undefined}
          errorMessage={isApiError(updateM.error) ? updateM.error.message : undefined}
          onSubmit={(payload) => updateM.mutate({ ...payload, updated_at: data.updated_at }, { onSuccess: (res) => toast(applyToast(res.apply, t('saved'))) })}
        />
        <TlsCard canManage={canManage} />
        <NotifySection canManage={canManage} />
      </div>

      <Modal
        open={confirmForce}
        onOpenChange={setConfirmForce}
        title={t('activeCallsModal.title')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmForce(false)}>{t('activeCallsModal.cancel')}</Button>
            <Button variant="danger" loading={restartM.isPending} onClick={() => doRestart(true)}>{t('activeCallsModal.confirmAnyway')}</Button>
          </>
        }
      >
        <p className="text-sm text-muted">{t('activeCallsModal.body')}</p>
      </Modal>
    </AppShellPage>
  );
}

function SipForm({ settings, canManage, onSubmit, pending, errorField, errorMessage }: {
  settings: NonNullable<ReturnType<typeof useSipSettings>['data']>;
  canManage: boolean;
  onSubmit: (payload: {
    external_ip: string | null; external_host: string | null; local_nets: string[]; sip_udp_port: number;
    sip_tls_port: number | null; rtp_start: number; rtp_end: number; codecs: string[];
  }) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('sip');
  const [externalIp, setExternalIp] = useState(settings.external_ip ?? '');
  const [externalHost, setExternalHost] = useState(settings.external_host ?? '');
  const [localNets, setLocalNets] = useState(settings.local_nets.join('\n'));
  const [udpPort, setUdpPort] = useState(String(settings.sip_udp_port));
  const [tlsPort, setTlsPort] = useState(settings.sip_tls_port != null ? String(settings.sip_tls_port) : '');
  const [rtpStart, setRtpStart] = useState(String(settings.rtp_start));
  const [rtpEnd, setRtpEnd] = useState(String(settings.rtp_end));
  const [codecs, setCodecs] = useState(new Set(settings.codecs));

  const netsList = splitList(localNets);
  const badNet = netsList.find((n) => !isValidCidr(n));
  const netsError = localNets.trim() !== '' && badNet ? t('error.badCidr', { bad: badNet }) : undefined;
  const rtpStartNum = Number(rtpStart);
  const rtpEndNum = Number(rtpEnd);
  const rtpError = rtpEndNum - rtpStartNum < 100 ? t('error.rtpRange') : undefined;
  const udpNum = Number(udpPort);
  const tlsNum = tlsPort.trim() ? Number(tlsPort) : null;
  const portError = tlsNum !== null && tlsNum === udpNum ? t('error.samePort') : undefined;
  const valid = !netsError && !rtpError && !portError && codecs.size > 0;

  const toggleCodec = (c: string) => setCodecs((prev) => { const n = new Set(prev); if (n.has(c)) n.delete(c); else n.add(c); return n; });

  return (
    <div className="flex flex-col gap-5">
      <section className="rounded-lg border border-line bg-surface p-4 shadow-card">
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-fg"><Wand2 aria-hidden className="size-4 text-brand" /> {t('detectedNetwork')}</h2>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted">{t('detectedExternalIp')}</span>
          <span className="num text-fg">{settings.detected.public_ip ?? '—'}</span>
          {canManage && settings.detected.public_ip && (
            <Button size="sm" variant="secondary" onClick={() => setExternalIp(settings.detected.public_ip as string)}>{t('apply')}</Button>
          )}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted">{t('detectedLocalNets')}</span>
          {settings.detected.local_ips.map((ip) => <Badge key={ip} mono>{ip}</Badge>)}
          {canManage && settings.detected.local_ips.length > 0 && (
            <Button size="sm" variant="secondary" onClick={() => setLocalNets(settings.detected.local_ips.join('\n'))}>{t('applyAll')}</Button>
          )}
        </div>
      </section>

      <div className="grid gap-4 rounded-lg border border-line bg-surface p-4 shadow-card sm:grid-cols-2">
        <Field label={t('field.externalIp')} aside={t('field.optional')} error={errorField === 'external_ip' ? errorMessage : undefined} hint={t('field.externalIpHint')} className="sm:col-span-2">
          {(a) => <Input {...a} mono disabled={!canManage} value={externalIp} onChange={(e) => setExternalIp(e.target.value)} placeholder="203.0.113.10" />}
        </Field>
        <Field label={t('field.externalHost')} aside={t('field.optional')} className="sm:col-span-2">
          {(a) => <Input {...a} mono disabled={!canManage} value={externalHost} onChange={(e) => setExternalHost(e.target.value)} placeholder={t('field.hostPlaceholder')} />}
        </Field>
        <Field label={t('field.localNets')} className="sm:col-span-2" error={netsError} hint={t('field.localNetsHint')}>
          {(a) => <Textarea {...a} className="num min-h-16" disabled={!canManage} value={localNets} onChange={(e) => setLocalNets(e.target.value)} placeholder="192.168.1.0/24" />}
        </Field>
        <Field label={t('field.udpPort')} required error={errorField === 'sip_udp_port' ? errorMessage : undefined}>
          {(a) => <Input {...a} mono disabled={!canManage} inputMode="numeric" value={udpPort} onChange={(e) => setUdpPort(e.target.value)} />}
        </Field>
        <Field label={t('field.tlsPort')} aside={t('field.optional')} error={portError}>
          {(a) => <Input {...a} mono disabled={!canManage} inputMode="numeric" placeholder={t('field.tlsDisabled')} value={tlsPort} onChange={(e) => setTlsPort(e.target.value)} />}
        </Field>
        <Field label={t('field.rtpStart')} required error={rtpError}>
          {(a) => <Input {...a} mono disabled={!canManage} inputMode="numeric" value={rtpStart} onChange={(e) => setRtpStart(e.target.value)} />}
        </Field>
        <Field label={t('field.rtpEnd')} required>
          {(a) => <Input {...a} mono disabled={!canManage} inputMode="numeric" value={rtpEnd} onChange={(e) => setRtpEnd(e.target.value)} />}
        </Field>
        <Field label={t('field.codecs')} className="sm:col-span-2">
          {() => (
            <div className="flex flex-wrap gap-3">
              {CODECS.map((c) => (
                <label key={c} className="flex items-center gap-1.5 text-sm">
                  <input type="checkbox" disabled={!canManage} className="size-4 accent-brand" checked={codecs.has(c)} onChange={() => toggleCodec(c)} />
                  <span className="num">{c}</span>
                </label>
              ))}
            </div>
          )}
        </Field>
      </div>

      {canManage && (
        <div>
          <Button
            variant="primary" loading={pending} disabled={!valid}
            onClick={() => onSubmit({
              external_ip: externalIp.trim() || null, external_host: externalHost.trim() || null, local_nets: netsList,
              sip_udp_port: udpNum, sip_tls_port: tlsNum, rtp_start: rtpStartNum, rtp_end: rtpEndNum, codecs: [...codecs],
            })}
          >
            {t('save')}
          </Button>
        </div>
      )}
    </div>
  );
}

function CertRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="shrink-0 text-muted">{label}</span>
      <span className={cn('truncate text-right text-fg', mono && 'num')}>{value}</span>
    </div>
  );
}

function TlsCard({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('sip');
  const { data: tls, isLoading, isError, refetch } = useSipTls();
  const toast = useToast();
  const uploadM = useUploadSipTlsCertificate();
  const generateM = useCreateSelfSignedTls();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [generateOpen, setGenerateOpen] = useState(false);

  const fail = (e: unknown) => {
    const reason = badCertificateReason(e);
    toast({ kind: 'error', title: t('tls.failedTitle'), description: reason ? t(`tls.badCertificate.${reason}`) : isApiError(e) ? e.message : undefined });
  };

  if (isLoading || !tls) {
    return (
      <section className="rounded-lg border border-line bg-surface p-4 shadow-card">
        <p className="text-sm text-muted">{isError ? t('loadFailed') : t('loading')}</p>
        {isError && <Button size="sm" variant="secondary" className="mt-2" onClick={() => void refetch()}>{t('retry')}</Button>}
      </section>
    );
  }

  const cert = tls.certificate;
  const expired = cert ? isExpired(cert.not_after) : false;
  const expiringSoon = cert && !expired ? isExpiringSoon(cert.not_after) : false;

  return (
    <section className="rounded-lg border border-line bg-surface p-4 shadow-card">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-fg"><Lock aria-hidden className="size-4 text-brand" /> {t('tls.title')}</h2>
        <Badge tone={tls.enabled ? 'success' : 'neutral'}>{tls.enabled ? t('tls.statusEnabled') : t('tls.statusDisabled')}</Badge>
      </div>

      {tls.restart_required && (
        <div className="mb-3 flex flex-wrap items-center gap-2 rounded-md border border-warning/30 bg-warning-soft px-3 py-2 text-sm text-on-warning-soft">
          <AlertTriangle aria-hidden className="size-4 shrink-0" />
          <span className="flex-1">{t('tls.restartRequired')}</span>
        </div>
      )}

      {tls.port != null && <p className="mb-2 text-sm text-muted">{t('tls.port')}: <span className="num text-fg">{tls.port}</span></p>}

      {cert ? (
        <div className="mb-3 flex flex-col gap-1 text-sm">
          <CertRow label={t('tls.subject')} value={cert.subject} />
          <CertRow label={t('tls.issuer')} value={cert.issuer} />
          <CertRow label={t('tls.notAfter')} value={formatDateTimeShort(cert.not_after)} />
          <CertRow label={t('tls.fingerprint')} value={cert.fingerprint_sha256} mono />
          {cert.self_signed && <Badge tone="neutral" className="mt-1 self-start">{t('tls.selfSigned')}</Badge>}
          {expired && <p className="mt-1 flex items-center gap-1.5 text-danger"><AlertTriangle aria-hidden className="size-4 shrink-0" />{t('tls.expired')}</p>}
          {expiringSoon && <p className="mt-1 flex items-center gap-1.5 text-warning"><AlertTriangle aria-hidden className="size-4 shrink-0" />{t('tls.expiringSoon', { days: daysUntil(cert.not_after) })}</p>}
        </div>
      ) : (
        <p className="mb-3 text-sm text-muted">{t('tls.noCertificate')}</p>
      )}

      {canManage && (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" icon={<Upload />} onClick={() => setUploadOpen(true)}>{t('tls.upload')}</Button>
          <Button size="sm" variant="secondary" icon={<Wand2 />} onClick={() => setGenerateOpen(true)}>{t('tls.generateSelfSigned')}</Button>
        </div>
      )}

      <TlsUploadModal
        open={uploadOpen} onOpenChange={setUploadOpen} pending={uploadM.isPending}
        onSubmit={(cert_, key, chain) => uploadM.mutate({ cert: cert_, key, chain }, {
          onSuccess: () => { setUploadOpen(false); toast({ kind: 'success', title: t('tls.uploadedTitle') }); },
          onError: fail,
        })}
      />
      <TlsGenerateModal
        open={generateOpen} onOpenChange={setGenerateOpen} pending={generateM.isPending}
        onSubmit={(common_name) => generateM.mutate({ common_name }, {
          onSuccess: () => { setGenerateOpen(false); toast({ kind: 'success', title: t('tls.generatedTitle') }); },
          onError: fail,
        })}
      />
    </section>
  );
}

function FilePicker({ label, aside, file, accept, onPick }: { label: string; aside?: string; file: File | null; accept: string; onPick: (f: File | null) => void }) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <Field label={label} aside={aside}>
      {() => (
        <div className="flex items-center gap-2">
          <Button size="sm" variant="secondary" onClick={() => ref.current?.click()}>{file ? file.name : label}</Button>
          <input ref={ref} type="file" accept={accept} className="sr-only" onChange={(e) => onPick(e.target.files?.[0] ?? null)} />
        </div>
      )}
    </Field>
  );
}

function TlsUploadModal({ open, onOpenChange, pending, onSubmit }: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  pending: boolean;
  onSubmit: (cert: File, key: File, chain?: File) => void;
}) {
  const { t } = useTranslation('sip');
  const [cert, setCert] = useState<File | null>(null);
  const [key, setKey] = useState<File | null>(null);
  const [chain, setChain] = useState<File | null>(null);
  const reset = () => { setCert(null); setKey(null); setChain(null); };

  return (
    <Modal
      open={open}
      onOpenChange={(v) => { onOpenChange(v); if (!v) reset(); }}
      title={t('tls.uploadTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!cert || !key} onClick={() => cert && key && onSubmit(cert, key, chain ?? undefined)}>{t('tls.upload')}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <FilePicker label={t('tls.certFile')} file={cert} accept=".pem,.crt,.cer" onPick={setCert} />
        <FilePicker label={t('tls.keyFile')} file={key} accept=".pem,.key" onPick={setKey} />
        <FilePicker label={t('tls.chainFile')} aside={t('tls.chainOptional')} file={chain} accept=".pem,.crt,.cer" onPick={setChain} />
      </div>
    </Modal>
  );
}

function TlsGenerateModal({ open, onOpenChange, pending, onSubmit }: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  pending: boolean;
  onSubmit: (commonName: string) => void;
}) {
  const { t } = useTranslation('sip');
  const [commonName, setCommonName] = useState('');

  return (
    <Modal
      open={open}
      onOpenChange={(v) => { onOpenChange(v); if (!v) setCommonName(''); }}
      title={t('tls.generateTitle')}
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>{t('cancel')}</Button>
          <Button variant="primary" loading={pending} disabled={!commonName.trim()} onClick={() => onSubmit(commonName.trim())}>{t('tls.generateSelfSigned')}</Button>
        </>
      }
    >
      <Field label={t('tls.commonNameLabel')} hint={t('tls.commonNameHint')}>
        {(a) => <Input {...a} mono autoFocus value={commonName} onChange={(e) => setCommonName(e.target.value)} placeholder={t('field.hostPlaceholder')} />}
      </Field>
    </Modal>
  );
}

const SMTP_TLS_OPTIONS = ['none', 'starttls', 'tls'] as const;

function NotifySection({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('notify');
  const { data, isLoading, isError, refetch } = useNotifySettings();
  const toast = useToast();
  const updateM = useUpdateNotifySettings();

  if (isLoading || !data) {
    return (
      <section className="rounded-lg border border-line bg-surface p-4 shadow-card">
        <p className="text-sm text-muted">{isError ? t('loadFailed') : t('loading')}</p>
        {isError && <Button size="sm" variant="secondary" className="mt-2" onClick={() => void refetch()}>{t('retry')}</Button>}
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-line bg-surface p-4 shadow-card">
      <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold text-fg"><Bell aria-hidden className="size-4 text-brand" /> {t('title')}</h2>
      <p className="mb-3 text-sm text-muted">{t('description')}</p>
      <NotifyForm
        settings={data} canManage={canManage} pending={updateM.isPending}
        errorField={isApiError(updateM.error) ? updateM.error.field : undefined}
        errorMessage={isApiError(updateM.error) ? updateM.error.message : undefined}
        onSubmit={(payload) => updateM.mutate(payload, { onSuccess: () => toast({ kind: 'success', title: t('saved') }) })}
      />
      <NotifyTestForm />
    </section>
  );
}

function NotifyForm({ settings, canManage, onSubmit, pending, errorField, errorMessage }: {
  settings: NotifySettings;
  canManage: boolean;
  onSubmit: (payload: {
    smtp_host: string | null; smtp_port: number; smtp_tls: NotifySettings['smtp_tls']; smtp_user: string | null;
    smtp_password?: string; from_email: string | null; telegram_token?: string; telegram_api_base: string;
  }) => void;
  pending: boolean;
  errorField?: string;
  errorMessage?: string;
}) {
  const { t } = useTranslation('notify');
  const [smtpHost, setSmtpHost] = useState(settings.smtp_host ?? '');
  const [smtpPort, setSmtpPort] = useState(String(settings.smtp_port));
  const [smtpTls, setSmtpTls] = useState(settings.smtp_tls);
  const [smtpUser, setSmtpUser] = useState(settings.smtp_user ?? '');
  const [smtpPassword, setSmtpPassword] = useState('');
  const [fromEmail, setFromEmail] = useState(settings.from_email ?? '');
  const [telegramToken, setTelegramToken] = useState('');
  const [telegramApiBase, setTelegramApiBase] = useState(settings.telegram_api_base);

  const portNum = Number(smtpPort);
  const valid = Number.isInteger(portNum) && portNum >= 1 && portNum <= 65535;

  const submit = () => {
    if (!valid) return;
    onSubmit({
      smtp_host: smtpHost.trim() || null,
      smtp_port: portNum,
      smtp_tls: smtpTls,
      smtp_user: smtpUser.trim() || null,
      ...(smtpPassword.trim() ? { smtp_password: smtpPassword.trim() } : {}),
      from_email: fromEmail.trim() || null,
      ...(telegramToken.trim() ? { telegram_token: telegramToken.trim() } : {}),
      telegram_api_base: telegramApiBase.trim(),
    });
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t('field.smtpHost')} error={errorField === 'smtp_host' ? errorMessage : undefined}>
          {(a) => <Input {...a} mono disabled={!canManage} value={smtpHost} onChange={(e) => setSmtpHost(e.target.value)} />}
        </Field>
        <Field label={t('field.smtpPort')} required error={errorField === 'smtp_port' ? errorMessage : undefined}>
          {(a) => <Input {...a} mono disabled={!canManage} inputMode="numeric" value={smtpPort} onChange={(e) => setSmtpPort(e.target.value)} />}
        </Field>
        <Field label={t('field.smtpTls')}>
          {({ id }) => (
            <Select
              id={id} disabled={!canManage} value={smtpTls} onValueChange={(v) => setSmtpTls(v as NotifySettings['smtp_tls'])}
              options={SMTP_TLS_OPTIONS.map((v) => ({ value: v, label: t(`field.smtpTls${v === 'none' ? 'None' : v === 'starttls' ? 'Starttls' : 'Tls'}`) }))}
            />
          )}
        </Field>
        <Field label={t('field.smtpUser')}>
          {(a) => <Input {...a} disabled={!canManage} value={smtpUser} onChange={(e) => setSmtpUser(e.target.value)} />}
        </Field>
        <Field label={t('field.smtpPassword')} aside={settings.has_smtp_password ? t('field.smtpPasswordSaved') : undefined}>
          {(a) => <Input {...a} type="password" disabled={!canManage} placeholder={t('field.smtpPasswordPlaceholder')} value={smtpPassword} onChange={(e) => setSmtpPassword(e.target.value)} />}
        </Field>
        <Field label={t('field.fromEmail')} error={errorField === 'from_email' ? errorMessage : undefined}>
          {(a) => <Input {...a} type="email" disabled={!canManage} value={fromEmail} onChange={(e) => setFromEmail(e.target.value)} />}
        </Field>
        <Field label={t('field.telegramToken')} aside={settings.has_telegram_token ? t('field.telegramTokenSaved') : undefined}>
          {(a) => <Input {...a} type="password" disabled={!canManage} placeholder={t('field.telegramTokenPlaceholder')} value={telegramToken} onChange={(e) => setTelegramToken(e.target.value)} />}
        </Field>
        <Field label={t('field.telegramApiBase')} error={errorField === 'telegram_api_base' ? errorMessage : undefined}>
          {(a) => <Input {...a} mono disabled={!canManage} value={telegramApiBase} onChange={(e) => setTelegramApiBase(e.target.value)} />}
        </Field>
      </div>

      {canManage && (
        <div>
          <Button variant="primary" loading={pending} disabled={!valid} onClick={submit}>{t('save')}</Button>
        </div>
      )}
    </div>
  );
}

function NotifyTestForm() {
  const { t } = useTranslation('notify');
  const toast = useToast();
  const testM = useTestNotify();
  const [channel, setChannel] = useState<NotifyChannel>('email');
  const [to, setTo] = useState('');

  const submit = () => {
    const toValue = to.trim();
    if (!toValue) return;
    testM.mutate({ channel, to: toValue }, {
      onSuccess: () => toast({ kind: 'success', title: t('test.sentTitle') }),
      onError: (e) => {
        const reason = isApiError(e) && e.code === 'notify_failed' ? (e.details?.reason as string | undefined) : undefined;
        toast({ kind: 'error', title: t('test.failedTitle'), description: reason ? t(`reason.${reason}`) : isApiError(e) ? e.message : undefined });
      },
    });
  };

  return (
    <div className="mt-4 flex flex-col gap-2 border-t border-line pt-4">
      <h3 className="text-sm font-medium text-fg">{t('test.title')}</h3>
      <div className="flex flex-wrap items-end gap-2">
        <Segmented
          label={t('test.channel')} value={channel} onChange={setChannel}
          options={[{ value: 'email', label: t('test.channelEmail') }, { value: 'telegram', label: t('test.channelTelegram') }]}
        />
        <Field label={t('test.to')} hint={channel === 'email' ? t('test.toHintEmail') : t('test.toHintTelegram')} className="min-w-[220px] flex-1">
          {(a) => <Input {...a} value={to} onChange={(e) => setTo(e.target.value)} />}
        </Field>
        <Button variant="secondary" icon={<Send />} loading={testM.isPending} disabled={!to.trim()} onClick={submit}>{t('test.send')}</Button>
      </div>
    </div>
  );
}
