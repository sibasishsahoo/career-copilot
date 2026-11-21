import { ApiError } from '../api/client'
import type { PrepCoverage } from '../api/types'

export const QUESTION_COUNT_OPTIONS = [5, 8, 10] as const
export const DEFAULT_QUESTION_COUNT = 8

export const CATEGORY_LABELS: Record<string, string> = {
  behavioral: 'Behavioral',
  technical: 'Technical',
  role: 'Role',
  gap: 'Skill gap',
}

// Full class names so Tailwind can find them.
export const CATEGORY_STYLES: Record<string, string> = {
  behavioral: 'bg-violet-100 text-violet-800 ring-violet-300',
  technical: 'bg-sky-100 text-sky-800 ring-sky-300',
  role: 'bg-teal-100 text-teal-800 ring-teal-300',
  gap: 'bg-amber-100 text-amber-800 ring-amber-300',
}
const FALLBACK_STYLE = 'bg-slate-100 text-slate-700 ring-slate-300'

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? (category ? category[0].toUpperCase() + category.slice(1) : 'Other')
}

export function categoryStyle(category: string): string {
  return CATEGORY_STYLES[category] ?? FALLBACK_STYLE
}

export function coveragePercent(coverage: PrepCoverage): number {
  return coverage.total === 0 ? 0 : Math.round((coverage.with_story / coverage.total) * 100)
}

export function coverageSummary(coverage: PrepCoverage): string {
  if (coverage.total === 0) return 'No questions yet.'
  if (coverage.with_story === 0) return `None of the ${coverage.total} questions has a matching story in your notes yet.`
  if (coverage.with_story === coverage.total) return `All ${coverage.total} questions have a matching story in your notes.`
  return `${coverage.with_story} of ${coverage.total} questions have a matching story in your notes.`
}

/** "#3", "#3 and #5", "#3, #5 and #7" */
export function listQuestionNumbers(numbers: number[]): string {
  const labels = numbers.map((number) => `#${number}`)
  if (labels.length <= 1) return labels.join('')
  return `${labels.slice(0, -1).join(', ')} and ${labels[labels.length - 1]}`
}

/** What to do about the gaps, in one sentence ('' when there are none). */
export function missingStoriesAdvice(coverage: PrepCoverage): string {
  if (coverage.without_story.length === 0) return ''
  const noun = coverage.without_story.length === 1 ? 'question' : 'questions'
  return `Write a note about your experience for ${noun} ${listQuestionNumbers(coverage.without_story)} in the Notes tab, then regenerate.`
}

export function isNotFound(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404
}

export function isNoSavedMatch(error: unknown): boolean {
  return error instanceof ApiError && error.status === 409
}
