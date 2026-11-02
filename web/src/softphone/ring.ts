// M3a §4 — kiruvchi qo'ng'iroq ovozi, WebAudio bilan (audio fayl kerak emas). Ikki tonli signal (425/450 Hz
// atrofida, O'zbekiston/Yevropa uslubidagi "burr-burr"), 1s yoqilgan / 3s o'chirilgan — standart ring cadence.

type RingHandle = { stop: () => void };

/** Jiringlash boshlaydi; qaytgan `stop()` chaqirilmaguncha davom etadi (`setInterval` bilan takrorlanadi). */
export function startRingtone(): RingHandle {
  const AudioCtor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioCtor) return { stop: () => undefined };
  const ctx = new AudioCtor();

  function beep(startAt: number, durationS: number) {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.value = 440;
    gain.gain.setValueAtTime(0.0001, startAt);
    gain.gain.exponentialRampToValueAtTime(0.18, startAt + 0.02);
    gain.gain.setValueAtTime(0.18, startAt + durationS - 0.05);
    gain.gain.exponentialRampToValueAtTime(0.0001, startAt + durationS);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(startAt);
    osc.stop(startAt + durationS);
  }

  function cycle() {
    const now = ctx.currentTime;
    beep(now, 0.4);
    beep(now + 0.5, 0.4);
  }

  cycle();
  const timer = window.setInterval(cycle, 3000);
  return {
    stop: () => {
      window.clearInterval(timer);
      void ctx.close().catch(() => undefined);
    },
  };
}
