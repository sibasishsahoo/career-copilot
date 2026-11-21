import { describe, expect, it } from 'vitest'
import { makeApplication } from '../test/factories'
import { EMPTY_VALUES, buildPayload, valuesFromApplication, validate } from './applicationForm'
import type { FormValues } from './applicationForm'

function valid(overrides: Partial<FormValues> = {}): FormValues {
  return { ...EMPTY_VALUES, company: 'Acme', job_title: 'Backend Engineer', ...overrides }
}

describe('validate', () => {
  it('accepts a form with just a company and a job title', () => {
    expect(validate(valid())).toEqual({})
  })

  it('requires a company', () => {
    expect(validate(valid({ company: '' })).company).toBe('Company is required.')
  })

  it('requires a job title', () => {
    expect(validate(valid({ job_title: '' })).job_title).toBe('Job title is required.')
  })

  it('treats whitespace-only text as empty', () => {
    const errors = validate(valid({ company: '   ', job_title: '\t' }))
    expect(errors.company).toBe('Company is required.')
    expect(errors.job_title).toBe('Job title is required.')
  })

  it('rejects an overlong company and an overlong title', () => {
    const errors = validate(valid({ company: 'x'.repeat(201), job_title: 'y'.repeat(201) }))
    expect(errors.company).toContain('200')
    expect(errors.job_title).toContain('200')
  })

  it('accepts http and https links, in any letter case', () => {
    expect(validate(valid({ job_url: 'https://example.com/jobs/1' }))).toEqual({})
    expect(validate(valid({ job_url: 'http://example.com' }))).toEqual({})
    expect(validate(valid({ job_url: 'HTTPS://EXAMPLE.COM' }))).toEqual({})
  })

  it('rejects links that are not http(s)', () => {
    for (const url of ['javascript:alert(1)', 'ftp://example.com', 'example.com/job']) {
      expect(validate(valid({ job_url: url })).job_url).toBe('The link must start with http:// or https://')
    }
  })

  it('allows an empty link', () => {
    expect(validate(valid({ job_url: '' }))).toEqual({})
  })

  it('rejects overlong notes', () => {
    expect(validate(valid({ notes: 'n'.repeat(5001) })).notes).toContain('5000')
  })

  it('reports several problems at once', () => {
    const errors = validate(valid({ company: '', job_title: '', job_url: 'nope' }))
    expect(Object.keys(errors).sort()).toEqual(['company', 'job_title', 'job_url'])
  })
})

describe('buildPayload', () => {
  it('trims text and turns empty optional fields into null', () => {
    const payload = buildPayload(valid({ company: '  Acme  ', location: '   ' }), true)
    expect(payload).toEqual({
      company: 'Acme',
      job_title: 'Backend Engineer',
      status: 'wishlist',
      job_url: null,
      location: null,
      applied_date: null,
      notes: null,
    })
  })

  it('keeps filled optional fields', () => {
    const payload = buildPayload(
      valid({ job_url: ' https://example.com ', location: 'Remote', applied_date: '2026-10-01', notes: 'hi' }),
      true,
    )
    expect(payload.job_url).toBe('https://example.com')
    expect(payload.location).toBe('Remote')
    expect(payload.applied_date).toBe('2026-10-01')
    expect(payload.notes).toBe('hi')
  })

  it('includes the chosen status when creating', () => {
    expect(buildPayload(valid({ status: 'applied' }), true).status).toBe('applied')
  })

  it('leaves status out when editing (status has its own endpoint)', () => {
    expect('status' in buildPayload(valid({ status: 'applied' }), false)).toBe(false)
  })
})

describe('valuesFromApplication', () => {
  it('turns null fields into empty strings for the inputs', () => {
    const values = valuesFromApplication(makeApplication({ job_url: null, location: null, notes: null }))
    expect(values.job_url).toBe('')
    expect(values.location).toBe('')
    expect(values.applied_date).toBe('')
    expect(values.notes).toBe('')
  })

  it('copies filled fields', () => {
    const values = valuesFromApplication(
      makeApplication({ company: 'Globex', status: 'offer', applied_date: '2026-10-01' }),
    )
    expect(values.company).toBe('Globex')
    expect(values.status).toBe('offer')
    expect(values.applied_date).toBe('2026-10-01')
  })
})
