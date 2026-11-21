import type { InterviewPrep, PrepItem } from '../api/types'
import { categoryLabel, categoryStyle, coveragePercent, coverageSummary, missingStoriesAdvice } from '../lib/interview'
import { formatDateTime } from '../lib/format'
import { cardClass } from './ui'

function CategoryBadge({ category }: { category: string }) {
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${categoryStyle(category)}`}>
      {categoryLabel(category)}
    </span>
  )
}

function Item({ item }: { item: PrepItem }) {
  return (
    <li className="space-y-2 rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-slate-500">{`#${item.number}`}</span>
        <CategoryBadge category={item.category} />
        {item.skill && <span className="text-xs text-slate-500">{`about ${item.skill}`}</span>}
      </div>
      <h4 className="font-semibold text-slate-900">{item.question}</h4>
      {item.why_asked && <p className="text-sm text-slate-500">{`Why it is asked: ${item.why_asked}`}</p>}

      {item.story_found ? (
        <div className="space-y-2 rounded-md bg-emerald-50 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-emerald-800">Your answer outline</p>
          <p className="whitespace-pre-wrap text-sm text-slate-800">{item.answer_outline}</p>
          <ul aria-label={`Notes used for question ${item.number}`} className="flex flex-wrap gap-2">
            {item.sources.map((source) => (
              <li key={source} className="rounded-full bg-white px-2.5 py-0.5 text-xs text-emerald-800 ring-1 ring-inset ring-emerald-300">
                {source}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div role="note" className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-semibold">No story found</p>
          <p>{item.note}</p>
        </div>
      )}
    </li>
  )
}

/** A generated interview prep pack. Presentational only: the page decides what buttons go around it. */
export default function InterviewPrepView({ prep }: { prep: InterviewPrep }) {
  const advice = missingStoriesAdvice(prep.coverage)
  return (
    <div className="space-y-6">
      <section aria-label="Story coverage" className={`${cardClass} space-y-2`}>
        <h3 className="text-lg font-semibold text-slate-900">Story coverage</h3>
        <p className="text-sm text-slate-700">{coverageSummary(prep.coverage)}</p>
        <div
          role="progressbar"
          aria-label="Story coverage"
          aria-valuenow={coveragePercent(prep.coverage)}
          aria-valuemin={0}
          aria-valuemax={100}
          className="h-2 w-full overflow-hidden rounded-full bg-slate-200"
        >
          <div className="h-full rounded-full bg-emerald-500" style={{ width: `${coveragePercent(prep.coverage)}%` }} />
        </div>
        {advice && <p className="text-sm text-amber-800">{advice}</p>}
        <p className="text-xs text-slate-400">{`Generated ${formatDateTime(prep.generated_at)} for ${prep.job_title} at ${prep.company}`}</p>
      </section>

      <ol aria-label="Interview questions" className="space-y-4">
        {prep.items.map((item) => (
          <Item key={item.number} item={item} />
        ))}
      </ol>

      {prep.questions_to_ask.length > 0 && (
        <section aria-label="Questions to ask" className={`${cardClass} space-y-2`}>
          <h3 className="text-lg font-semibold text-slate-900">Questions to ask the interviewer</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
            {prep.questions_to_ask.map((question) => (
              <li key={question}>{question}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
