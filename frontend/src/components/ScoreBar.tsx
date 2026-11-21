import { SCORE_BAR_STYLES, SCORE_LABELS, scoreTone } from '../lib/score'

export default function ScoreBar({ score }: { score: number }) {
  const tone = scoreTone(score)
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-2xl font-bold text-slate-900">{`${score}/100`}</span>
        <span className="text-sm font-medium text-slate-600">{SCORE_LABELS[tone]}</span>
      </div>
      <div
        role="progressbar"
        aria-label="Match score"
        aria-valuenow={score}
        aria-valuemin={0}
        aria-valuemax={100}
        className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-200"
      >
        <div className={`h-full rounded-full ${SCORE_BAR_STYLES[tone]}`} style={{ width: `${score}%` }} />
      </div>
    </div>
  )
}
