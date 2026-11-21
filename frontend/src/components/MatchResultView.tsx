import type { MatchResult, SkillSource } from '../api/types'
import { cardClass } from './ui'
import ScoreBar from './ScoreBar'
import SkillChips from './SkillChips'

const SOURCE_HINTS: Record<SkillSource, string> = {
  skills_section: 'in skills list',
  experience_text: 'in experience',
}

/** The live result of POST /jobs/match. */
export default function MatchResultView({ result }: { result: MatchResult }) {
  const { job } = result
  const details = [job.seniority, job.employment_type, job.location].filter(Boolean).join(' · ')

  return (
    <section aria-label="Match result" className={`${cardClass} space-y-5`}>
      <div>
        <h3 className="text-lg font-semibold text-slate-900">
          {job.job_title}
          {job.company ? ` at ${job.company}` : ''}
        </h3>
        {details && <p className="text-sm text-slate-500">{details}</p>}
      </div>

      <div>
        <ScoreBar score={result.score} />
        <p className="mt-2 text-xs text-slate-500">
          The score is calculated by code (70% required skills, 30% preferred skills). The AI only wrote
          the suggestions below.
        </p>
      </div>

      <SkillChips
        title="Required skills you have"
        items={result.required.matched.map((hit) => ({
          label: hit.skill,
          hint: SOURCE_HINTS[hit.found_in],
        }))}
        tone="good"
        emptyText="None"
      />
      <SkillChips
        title="Required skills missing"
        items={result.required.missing.map((skill) => ({ label: skill }))}
        tone="bad"
        emptyText="None - every required skill was found."
      />
      <SkillChips
        title="Preferred skills you have"
        items={result.preferred.matched.map((hit) => ({
          label: hit.skill,
          hint: SOURCE_HINTS[hit.found_in],
        }))}
        tone="good"
        emptyText="None"
      />
      <SkillChips
        title="Preferred skills missing"
        items={result.preferred.missing.map((skill) => ({ label: skill }))}
        tone="bad"
        emptyText="None"
      />

      <div>
        <h4 className="text-sm font-medium text-slate-700">Suggestions</h4>
        {result.suggestions.length === 0 ? (
          <p className="mt-1 text-sm text-slate-500">Nothing is missing, so there is nothing to suggest.</p>
        ) : (
          <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm text-slate-700">
            {result.suggestions.map((suggestion, index) => (
              <li key={index}>{suggestion}</li>
            ))}
          </ol>
        )}
      </div>
    </section>
  )
}
