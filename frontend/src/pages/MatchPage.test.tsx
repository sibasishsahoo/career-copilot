import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as client from '../api/client'
import { makeApplication, makeDetail, makeMatchResult } from '../test/factories'
import MatchPage from './MatchPage'

// Replace the functions that call the network. Everything else in client.ts stays real.
vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return {
    ...actual,
    parseResume: vi.fn(),
    matchJob: vi.fn(),
    createApplication: vi.fn(),
    attachMatch: vi.fn(),
  }
})

const JOB_TEXT = 'We are hiring a Backend Engineer. Requirements: Python, SQL, REST APIs. Nice to have: Docker.'
const parsedResume = {
  full_name: 'Jane Doe',
  email: null,
  phone: null,
  location: 'Austin, TX',
  summary: null,
  skills: ['Python', 'SQL'],
  experience: [],
  education: [],
}

async function parseTheResume() {
  const file = new File(['%PDF-1.4 test'], 'resume.pdf', { type: 'application/pdf' })
  await userEvent.upload(screen.getByLabelText(/Resume file/), file)
  await userEvent.click(screen.getByRole('button', { name: 'Parse resume' }))
  await screen.findByText('Jane Doe')
}

describe('MatchPage', () => {
  beforeEach(() => {
    vi.mocked(client.parseResume).mockReset()
    vi.mocked(client.matchJob).mockReset()
    vi.mocked(client.createApplication).mockReset()
    vi.mocked(client.attachMatch).mockReset()
    vi.mocked(client.parseResume).mockResolvedValue({
      filename: 'resume.pdf',
      characters_extracted: 100,
      text_truncated: false,
      text_preview: 'Jane Doe',
      parsed: parsedResume,
    })
  })

  it('cannot analyze until a resume is parsed and the job text is long enough', async () => {
    render(<MatchPage applications={[]} reloadApplications={vi.fn()} />)
    const analyze = screen.getByRole('button', { name: /Analyze match/ })
    expect(analyze).toBeDisabled()

    await userEvent.type(screen.getByLabelText('Job description'), JOB_TEXT)
    expect(analyze).toBeDisabled() // still no resume

    await parseTheResume()
    expect(analyze).toBeEnabled()
  })

  it('rejects a file that is not a PDF or DOCX before uploading anything', async () => {
    render(<MatchPage applications={[]} reloadApplications={vi.fn()} />)
    const file = new File(['hello'], 'notes.txt', { type: 'text/plain' })
    await userEvent.upload(screen.getByLabelText(/Resume file/), file, { applyAccept: false })

    expect(screen.getByRole('alert')).toHaveTextContent('Please choose a PDF or DOCX file.')
    expect(client.parseResume).not.toHaveBeenCalled()
  })

  it('shows the match result after analyzing', async () => {
    vi.mocked(client.matchJob).mockResolvedValue(makeMatchResult())
    render(<MatchPage applications={[]} reloadApplications={vi.fn()} />)

    await parseTheResume()
    await userEvent.type(screen.getByLabelText('Job description'), JOB_TEXT)
    await userEvent.click(screen.getByRole('button', { name: /Analyze match/ }))

    expect(await screen.findByRole('region', { name: 'Match result' })).toBeInTheDocument()
    expect(client.matchJob).toHaveBeenCalledWith(parsedResume, JOB_TEXT)
    expect(screen.getByText('47/100')).toBeInTheDocument()
  })

  it('shows the backend message when analysis fails', async () => {
    vi.mocked(client.matchJob).mockRejectedValue(new client.ApiError(429, 'Gemini rate limit reached.'))
    render(<MatchPage applications={[]} reloadApplications={vi.fn()} />)

    await parseTheResume()
    await userEvent.type(screen.getByLabelText('Job description'), JOB_TEXT)
    await userEvent.click(screen.getByRole('button', { name: /Analyze match/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Gemini rate limit reached.')
  })

  it('saves the match on an existing application, sending only the snapshot fields', async () => {
    vi.mocked(client.matchJob).mockResolvedValue(makeMatchResult())
    vi.mocked(client.attachMatch).mockResolvedValue(makeDetail().match_snapshot as never)
    const reload = vi.fn()
    const existing = makeApplication({ id: 7, company: 'Acme Cloud', job_title: 'Backend Engineer' })
    render(<MatchPage applications={[existing]} reloadApplications={reload} />)

    await parseTheResume()
    await userEvent.type(screen.getByLabelText('Job description'), JOB_TEXT)
    await userEvent.click(screen.getByRole('button', { name: /Analyze match/ }))
    await screen.findByRole('region', { name: 'Save match' })

    await userEvent.selectOptions(screen.getByLabelText('Save to'), '7')
    await userEvent.click(screen.getByRole('button', { name: 'Save match' }))

    expect(await screen.findByText('Saved to "Acme Cloud".')).toBeInTheDocument()
    expect(client.attachMatch).toHaveBeenCalledWith(7, {
      job_description: JOB_TEXT,
      score: 47,
      matched_skills: [
        { skill: 'Python', category: 'required' },
        { skill: 'SQL', category: 'required' },
      ],
      missing_skills: [
        { skill: 'REST APIs', category: 'required' },
        { skill: 'Docker', category: 'preferred' },
        { skill: 'AWS', category: 'preferred' },
      ],
    })
    expect(reload).toHaveBeenCalled()
  })

  it('removes the resume from memory on request', async () => {
    render(<MatchPage applications={[]} reloadApplications={vi.fn()} />)
    await parseTheResume()

    await userEvent.click(screen.getByRole('button', { name: 'Remove resume' }))
    expect(screen.queryByText('Jane Doe')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Parse resume' })).toBeDisabled()
  })
})
