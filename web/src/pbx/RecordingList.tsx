import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Download, Trash2 } from 'lucide-react';
import { apiClient } from '@/api';
import { useDeleteRecording } from '@/api/queries';
import type { Call, CallRecordingRef } from '@/api/types';
import { formatDurationSec, tenantTz } from '@/lib/time';
import { fmt, playIcon, RateButton, usePlayback } from '@/pbx/AudioPlayer';
import { Button } from '@/ui/Button';
import { Modal } from '@/ui/Dialog';
import { useToast } from '@/ui/Toast';

// `sv-SE` — tilga bogʻliq boʻlmagan «YYYY-MM-DD HH:MM:SS» shakli (fayl nomi interfeys tiliga qarab oʻzgarmasin).
// Har chaqiruvda qayta tuziladi (modul yuklanganda emas) — tenant zonasi keyinroq o'zgarsa ham to'g'ri bo'lishi uchun.
function fileStamp(): Intl.DateTimeFormat {
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: tenantTz(), year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}
const fileSafeNumber = (n: string) => n.replace(/[^0-9A-Za-z+]/g, '') || 'nomalum';

/** Yuklab olinadigan fayl nomi asosi: `2026-11-03_01-12-35_<kimdan>_<kimga>` (tenant vaqt zonasida). */
export function recordingFileBase(call: Pick<Call, 'started_at' | 'src' | 'dst'>): string {
  const stamp = fileStamp().format(new Date(call.started_at)).replace(' ', '_').replace(/:/g, '-');
  return `${stamp}_${fileSafeNumber(call.src)}_${fileSafeNumber(call.dst)}`;
}

export function recordingFileName(fileBase: string | undefined, id: string, index: number, total: number): string {
  if (!fileBase) return `${id}.wav`;
  return total > 1 ? `${fileBase}_${index + 1}.wav` : `${fileBase}.wav`;
}

/** Jadval qatoridagi ixcham oʻrin chizigʻi — sudrab yoki bosib istalgan joydan tinglash.
 * Hali ijro boshlanmagan boʻlsa — tanlangan joydan boshlaydi (davomiylik serverdagi `duration_s`dan). */
function SeekBar({ p, durationS, id }: { p: ReturnType<typeof usePlayback>; durationS: number; id: string }) {
  const { t } = useTranslation('common');
  const max = p.dur || durationS;
  return (
    <input
      type="range" min={0} max={max || 0} step="any" value={Math.min(p.t, max)}
      data-testid={`recording-seek-${id}`}
      aria-label={t('audioPlayer.positionDefault')}
      aria-valuetext={`${fmt(p.t)} / ${fmt(max)}`}
      disabled={!max}
      onChange={(e) => {
        const to = Number(e.target.value);
        if (p.state === 'idle') void p.toggle(to); else p.seek(to);
      }}
      className="h-1.5 w-28 shrink-0 cursor-pointer accent-brand disabled:cursor-default"
    />
  );
}

/** Bitta yozuv qatori — tinglash (inline pleer), yuklab olish va, admin boʻlsa, oʻchirish. M3b §1. */
function RecordingRow({ rec, canDelete, fileName }: { rec: CallRecordingRef; canDelete: boolean; fileName: string }) {
  const { t } = useTranslation('recordings');
  const toast = useToast();
  const deleteM = useDeleteRecording();
  const [confirming, setConfirming] = useState(false);
  const p = usePlayback(() => apiClient.fetchRecordingAudio(rec.id));
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
        icon={playIcon(p.state)}
        onClick={() => void p.toggle()}
      />
      {p.state === 'error' ? (
        <span className="text-sm text-danger">{t('unplayable')}</span>
      ) : (
        <>
          <SeekBar p={p} durationS={rec.duration_s} id={rec.id} />
          <span className="num w-[76px] shrink-0 text-xs text-muted" data-testid={`recording-time-${rec.id}`}>
            {p.state === 'idle' ? formatDurationSec(rec.duration_s) : `${fmt(p.t)} / ${fmt(p.dur || rec.duration_s)}`}
          </span>
          <RateButton rate={p.rate} nextRate={p.nextRate} />
        </>
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
