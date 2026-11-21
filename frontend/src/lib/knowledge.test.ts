import { describe, expect, it } from 'vitest'
import { MAX_NOTE_CHARS, MAX_QUESTION_CHARS, formatScore, splitCitations, validateNote, validateQuestion } from './knowledge'

describe('validateNote', () => {
  it('accepts a note with a title and text', () => {
    expect(validateNote({ title: 'Faster deploys', text: 'I cut deploys to 12 minutes.' })).toEqual({})
  })

  it('requires a title and text', () => {
    expect(validateNote({ title: '', text: 'x' }).title).toBe('Title is required.')
    expect(validateNote({ title: 'x', text: '' }).text).toBe('Note text is required.')
  })

  it('treats whitespace-only fields as empty', () => {
    const errors = validateNote({ title: '   ', text: ' \n\t ' })
    expect(errors.title).toBe('Title is required.')
    expect(errors.text).toBe('Note text is required.')
  })

  it('rejects an overlong title and an overlong text', () => {
    expect(validateNote({ title: 't'.repeat(201), text: 'x' }).title).toContain('200')
    expect(validateNote({ title: 'x', text: 'n'.repeat(MAX_NOTE_CHARS + 1) }).text).toContain('50,000')
  })

  it('accepts the exact limits', () => {
    expect(validateNote({ title: 't'.repeat(200), text: 'n'.repeat(MAX_NOTE_CHARS) })).toEqual({})
  })

  it('reports both problems at once', () => {
    expect(Object.keys(validateNote({ title: '', text: '' })).sort()).toEqual(['text', 'title'])
  })
})

describe('validateQuestion', () => {
  it('accepts normal text', () => {
    expect(validateQuestion('Which story shows leadership?')).toBeNull()
  })

  it('rejects empty and blank text', () => {
    expect(validateQuestion('')).toBe('Please type something first.')
    expect(validateQuestion('   ')).toBe('Please type something first.')
  })

  it('rejects text over the limit and accepts exactly the limit', () => {
    expect(validateQuestion('q'.repeat(MAX_QUESTION_CHARS + 1))).toContain('500')
    expect(validateQuestion('q'.repeat(MAX_QUESTION_CHARS))).toBeNull()
  })
})

describe('formatScore', () => {
  it('shows two decimals', () => {
    expect(formatScore(0.5)).toBe('0.50')
    expect(formatScore(0.12345)).toBe('0.12')
    expect(formatScore(1)).toBe('1.00')
    expect(formatScore(0)).toBe('0.00')
  })
})

describe('splitCitations', () => {
  it('returns one text part when there are no citations', () => {
    expect(splitCitations('Plain answer.')).toEqual([{ type: 'text', text: 'Plain answer.' }])
  })

  it('splits text around a citation', () => {
    expect(splitCitations('I cut it to 12 minutes [1] last year.')).toEqual([
      { type: 'text', text: 'I cut it to 12 minutes ' },
      { type: 'citation', number: 1 },
      { type: 'text', text: ' last year.' },
    ])
  })

  it('handles adjacent citations without empty text parts', () => {
    expect(splitCitations('Facts [1][2].')).toEqual([
      { type: 'text', text: 'Facts ' },
      { type: 'citation', number: 1 },
      { type: 'citation', number: 2 },
      { type: 'text', text: '.' },
    ])
  })

  it('handles a citation at the very start or end', () => {
    expect(splitCitations('[3] first')).toEqual([
      { type: 'citation', number: 3 },
      { type: 'text', text: ' first' },
    ])
    expect(splitCitations('last [4]')).toEqual([
      { type: 'text', text: 'last ' },
      { type: 'citation', number: 4 },
    ])
  })

  it('reads multi-digit numbers', () => {
    expect(splitCitations('See [12].')[1]).toEqual({ type: 'citation', number: 12 })
  })

  it('leaves brackets that are not citations alone', () => {
    expect(splitCitations('Use [a] and [] and [1x] here.')).toEqual([
      { type: 'text', text: 'Use [a] and [] and [1x] here.' },
    ])
  })

  it('returns nothing for an empty answer', () => {
    expect(splitCitations('')).toEqual([])
  })
})
