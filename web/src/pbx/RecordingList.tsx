import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Download, FileWarning, LoaderCircle, Pause, Play, Trash2 } from 'lucide-react';
import { apiClient } from '@/api';
import { useDeleteRecording } from '@/api/queries';
import type { CallRecordingRef } from '@/api/types';
import { formatDurationSec } from '@/lib/time';
import { Button } from '@/ui/Button';
import { Modal } from '@/ui/Dialog';
import { useToast } from '@/ui/Toast';

type PlayState = 'idle' | 'loading' | 'playing' | 'paused' | 'error';

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
function RecordingRow({ rec, canDelete }: { rec: CallRecordingRef; canDelete: boolean }) {
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
    a.download = `${rec.id}.wav`;
    a.click();
    URL.revokeObjectURL(url);
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
export function RecordingList({ recordings, canDelete }: { recordings: CallRecordingRef[]; canDelete: boolean }) {
  if (recordings.length === 0) return null;
  return (
    <div className="flex flex-col gap-1.5">
      {recordings.map((rec) => <RecordingRow key={rec.id} rec={rec} canDelete={canDelete} />)}
    </div>
  );
}
