import { describe, expect, it } from 'vitest'
import { formatDate, formatDateTime } from './format'

describe('formatDate', () => {
  it('shows a placeholder for null', () => {
    expect(formatDate(null)).toBe('—')
  })

  it('formats a date-only string as that calendar day', () => {
    expect(formatDate('2026-10-01')).toBe('Oct 1, 2026')
  })

  it('formats a full ISO timestamp', () => {
    expect(formatDate('2026-10-15T12:00:00Z')).toContain('2026')
  })

  it('returns the original text when it is not a date', () => {
    expect(formatDate('not a date')).toBe('not a date')
  })
})

describe('formatDateTime', () => {
  it('shows a placeholder for null', () => {
    expect(formatDateTime(null)).toBe('—')
  })

  it('formats a timestamp with a date and a time', () => {
    const text = formatDateTime('2026-10-15T12:00:00Z')
    expect(text).toContain('2026')
    expect(text).toContain('Oct')
    expect(/\d{1,2}:\d{2}/.test(text)).toBe(true)
  })

  it('returns the original text when it is not a date', () => {
    expect(formatDateTime('garbage')).toBe('garbage')
  })
})
