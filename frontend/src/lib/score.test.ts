import { describe, expect, it } from 'vitest'
import { SCORE_BAR_STYLES, SCORE_LABELS, scoreTone } from './score'

describe('scoreTone', () => {
  it('is strong from 75 upwards', () => {
    expect(scoreTone(75)).toBe('strong')
    expect(scoreTone(100)).toBe('strong')
  })

  it('is moderate from 50 to 74', () => {
    expect(scoreTone(74)).toBe('moderate')
    expect(scoreTone(50)).toBe('moderate')
  })

  it('is low below 50', () => {
    expect(scoreTone(49)).toBe('low')
    expect(scoreTone(0)).toBe('low')
  })
})

describe('score tables', () => {
  it('has a label and a bar colour for every tone', () => {
    for (const tone of ['strong', 'moderate', 'low'] as const) {
      expect(SCORE_LABELS[tone].length > 0).toBe(true)
      expect(SCORE_BAR_STYLES[tone].length > 0).toBe(true)
    }
  })
})
