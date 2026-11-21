import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as client from '../api/client'
import { makeApplication, makePrep } from '../test/factories'
import InterviewPage from './InterviewPage'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return { ...actual, getInterviewPrep: vi.fn(), generateInterviewPrep: vi.fn(), deleteInterviewPrep: vi.fn() }
})

const applications = [
  makeApplication({ id: 7, company: 'Acme Cloud', job_title: 'Backend Engineer', status: 'applied' }),
  makeApplication({ id: 8, company: 'Globex', job_title: 'Data Engineer', status: 'wishlist' }),
]
const COVERAGE_TEXT = '1 of 2 questions have a matching story in your notes.'

async function choose(id: string) {
  await userEvent.selectOptions(screen.getByLabelText('Application'), id)
}

describe('InterviewPage', () => {
  beforeEach(() => {
    vi.mocked(client.getInterviewPrep).mockReset()
    vi.mocked(client.generateInterviewPrep).mockReset()
    vi.mocked(client.deleteInterviewPrep).mockReset()
    vi.mocked(client.getInterviewPrep).mockRejectedValue(new client.ApiError(404, 'no prep yet'))
  })

  it('asks you to add an application first when there are none', () => {
    render(<InterviewPage applications={[]} />)
    expect(screen.getByText('Add an application in the Tracker tab first.')).toBeInTheDocument()
  })

  it('shows a saved pack when the application already has one', async () => {
    vi.mocked(client.getInterviewPrep).mockResolvedValue(makePrep())
    render(<InterviewPage applications={applications} />)
    await choose('7')

    expect(await screen.findByText(COVERAGE_TEXT)).toBeInTheDocument()
    expect(client.getInterviewPrep).toHaveBeenCalledWith(7)
    expect(screen.getByRole('button', { name: 'Regenerate interview prep' })).toBeInTheDocument()
  })

  it('offers to generate one when there is none yet (a 404 is not an error)', async () => {
    render(<InterviewPage applications={applications} />)
    await choose('7')

    expect(await screen.findByText('No interview prep has been generated for this application yet.')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Generate interview prep' })).toBeInTheDocument()
  })

  it('generates a pack with the chosen number of questions', async () => {
    vi.mocked(client.generateInterviewPrep).mockResolvedValue(makePrep())
    render(<InterviewPage applications={applications} />)
    await choose('7')
    await screen.findByRole('button', { name: 'Generate interview prep' })

    await userEvent.selectOptions(screen.getByLabelText('Number of questions'), '5')
    await userEvent.click(screen.getByRole('button', { name: 'Generate interview prep' }))

    expect(await screen.findByText(COVERAGE_TEXT)).toBeInTheDocument()
    expect(client.generateInterviewPrep).toHaveBeenCalledWith(7, 5)
  })

  it('uses 8 questions by default', async () => {
    vi.mocked(client.generateInterviewPrep).mockResolvedValue(makePrep())
    render(<InterviewPage applications={applications} />)
    await choose('7')
    await userEvent.click(await screen.findByRole('button', { name: 'Generate interview prep' }))

    await screen.findByText(COVERAGE_TEXT)
    expect(client.generateInterviewPrep).toHaveBeenCalledWith(7, 8)
  })

  it('explains what to do when the application has no saved match (409)', async () => {
    vi.mocked(client.generateInterviewPrep).mockRejectedValue(
      new client.ApiError(409, 'Application 7 has no saved job match, so there is no job description to prepare from.'),
    )
    render(<InterviewPage applications={applications} />)
    await choose('7')
    await userEvent.click(await screen.findByRole('button', { name: 'Generate interview prep' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('no saved job match')
    expect(screen.getByText(/Open the Match tool/)).toBeInTheDocument()
  })

  it('shows other errors without the match hint', async () => {
    vi.mocked(client.generateInterviewPrep).mockRejectedValue(new client.ApiError(503, 'The local embedding model failed.'))
    render(<InterviewPage applications={applications} />)
    await choose('7')
    await userEvent.click(await screen.findByRole('button', { name: 'Generate interview prep' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('The local embedding model failed.')
    expect(screen.queryByText(/Open the Match tool/)).not.toBeInTheDocument()
  })

  it('deletes a saved pack after a confirmation step', async () => {
    vi.mocked(client.getInterviewPrep).mockResolvedValue(makePrep())
    vi.mocked(client.deleteInterviewPrep).mockResolvedValue(undefined)
    render(<InterviewPage applications={applications} />)
    await choose('7')
    await screen.findByText(COVERAGE_TEXT)

    await userEvent.click(screen.getByRole('button', { name: 'Delete saved prep' }))
    expect(screen.getByText('Delete the saved prep?')).toBeInTheDocument()
    expect(client.deleteInterviewPrep).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: 'Yes, delete prep' }))
    expect(await screen.findByText('No interview prep has been generated for this application yet.')).toBeInTheDocument()
    expect(client.deleteInterviewPrep).toHaveBeenCalledWith(7)
  })

  it('clears the pack when you switch to another application', async () => {
    vi.mocked(client.getInterviewPrep).mockImplementation(async (id: number) => {
      if (id === 7) return makePrep()
      throw new client.ApiError(404, 'no prep yet')
    })
    render(<InterviewPage applications={applications} />)
    await choose('7')
    await screen.findByText(COVERAGE_TEXT)

    await choose('8')
    expect(await screen.findByText('No interview prep has been generated for this application yet.')).toBeInTheDocument()
    expect(screen.queryByText(COVERAGE_TEXT)).not.toBeInTheDocument()
  })
})
