import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { makePrep } from '../test/factories'
import InterviewPrepView from './InterviewPrepView'

describe('InterviewPrepView', () => {
  it('summarizes the story coverage in words and in a bar', () => {
    render(<InterviewPrepView prep={makePrep()} />)

    expect(screen.getByText('1 of 2 questions have a matching story in your notes.')).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Story coverage' })).toHaveAttribute('aria-valuenow', '50')
    expect(screen.getByText('Write a note about your experience for question #2 in the Notes tab, then regenerate.')).toBeInTheDocument()
  })

  it('shows the answer outline and the notes it is built from for a question with a story', () => {
    render(<InterviewPrepView prep={makePrep()} />)

    expect(screen.getByText('Tell me about a time you reduced deployment time.')).toBeInTheDocument()
    expect(screen.getByText('Behavioral')).toBeInTheDocument()
    expect(screen.getByText('Why it is asked: Shows impact on delivery.')).toBeInTheDocument()
    expect(screen.getByText('Deployments took forty minutes. I automated rollbacks [Faster deployments].')).toBeInTheDocument()
    expect(screen.getByText('Faster deployments')).toBeInTheDocument() // the source chip
  })

  it('flags a question with no story instead of inventing one', () => {
    render(<InterviewPrepView prep={makePrep()} />)

    expect(screen.getByText('How would you use Docker in production?')).toBeInTheDocument()
    expect(screen.getByText('Skill gap')).toBeInTheDocument()
    expect(screen.getByText('about Docker')).toBeInTheDocument()
    expect(screen.getByText('No story found')).toBeInTheDocument()
    expect(screen.getByText('No note in your knowledge base matched this question. Consider writing one.')).toBeInTheDocument()
  })

  it('lists the questions to ask the interviewer', () => {
    render(<InterviewPrepView prep={makePrep()} />)
    expect(screen.getByText('Questions to ask the interviewer')).toBeInTheDocument()
    expect(screen.getByText('What does success look like in six months?')).toBeInTheDocument()
  })

  it('gives no advice when every question has a story', () => {
    const prep = makePrep({ coverage: { total: 1, with_story: 1, without_story: [] }, items: [makePrep().items[0]] })
    render(<InterviewPrepView prep={prep} />)

    expect(screen.getByText('All 1 questions have a matching story in your notes.')).toBeInTheDocument()
    expect(screen.queryByText(/Write a note about your experience/)).not.toBeInTheDocument()
  })
})
