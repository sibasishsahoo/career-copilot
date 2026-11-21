import { describe, expect, it } from 'vitest'
import { EXAMPLE_QUESTIONS, formatArguments, prettyObservation, stepCountText } from './agent'

describe('formatArguments', () => {
  it('says so when there are none', () => {
    expect(formatArguments({})).toBe('no arguments')
  })

  it('formats values as JSON so strings are quoted', () => {
    expect(formatArguments({ status: 'applied', limit: 3 })).toBe('status: "applied", limit: 3')
  })

  it('handles booleans, null and nested values', () => {
    expect(formatArguments({ flag: true, none: null, list: [1, 2] })).toBe('flag: true, none: null, list: [1,2]')
  })
})

describe('prettyObservation', () => {
  it('indents JSON results', () => {
    expect(prettyObservation('{"count":1}')).toBe('{\n  "count": 1\n}')
  })

  it('shows error messages and other non-JSON text as they are', () => {
    expect(prettyObservation('Error: Application 9 was not found.')).toBe('Error: Application 9 was not found.')
  })

  it('shows a cut-off result (invalid JSON) as it is', () => {
    expect(prettyObservation('{"matches":[{"text":"abc... [truncated: the result was too long]')).toContain('[truncated')
  })

  it('shortens very long results and says how much was cut', () => {
    const shown = prettyObservation('x'.repeat(5000), 100)
    expect(shown.startsWith('x'.repeat(100))).toBe(true)
    expect(shown).toContain('4900 more characters')
  })
})

describe('stepCountText', () => {
  it('describes zero, one and several tool calls', () => {
    expect(stepCountText(0)).toBe('The agent answered without using any tools.')
    expect(stepCountText(1)).toBe('The agent used 1 tool call.')
    expect(stepCountText(3)).toBe('The agent used 3 tool calls.')
  })
})

describe('EXAMPLE_QUESTIONS', () => {
  it('offers a few usable questions', () => {
    expect(EXAMPLE_QUESTIONS.length).toBeGreaterThan(1)
    for (const question of EXAMPLE_QUESTIONS) expect(question.length > 5 && question.length <= 500).toBe(true)
  })
})
