import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';
import { useBackupJob, useRestoreBackup } from '@/api/queries';
import { isApiError } from '@/api/errors';
import { useSession } from '@/api/session';
import { Button } from '@/ui/Button';
import { Modal } from '@/ui/Dialog';
import { Field, Input } from '@/ui/Field';
import { useToast } from '@/ui/Toast';
import { restoreConfirmValid, restorePayload } from './backupForms';
import { JobProgressBody } from './Progress';

export type RestoreTarget = { id: string; fileName: string };

type Phase = 'confirm' | 'force' | 'running';
type Translate = (k: string, o?: Record<string, unknown>) => string;

/** `restoreM.error`dan `active_calls` 409'ining `details.count`'ini ajratib oladi. */
function activeCallCountFromError(error: unknown): number | undefined {
  return isApiError(error) ? (error.details?.count as number | undefined) : undefined;
}

/** Tiklashni boshlash (kuchlab yoki oddiy) — muvaffaqiyatda progress bosqichiga, 409
 * `active_calls`'da kuchlab tasdiqlash bosqichiga oʻtkazadi, boshqa xatoda toast chiqaradi. */
function makeRestoreStart(
  restoreM: ReturnType<typeof useRestoreBackup>,
  target: RestoreTarget,
  passphrase: string,
  setPhase: (p: Phase) => void,
  setJobId: (id: string) => void,
  toast: ReturnType<typeof useToast>,
  t: Translate,
) {
  return (force: boolean) => {
    restoreM.mutate({ id: target.id, payload: restorePayload(passphrase, force) }, {
      onSuccess: (res) => { setPhase('running'); setJobId(res.job.id); },
      onError: (e) => {
        if (isApiError(e) && e.code === 'active_calls') setPhase('force');
        else toast({ kind: 'error', title: t('restore.failedToast', { error: isApiError(e) ? e.message : '' }) });
      },
    });
  };
}

/** Progress bosqichi — login sahifasiga qaytarilguncha yopib boʻlmaydi. */
function RunningModal({ title, jobData }: { title: string; jobData?: { progress: number | null; step: string | null } }) {
  return (
    <Modal open title={title} onAttemptClose={() => false}>
      <div className="flex flex-col gap-3">
        <JobProgressBody label={title} jobData={jobData} />
      </div>
    </Modal>
  );
}

/** Faol qoʻngʻiroqlar bor (409 `active_calls`) — kuchlab tiklashni tasdiqlash. */
function ActiveCallsModal({
  count, pending, onCancel, onConfirm, t,
}: { count: number | undefined; pending: boolean; onCancel: () => void; onConfirm: () => void; t: Translate }) {
  return (
    <Modal
      open
      title={t('restore.activeCallsModal.title')}
      onOpenChange={(v) => !v && onCancel()}
      footer={
        <>
          <Button variant="ghost" onClick={onCancel}>{t('restore.activeCallsModal.cancel')}</Button>
          <Button variant="danger" loading={pending} onClick={onConfirm}>{t('restore.activeCallsModal.confirmAnyway')}</Button>
        </>
      }
    >
      <p className="text-sm text-muted">{t('restore.activeCallsModal.body', { count: count ?? '' })}</p>
    </Modal>
  );
}

/** «TIKLASH» yozib tasdiqlash + ixtiyoriy parol. */
function ConfirmModal({
  fileName, passphrase, setPassphrase, confirmText, setConfirmText, pending, onClose, onSubmit, t,
}: {
  fileName: string; passphrase: string; setPassphrase: (v: string) => void; confirmText: string; setConfirmText: (v: string) => void;
  pending: boolean; onClose: () => void; onSubmit: () => void; t: Translate;
}) {
  return (
    <Modal
      open
      onOpenChange={(v) => !v && onClose()}
      title={t('restore.confirmModal.title')}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>{t('cancel')}</Button>
          <Button variant="danger" loading={pending} disabled={!restoreConfirmValid(confirmText)} onClick={onSubmit}>
            {t('restore.confirmModal.submit')}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <p className="flex items-start gap-1.5 text-sm text-danger">
          <ShieldAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />
          {t('restore.confirmModal.body', { file: fileName })}
        </p>
        <Field label={t('restore.passphraseLabel')} hint={t('restore.passphraseHint')}>
          {(a) => <Input {...a} type="password" value={passphrase} onChange={(e) => setPassphrase(e.target.value)} />}
        </Field>
        <Field label={t('restore.confirmModal.typeLabel')}>
          {(a) => (
            <Input
              {...a} mono placeholder={t('restore.confirmModal.typePlaceholder')}
              value={confirmText} onChange={(e) => setConfirmText(e.target.value)}
            />
          )}
        </Field>
      </div>
    </Modal>
  );
}

/**
 * Tiklashni tasdiqlash → faol qoʻngʻiroq 409'ini kuchlab tasdiqlash → progress → sessiyani
 * bekor qilib login sahifasiga qaytarish. Roʻyxatdagi «Tiklash» (`BackupsTab`) va «Fayldan
 * tiklash»ning inspect-dan keyingi bosqichi (`RestoreTab`) — ikkisi ham shu komponentni ishlatadi.
 */
export function RestoreRunner({
  target, onClose, initialPassphrase,
}: { target: RestoreTarget | null; onClose: () => void; initialPassphrase?: string }) {
  const { t } = useTranslation('backup');
  const toast = useToast();
  const navigate = useNavigate();
  const clearSession = useSession((s) => s.clear);
  const restoreM = useRestoreBackup();
  const [phase, setPhase] = useState<Phase>('confirm');
  const [passphrase, setPassphrase] = useState('');
  const [confirmText, setConfirmText] = useState('');
  const [jobId, setJobId] = useState<string | null>(null);
  const jobQ = useBackupJob(jobId);

  useEffect(() => {
    setPhase('confirm');
    setPassphrase(initialPassphrase ?? '');
    setConfirmText('');
    setJobId(null);
    restoreM.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target?.id]);

  useRestoreCompletionEffect(jobQ.data?.status, jobQ.data?.error, clearSession, navigate, toast, onClose, t);

  if (!target) return null;

  const start = makeRestoreStart(restoreM, target, passphrase, setPhase, setJobId, toast, t);

  if (phase === 'running') return <RunningModal title={t('restore.progressTitle')} jobData={jobQ.data} />;

  if (phase === 'force') {
    return (
      <ActiveCallsModal
        count={activeCallCountFromError(restoreM.error)} pending={restoreM.isPending}
        onCancel={() => setPhase('confirm')} onConfirm={() => start(true)} t={t}
      />
    );
  }

  return (
    <ConfirmModal
      fileName={target.fileName} passphrase={passphrase} setPassphrase={setPassphrase}
      confirmText={confirmText} setConfirmText={setConfirmText} pending={restoreM.isPending}
      onClose={onClose} onSubmit={() => start(false)} t={t}
    />
  );
}

/** Tiklash ishi tugaganda (ok/failed) sessiyani tozalab login sahifasiga oʻtish yoki xato toastini chiqarish. */
function useRestoreCompletionEffect(
  status: string | undefined,
  error: string | null | undefined,
  clearSession: (notice?: string) => void,
  navigate: ReturnType<typeof useNavigate>,
  toast: ReturnType<typeof useToast>,
  onClose: () => void,
  t: Translate,
) {
  useEffect(() => {
    if (status === 'ok') {
      // Xabar store'da: clear() RequireAuth'ni qayta chizib, state'siz /login'ga yo'naltirishi mumkin.
      clearSession(t('auth:restoredNotice'));
      navigate('/login', { replace: true });
    } else if (status === 'failed') {
      toast({ kind: 'error', title: t('restore.failedToast', { error: error ?? '' }) });
      onClose();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);
}
