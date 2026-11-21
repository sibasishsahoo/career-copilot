import { describe, expect, it } from 'vitest'
import { ApiError } from '../api/client'
import {
  CATEGORY_LABELS,
  DEFAULT_QUESTION_COUNT,
  QUESTION_COUNT_OPTIONS,
  categoryLabel,
  categoryStyle,
  coveragePercent,
  coverageSummary,
  isNoSavedMatch,
  isNotFound,
  listQuestionNumbers,
  missingStoriesAdvice,
} from './interview'

const coverage = (total: number, withStory: number, without: number[] = []) => ({ total, with_story: withStory, without_story: without })

describe('categories', () => {
  it('labels the four known categories', () => {
    expect(categoryLabel('behavioral')).toBe('Behavioral')
    expect(categoryLabel('technical')).toBe('Technical')
    expect(categoryLabel('role')).toBe('Role')
    expect(categoryLabel('gap')).toBe('Skill gap')
  })

  it('copes with unknown categories', () => {
    expect(categoryLabel('culture')).toBe('Culture')
    expect(categoryLabel('')).toBe('Other')
  })

  it('has a style for every known category and a fallback', () => {
    for (const category of Object.keys(CATEGORY_LABELS)) expect(categoryStyle(category).length > 0).toBe(true)
    expect(categoryStyle('culture')).toContain('slate')
  })
})

describe('coverage', () => {
  it('computes a rounded percentage', () => {
    expect(coveragePercent(coverage(8, 5))).toBe(63)
    expect(coveragePercent(coverage(3, 3))).toBe(100)
    expect(coveragePercent(coverage(3, 0))).toBe(0)
    expect(coveragePercent(coverage(0, 0))).toBe(0)
  })

  it('summarizes the four situations in words', () => {
    expect(coverageSummary(coverage(0, 0))).toBe('No questions yet.')
    expect(coverageSummary(coverage(8, 0))).toBe('None of the 8 questions has a matching story in your notes yet.')
    expect(coverageSummary(coverage(8, 8))).toBe('All 8 questions have a matching story in your notes.')
    expect(coverageSummary(coverage(8, 5))).toBe('5 of 8 questions have a matching story in your notes.')
  })

  it('lists question numbers naturally', () => {
    expect(listQuestionNumbers([])).toBe('')
    expect(listQuestionNumbers([3])).toBe('#3')
    expect(listQuestionNumbers([3, 5])).toBe('#3 and #5')
    expect(listQuestionNumbers([3, 5, 7])).toBe('#3, #5 and #7')
  })

  it('gives advice only when something is missing', () => {
    expect(missingStoriesAdvice(coverage(2, 2))).toBe('')
    expect(missingStoriesAdvice(coverage(2, 1, [2]))).toBe(
      'Write a note about your experience for question #2 in the Notes tab, then regenerate.',
    )
    expect(missingStoriesAdvice(coverage(8, 5, [3, 5, 7]))).toBe(
      'Write a note about your experience for questions #3, #5 and #7 in the Notes tab, then regenerate.',
    )
  })
})

describe('error helpers', () => {
  it('recognizes 404 and 409 API errors only', () => {
    expect(isNotFound(new ApiError(404, 'x'))).toBe(true)
    expect(isNotFound(new ApiError(409, 'x'))).toBe(false)
    expect(isNoSavedMatch(new ApiError(409, 'x'))).toBe(true)
    expect(isNoSavedMatch(new ApiError(404, 'x'))).toBe(false)
  })

  it('ignores anything that is not an ApiError', () => {
    expect(isNotFound(new Error('404'))).toBe(false)
    expect(isNoSavedMatch('409')).toBe(false)
    expect(isNotFound(undefined)).toBe(false)
  })
})

describe('question count options', () => {
  it('include the default', () => {
    expect((QUESTION_COUNT_OPTIONS as readonly number[]).includes(DEFAULT_QUESTION_COUNT)).toBe(true)
  })
})
