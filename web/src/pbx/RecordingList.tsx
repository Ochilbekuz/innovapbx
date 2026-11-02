import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Download, FileWarning, LoaderCircle, Pause, Play, Trash2 } from 'lucide-react';
import { apiClient } from '@/api';
import { useDeleteRecording } from '@/api/queries';
import type { Call, CallRecordingRef } from '@/api/types';
import { formatDurationSec, TENANT_TZ } from '@/lib/time';
import { Button } from '@/ui/Button';
import { Modal } from '@/ui/Dialog';
import { useToast } from '@/ui/Toast';

type PlayState = 'idle' | 'loading' | 'playing' | 'paused' | 'error';

// `sv-SE` — tilga bogʻliq boʻlmagan «YYYY-MM-DD HH:MM:SS» shakli (fayl nomi interfeys tiliga qarab oʻzgarmasin).
const FILE_STAMP = new Intl.DateTimeFormat('sv-SE', {
  timeZone: TENANT_TZ, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
});
const fileSafeNumber = (n: string) => n.replace(/[^0-9A-Za-z+]/g, '') || 'nomalum';

/** Yuklab olinadigan fayl nomi asosi: `2026-11-03_01-12-35_<kimdan>_<kimga>` (Toshkent vaqti). */
export function recordingFileBase(call: Pick<Call, 'started_at' | 'src' | 'dst'>): string {
  const stamp = FILE_STAMP.format(new Date(call.started_at)).replace(' ', '_').replace(/:/g, '-');
  return `${stamp}_${fileSafeNumber(call.src)}_${fileSafeNumber(call.dst)}`;
}

export function recordingFileName(fileBase: string | undefined, id: string, index: number, total: number): string {
  if (!fileBase) return `${id}.wav`;
  return total > 1 ? `${fileBase}_${index + 1}.wav` : `${fileBase}.wav`;
}

/** Lazy Blob manba — birinchi bosishda bir marta `fetchRecordingAudio` chaqiradi, keyin `<audio>`ga bog'laydi. */
function useRecordingPlayback(id: string) {
  const audio = useRef<HTMLAudioElement>(null);
  const objectUrl = useRef<string | null>(null);
  const [state, setState] = useState<PlayState>('idle');
  useEffect(() => () => { if (objectUrl.current) URL.revokeObjectURL(objectUrl.current); }, []);

  const toggle = async () => {
    const a = audio.current;
    if (!a || state === 'error') return;
    if (!a.paused) { a.pause(); return; }
    setState('loading');
    try {
      if (!objectUrl.current) {
        objectUrl.current = URL.createObjectURL(await apiClient.fetchRecordingAudio(id));
        a.src = objectUrl.current;
      }
      await a.play();
    } catch {
      setState('error');
    }
  };

  return {
    audio, state, toggle,
    events: {
      onPlaying: () => setState('playing'),
      onPause: () => setState('paused'),
      onWaiting: () => setState('loading'),
      onEnded: () => setState('paused'),
      onError: () => setState('error'),
    },
  };
}

function PlayIcon({ state }: { state: PlayState }) {
  if (state === 'loading') return <LoaderCircle className="animate-spin" />;
  if (state === 'error') return <FileWarning />;
  return state === 'playing' ? <Pause /> : <Play className="translate-x-px" />;
}

/** Bitta yozuv qatori — tinglash (inline pleer), yuklab olish va, admin boʻlsa, oʻchirish. M3b §1. */
function RecordingRow({ rec, canDelete, fileName }: { rec: CallRecordingRef; canDelete: boolean; fileName: string }) {
  const { t } = useTranslation('recordings');
  const toast = useToast();
  const deleteM = useDeleteRecording();
  const [confirming, setConfirming] = useState(false);
  const p = useRecordingPlayback(rec.id);
  const playLabel = p.state === 'playing' ? t('pauseAriaLabel') : t('playAriaLabel');

  const download = async () => {
    const blob = await apiClient.fetchRecordingAudio(rec.id);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    a.click();
    // Darhol bekor qilinsa Firefox yuklashni boshlamay qoladi.
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return (
    <div className="flex items-center gap-1.5">
      <audio ref={p.audio} preload="none" {...p.events} />
      <Button
        size="sm" variant="secondary" iconOnly
        data-testid={`recording-play-${rec.id}`}
        aria-label={playLabel}
        disabled={p.state === 'error'}
        icon={<PlayIcon state={p.state} />}
        onClick={() => void p.toggle()}
      />
      {p.state === 'error' ? (
        <span className="text-sm text-danger">{t('unplayable')}</span>
      ) : (
        <span className="num text-xs text-muted">{formatDurationSec(rec.duration_s)}</span>
      )}
      <Button
        size="sm" variant="ghost" iconOnly
        data-testid={`recording-download-${rec.id}`}
        aria-label={t('downloadAriaLabel')}
        icon={<Download />}
        onClick={() => void download()}
      />
      {canDelete && (
        <>
          <Button
            size="sm" variant="danger-ghost" iconOnly
            aria-label={t('deleteAriaLabel')}
            icon={<Trash2 />}
            onClick={() => setConfirming(true)}
          />
          <Modal
            open={confirming}
            onOpenChange={setConfirming}
            title={t('deleteConfirmTitle')}
            footer={
              <>
                <Button variant="ghost" onClick={() => setConfirming(false)}>{t('cancel')}</Button>
                <Button
                  variant="danger" loading={deleteM.isPending}
                  onClick={() => deleteM.mutate(rec.id, {
                    onSuccess: () => { toast({ kind: 'success', title: t('deletedToast') }); setConfirming(false); },
                    onError: (e) => { toast({ kind: 'error', title: t('deleteFailedToast'), description: e.message }); setConfirming(false); },
                  })}
                >
                  {t('confirm')}
                </Button>
              </>
            }
          >
            <p className="text-sm text-muted">{t('deleteConfirmBody')}</p>
          </Modal>
        </>
      )}
    </div>
  );
}

/** Qoʻngʻiroqqa bogʻlangan yozuvlar roʻyxati — boʻlmasa hech narsa chiqarmaydi (jadval qatorida joy band qilmaydi). */
export function RecordingList({ recordings, canDelete, fileBase }: { recordings: CallRecordingRef[]; canDelete: boolean; fileBase?: string }) {
  if (recordings.length === 0) return null;
  return (
    <div className="flex flex-col gap-1.5">
      {recordings.map((rec, i) => (
        <RecordingRow key={rec.id} rec={rec} canDelete={canDelete} fileName={recordingFileName(fileBase, rec.id, i, recordings.length)} />
      ))}
    </div>
  );
}
