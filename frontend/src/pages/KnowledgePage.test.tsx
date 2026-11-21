import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as client from '../api/client'
import { makeDocument, makeSearchResult } from '../test/factories'
import KnowledgePage from './KnowledgePage'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return {
    ...actual,
    listDocuments: vi.fn(),
    addDocument: vi.fn(),
    getDocument: vi.fn(),
    deleteDocument: vi.fn(),
    searchKnowledge: vi.fn(),
    askKnowledge: vi.fn(),
  }
})

describe('KnowledgePage', () => {
  beforeEach(() => {
    for (const fn of [client.listDocuments, client.addDocument, client.getDocument, client.deleteDocument, client.searchKnowledge, client.askKnowledge]) {
      vi.mocked(fn).mockReset()
    }
    vi.mocked(client.listDocuments).mockResolvedValue([makeDocument()])
  })

  it('lists your notes with how they were split', async () => {
    render(<KnowledgePage />)
    expect(await screen.findByText('Faster deployments')).toBeInTheDocument()
    expect(screen.getByText(/2 passages · 1,234 characters/)).toBeInTheDocument()
    expect(screen.getByText('Your notes (1)')).toBeInTheDocument()
  })

  it('invites you to add a first note when there are none', async () => {
    vi.mocked(client.listDocuments).mockResolvedValue([])
    render(<KnowledgePage />)
    expect(await screen.findByText(/You have no notes yet\. Add your first one above/)).toBeInTheDocument()
  })

  it('adds a note and refreshes the list', async () => {
    vi.mocked(client.addDocument).mockResolvedValue(makeDocument({ id: 'doc2', title: 'Mentoring' }))
    render(<KnowledgePage />)
    await screen.findByText('Faster deployments')

    await userEvent.type(screen.getByLabelText('Note title'), 'Mentoring')
    await userEvent.type(screen.getByLabelText('Note text'), 'I mentored two interns.')
    await userEvent.click(screen.getByRole('button', { name: 'Add note' }))

    expect(client.addDocument).toHaveBeenCalledWith({ title: 'Mentoring', text: 'I mentored two interns.' })
    expect(await screen.findByText('Saved "Mentoring".')).toBeInTheDocument()
    expect(client.listDocuments).toHaveBeenCalledTimes(2) // loaded once, reloaded after the add
  })

  it('shows how a note was split into passages', async () => {
    vi.mocked(client.getDocument).mockResolvedValue({
      ...makeDocument(),
      chunks: [{ index: 0, text: 'First passage text.' }, { index: 1, text: 'Second passage text.' }],
    })
    render(<KnowledgePage />)
    await userEvent.click(await screen.findByRole('button', { name: 'Show passages of Faster deployments' }))

    expect(await screen.findByText('First passage text.')).toBeInTheDocument()
    expect(screen.getByText('Passage 2')).toBeInTheDocument()
    expect(client.getDocument).toHaveBeenCalledWith('doc1')
  })

  it('deletes a note after a confirmation step and refreshes the list', async () => {
    vi.mocked(client.deleteDocument).mockResolvedValue(undefined)
    render(<KnowledgePage />)
    await userEvent.click(await screen.findByRole('button', { name: 'Delete Faster deployments' }))

    expect(screen.getByText('Delete this note?')).toBeInTheDocument()
    expect(client.deleteDocument).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Yes, delete' }))

    expect(client.deleteDocument).toHaveBeenCalledWith('doc1')
    expect(client.listDocuments).toHaveBeenCalledTimes(2)
  })

  it('searches and shows each passage with its similarity score', async () => {
    vi.mocked(client.searchKnowledge).mockResolvedValue({ query: 'deploy', results: [makeSearchResult()] })
    render(<KnowledgePage />)
    await screen.findByText('Faster deployments')

    await userEvent.type(screen.getByLabelText('Search text'), 'deploy')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))

    expect(await screen.findByText('similarity 0.53')).toBeInTheDocument()
    expect(client.searchKnowledge).toHaveBeenCalledWith('deploy')
  })

  it('shows a load error with a working Retry button', async () => {
    vi.mocked(client.listDocuments).mockRejectedValueOnce(new client.ApiError(503, 'The knowledge base is unavailable.'))
    render(<KnowledgePage />)

    expect(await screen.findByRole('alert')).toHaveTextContent('The knowledge base is unavailable.')
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('Faster deployments')).toBeInTheDocument()
  })
})
