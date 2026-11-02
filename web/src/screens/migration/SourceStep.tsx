import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Download, ShieldAlert, UploadCloud } from 'lucide-react';
import {
  useFetchMigrationSsh, useMigrationExportScript, useTestMigrationSsh, useUploadMigrationBundle,
} from '@/api/queries';
import { apiErrorMessage } from '@/api/errors';
import { Button } from '@/ui/Button';
import { Field, Input } from '@/ui/Field';
import { Modal } from '@/ui/Dialog';
import { Tabs } from '@/ui/Tabs';
import { useToast } from '@/ui/Toast';
import { bundleFileValid, sshFetchPayload, sshTestPayload, sshTestValid, useSshForm } from './migrationForms';

/** Blob'ni berilgan nom bilan brauzerda yuklab oladi — qarang `screens/backup/BackupsTab.tsx` namunasi. */
function triggerDownload(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
}

/** SSH orqali avtomatik olib kelish: ulanishni tekshirish → birinchi marta koʻrilgan barmoq izini
 * tasdiqlash (`TrustHostKeyModal`dan nusxa — qarang `screens/backup/SettingsTab.tsx`) → olib kelish. */
function SshTab({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('migration');
  const toast = useToast();
  const form = useSshForm();
  const testM = useTestMigrationSsh();
  const fetchM = useFetchMigrationSsh();
  const [confirmedFp, setConfirmedFp] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ ok: boolean; error?: string } | null>(null);

  const runTest = () => {
    setTestResult(null);
    setConfirmedFp(null);
    testM.mutate(sshTestPayload(form.state), {
      onSuccess: (res) => (res.ok && res.host_key_fp ? setConfirmedFp(res.host_key_fp) : setTestResult(res)),
    });
  };
  const runFetch = (fp: string) => {
    fetchM.mutate(sshFetchPayload(form.state, fp), {
      onError: (e) => toast({ kind: 'error', title: t('source.ssh.fetchFailedToast', { error: apiErrorMessage(e) }) }),
    });
  };

  return (
    <div className="flex max-w-md flex-col gap-4">
      <Field label={t('source.ssh.host')}>{(a) => <Input {...a} disabled={!canManage} mono value={form.state.host} onChange={(e) => form.setHost(e.target.value)} />}</Field>
      <Field label={t('source.ssh.port')}>{(a) => <Input {...a} disabled={!canManage} mono type="number" value={form.state.port} onChange={(e) => form.setPort(Number(e.target.value))} />}</Field>
      <Field label={t('source.ssh.username')}>{(a) => <Input {...a} disabled={!canManage} mono value={form.state.username} onChange={(e) => form.setUsername(e.target.value)} />}</Field>
      <Field label={t('source.ssh.password')}>{(a) => <Input {...a} disabled={!canManage} type="password" value={form.state.password} onChange={(e) => form.setPassword(e.target.value)} />}</Field>
      <Field label={t('source.ssh.privateKey')}>{(a) => <Input {...a} disabled={!canManage} type="password" value={form.state.privateKey} onChange={(e) => form.setPrivateKey(e.target.value)} />}</Field>

      {testResult && !testResult.ok && (
        <p className="flex items-start gap-1.5 text-sm text-danger">
          <ShieldAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />
          {t('source.ssh.testFailed', { error: testResult.error ?? '' })}
        </p>
      )}
      {testResult?.ok && <p className="text-sm text-success">{t('source.ssh.testOk')}</p>}

      <div>
        <Button variant="secondary" disabled={!canManage || !sshTestValid(form.state)} loading={testM.isPending} onClick={runTest}>
          {testM.isPending ? t('source.ssh.testing') : t('source.ssh.test')}
        </Button>
      </div>

      <Modal
        size="sm"
        open={!!confirmedFp}
        onOpenChange={(v) => !v && setConfirmedFp(null)}
        title={t('source.ssh.fingerprintModal.title')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmedFp(null)}>{t('source.ssh.fingerprintModal.cancel')}</Button>
            <Button
              variant="primary" loading={fetchM.isPending}
              onClick={() => confirmedFp && runFetch(confirmedFp)}
            >
              {t('source.ssh.fingerprintModal.confirm')}
            </Button>
          </>
        }
      >
        <p className="flex items-start gap-1.5 text-sm text-fg">
          <ShieldAlert aria-hidden className="mt-0.5 size-3.5 shrink-0 text-warning" />
          {t('source.ssh.fingerprintModal.body', { fp: confirmedFp })}
        </p>
      </Modal>
    </div>
  );
}

/** Toʻplam yuklash: `.tar.gz`/`.tgz` fayl tanlab yuklaydi. */
function UploadTab({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('migration');
  const toast = useToast();
  const uploadM = useUploadMigrationBundle();
  const [file, setFile] = useState<File | null>(null);

  const submit = () => {
    if (!file) return;
    uploadM.mutate(file, {
      onError: (e) => toast({ kind: 'error', title: t('source.upload.failedToast', { error: apiErrorMessage(e) }) }),
    });
  };

  return (
    <div className="flex max-w-md flex-col gap-4">
      <Field label={t('source.upload.label')} hint={t('source.upload.hint')} error={file && !bundleFileValid(file) ? t('source.upload.invalidFile') : undefined}>
        {(a) => (
          <Input
            {...a} type="file" accept=".tar.gz,.tgz" disabled={!canManage}
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        )}
      </Field>
      <div>
        <Button
          variant="primary" icon={<UploadCloud aria-hidden className="size-4" />}
          disabled={!canManage || !bundleFileValid(file)} loading={uploadM.isPending} onClick={submit}
        >
          {uploadM.isPending ? t('source.upload.uploading') : t('source.upload.submit')}
        </Button>
      </div>
    </div>
  );
}

/** FreePBX serverda ishlatiladigan eksport skriptini yuklab olish — buyruq namunasi bilan. */
function ExportScriptBlock() {
  const { t } = useTranslation('migration');
  const toast = useToast();
  const exportM = useMigrationExportScript();
  const download = () => exportM.mutate(undefined, {
    onSuccess: (blob) => triggerDownload(blob, 'innova-fpbx-export.sh'),
  });
  const copy = () => {
    navigator.clipboard?.writeText(t('source.exportScript.command'));
    toast({ kind: 'success', title: t('source.exportScript.copied') });
  };
  return (
    <div className="flex flex-col gap-2 rounded-md border border-line bg-surface-2/50 p-3 text-sm">
      <p className="font-medium text-fg">{t('source.exportScript.title')}</p>
      <p className="text-muted">{t('source.exportScript.body')}</p>
      <div className="flex items-center gap-2">
        <code className="num flex-1 truncate rounded-sm bg-surface px-2 py-1 text-xs">{t('source.exportScript.command')}</code>
        <Button size="sm" variant="ghost" onClick={copy}>{t('source.exportScript.copyButton')}</Button>
      </div>
      <div><Button size="sm" variant="secondary" icon={<Download aria-hidden className="size-3.5" />} onClick={download}>{t('source.exportScript.downloadButton')}</Button></div>
    </div>
  );
}

/** Sehrgarning 1-bosqichi: toʻplam yuklash yoki SSH orqali olib kelish — ikkisi ham bir xil tahlilga oʻtadi. */
export function SourceStep({ canManage }: { canManage: boolean }) {
  const { t } = useTranslation('migration');
  const [tab, setTab] = useState<'upload' | 'ssh'>('upload');
  return (
    <section data-testid="migration-source-step" className="flex flex-col gap-6">
      <div>
        <h2 className="text-lg font-semibold text-fg">{t('source.title')}</h2>
        <p className="mt-1 max-w-xl text-sm text-muted">{t('source.intro')}</p>
      </div>
      <Tabs
        label={t('source.title')}
        value={tab}
        onValueChange={(v) => setTab(v as 'upload' | 'ssh')}
        items={[
          { value: 'upload', label: t('source.uploadTab'), content: <UploadTab canManage={canManage} /> },
          { value: 'ssh', label: t('source.sshTab'), content: <SshTab canManage={canManage} /> },
        ]}
      />
      <ExportScriptBlock />
    </section>
  );
}
