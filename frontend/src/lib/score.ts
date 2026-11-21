export type ScoreTone = 'strong' | 'moderate' | 'low'

export function scoreTone(score: number): ScoreTone {
  if (score >= 75) return 'strong'
  if (score >= 50) return 'moderate'
  return 'low'
}

export const SCORE_LABELS: Record<ScoreTone, string> = {
  strong: 'Strong match',
  moderate: 'Moderate match',
  low: 'Low match',
}

// Full class names written out so Tailwind can find them.
export const SCORE_BAR_STYLES: Record<ScoreTone, string> = {
  strong: 'bg-emerald-500',
  moderate: 'bg-amber-500',
  low: 'bg-red-500',
}
