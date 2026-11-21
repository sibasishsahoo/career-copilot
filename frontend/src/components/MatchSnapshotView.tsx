import type { MatchSnapshot, SkillCategory, SkillEntry } from '../api/types'
import { formatDateTime } from '../lib/format'
import ScoreBar from './ScoreBar'
import type { SkillChip } from './SkillChips'
import SkillChips from './SkillChips'

function chipsFor(entries: SkillEntry[], category: SkillCategory): SkillChip[] {
  return entries.filter((entry) => entry.category === category).map((entry) => ({ label: entry.skill }))
}

/** Shows a match that was saved on an application (see the Match tool page). */
export default function MatchSnapshotView({ snapshot }: { snapshot: MatchSnapshot }) {
  return (
    <div className="space-y-4">
      <ScoreBar score={snapshot.score} />
      <SkillChips
        title="Required skills you have"
        items={chipsFor(snapshot.matched_skills, 'required')}
        tone="good"
        emptyText="None"
      />
      <SkillChips
        title="Required skills missing"
        items={chipsFor(snapshot.missing_skills, 'required')}
        tone="bad"
        emptyText="None - every required skill was found."
      />
      <SkillChips
        title="Preferred skills you have"
        items={chipsFor(snapshot.matched_skills, 'preferred')}
        tone="good"
        emptyText="None"
      />
      <SkillChips
        title="Preferred skills missing"
        items={chipsFor(snapshot.missing_skills, 'preferred')}
        tone="bad"
        emptyText="None"
      />
      <details className="rounded-md border border-slate-200 p-3 text-sm">
        <summary className="cursor-pointer font-medium text-slate-700">Saved job description</summary>
        <p className="mt-2 whitespace-pre-wrap text-slate-600">{snapshot.job_description}</p>
      </details>
      <p className="text-xs text-slate-500">Saved {formatDateTime(snapshot.attached_at)}</p>
    </div>
  )
}
