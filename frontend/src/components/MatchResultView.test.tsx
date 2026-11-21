import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { makeMatchResult } from '../test/factories'
import MatchResultView from './MatchResultView'

describe('MatchResultView', () => {
  it('shows the job, the score and the explanation of who computed it', () => {
    render(<MatchResultView result={makeMatchResult()} />)

    expect(screen.getByRole('heading', { name: 'Backend Engineer at Acme Cloud' })).toBeInTheDocument()
    expect(screen.getByText('47/100')).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Match score' })).toHaveAttribute('aria-valuenow', '47')
    expect(screen.getByText(/calculated by code/)).toBeInTheDocument()
  })

  it('lists matched and missing skills', () => {
    render(<MatchResultView result={makeMatchResult()} />)

    // Exact strings, not /regex/: "Docker" also appears inside the suggestion sentence,
    // and getByText throws when more than one element matches.
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText('REST APIs')).toBeInTheDocument()
    expect(screen.getByText('Docker')).toBeInTheDocument()
  })

  it('shows where each matched skill was found', () => {
    render(<MatchResultView result={makeMatchResult()} />)

    expect(screen.getByText('(in skills list)')).toBeInTheDocument()
    expect(screen.getByText('(in experience)')).toBeInTheDocument()
  })

  it('shows the suggestions', () => {
    render(<MatchResultView result={makeMatchResult()} />)
    expect(screen.getByText('Learn Docker by containerizing a small project.')).toBeInTheDocument()
  })

  it('says there is nothing to suggest when nothing is missing', () => {
    const result = makeMatchResult({
      score: 100,
      required: { matched: [{ skill: 'Python', found_in: 'skills_section' }], missing: [] },
      preferred: { matched: [], missing: [] },
      suggestions: [],
    })
    render(<MatchResultView result={result} />)
    expect(screen.getByText('Nothing is missing, so there is nothing to suggest.')).toBeInTheDocument()
  })
})
