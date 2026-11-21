import type { MatchResult, MatchSnapshotCreate, SkillCategory, SkillEntry } from '../api/types'

function toEntries(skills: string[], category: SkillCategory): SkillEntry[] {
  return skills.map((skill) => ({ skill, category }))
}

/**
 * Turn a match result into the small snapshot the tracker stores.
 * (Same conversion as snapshot_from_match_result in backend/app/services/application_service.py.)
 *
 * What is deliberately NOT copied: the AI's suggestions, the job analysis - and the resume,
 * which this function never even receives. The privacy rule is built into the function's inputs.
 */
export function buildSnapshot(jobDescription: string, match: MatchResult): MatchSnapshotCreate {
  return {
    job_description: jobDescription,
    score: match.score,
    matched_skills: [
      ...toEntries(match.required.matched.map((hit) => hit.skill), 'required'),
      ...toEntries(match.preferred.matched.map((hit) => hit.skill), 'preferred'),
    ],
    missing_skills: [
      ...toEntries(match.required.missing, 'required'),
      ...toEntries(match.preferred.missing, 'preferred'),
    ],
  }
}
