import { describe, expect, it } from 'vitest'
import { APPLICATION_STATUSES } from '../api/types'
import { makeApplication } from '../test/factories'
import { BOARD_STATUSES, STATUS_LABELS, STATUS_STYLES, filterApplications, groupByStatus } from './status'

describe('status tables', () => {
  it('has a label and a style for every status', () => {
    for (const status of APPLICATION_STATUSES) {
      expect(STATUS_LABELS[status].length > 0).toBe(true)
      expect(STATUS_STYLES[status].length > 0).toBe(true)
    }
  })

  it('shows every status as a board column, in pipeline order', () => {
    expect(BOARD_STATUSES).toEqual(['wishlist', 'applied', 'interviewing', 'offer', 'rejected', 'withdrawn'])
  })
})

describe('groupByStatus', () => {
  it('puts each application in the list for its status', () => {
    const groups = groupByStatus([
      makeApplication({ id: 1, status: 'applied' }),
      makeApplication({ id: 2, status: 'offer' }),
      makeApplication({ id: 3, status: 'applied' }),
    ])
    expect(groups.applied.map((a) => a.id)).toEqual([1, 3])
    expect(groups.offer.map((a) => a.id)).toEqual([2])
  })

  it('always returns a list for every status, even when empty', () => {
    const groups = groupByStatus([])
    for (const status of APPLICATION_STATUSES) {
      expect(groups[status]).toEqual([])
    }
  })
})

describe('filterApplications', () => {
  const applications = [
    makeApplication({ id: 1, company: 'Acme Corp', job_title: 'Backend Engineer', location: 'Remote' }),
    makeApplication({ id: 2, company: 'Globex', job_title: 'Data Scientist', location: 'Berlin' }),
    makeApplication({ id: 3, company: 'Initech', job_title: 'Designer', location: null }),
  ]

  it('keeps everything for a blank query', () => {
    expect(filterApplications(applications, '')).toBe(applications)
    expect(filterApplications(applications, '   ')).toBe(applications)
  })

  it('matches the company, ignoring case', () => {
    expect(filterApplications(applications, 'ACME').map((a) => a.id)).toEqual([1])
  })

  it('matches the job title', () => {
    expect(filterApplications(applications, 'scientist').map((a) => a.id)).toEqual([2])
  })

  it('matches the location', () => {
    expect(filterApplications(applications, 'berlin').map((a) => a.id)).toEqual([2])
  })

  it('returns an empty list when nothing matches', () => {
    expect(filterApplications(applications, 'zzz')).toEqual([])
  })

  it('copes with applications that have no location', () => {
    expect(filterApplications(applications, 'initech').map((a) => a.id)).toEqual([3])
  })
})
