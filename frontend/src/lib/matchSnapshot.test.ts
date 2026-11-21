import { describe, expect, it } from 'vitest'
import { makeMatchResult } from '../test/factories'
import { buildSnapshot } from './matchSnapshot'

describe('buildSnapshot', () => {
  it('converts a match result into the snapshot the tracker stores', () => {
    const snapshot = buildSnapshot('The job posting text.', makeMatchResult())
    expect(snapshot).toEqual({
      job_description: 'The job posting text.',
      score: 47,
      matched_skills: [
        { skill: 'Python', category: 'required' },
        { skill: 'SQL', category: 'required' },
      ],
      missing_skills: [
        { skill: 'REST APIs', category: 'required' },
        { skill: 'Docker', category: 'preferred' },
        { skill: 'AWS', category: 'preferred' },
      ],
    })
  })

  it('keeps matched preferred skills in the matched list', () => {
    const result = makeMatchResult({
      preferred: { matched: [{ skill: 'Docker', found_in: 'skills_section' }], missing: ['AWS'] },
    })
    const snapshot = buildSnapshot('text', result)
    expect(snapshot.matched_skills).toContainEqual({ skill: 'Docker', category: 'preferred' })
    expect(snapshot.missing_skills).toContainEqual({ skill: 'AWS', category: 'preferred' })
  })

  it('contains exactly the four agreed fields - no suggestions, no resume', () => {
    const snapshot = buildSnapshot('text', makeMatchResult())
    expect(Object.keys(snapshot).sort()).toEqual(['job_description', 'matched_skills', 'missing_skills', 'score'])
  })

  it('handles a perfect match with nothing missing', () => {
    const snapshot = buildSnapshot(
      'text',
      makeMatchResult({
        score: 100,
        required: { matched: [{ skill: 'Python', found_in: 'skills_section' }], missing: [] },
        preferred: { matched: [], missing: [] },
        suggestions: [],
      }),
    )
    expect(snapshot.missing_skills).toEqual([])
    expect(snapshot.score).toBe(100)
  })
})
