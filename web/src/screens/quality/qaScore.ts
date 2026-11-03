import type { Tone } from '@/ui/Status';

/** M10 C B1 — baholash ball foizi uchun bitta umumiy rang chizig'i (MePage/CallsPage/QualityPage/EvaluationDrawer). */
export function scoreTone(pct: number): Tone {
  if (pct >= 80) return 'success';
  if (pct >= 50) return 'warning';
  return 'danger';
}
