import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as client from '../api/client'
import { makeAskResponse, makeSearchResult } from '../test/factories'
import AskPanel from './AskPanel'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return { ...actual, askKnowledge: vi.fn() }
})

async function ask(question = 'How did I speed up deployments?') {
  await userEvent.type(screen.getByLabelText('Question for your notes'), question)
  await userEvent.click(screen.getByRole('button', { name: 'Ask your notes' }))
}

describe('AskPanel', () => {
  beforeEach(() => {
    vi.mocked(client.askKnowledge).mockReset()
  })

  it('shows a grounded answer with citation badges and highlights the source it used', async () => {
    vi.mocked(client.askKnowledge).mockResolvedValue(makeAskResponse())
    render(<AskPanel hasNotes />)
    await ask()

    expect(await screen.findByText('Grounded in your notes')).toBeInTheDocument()
    expect(screen.getByText('[1]')).toBeInTheDocument()
    expect(screen.getByText('used in the answer')).toBeInTheDocument()
    expect(screen.getByText('Source 1')).toBeInTheDocument()
    expect(client.askKnowledge).toHaveBeenCalledWith('How did I speed up deployments?')
  })

  it('says so when no note was relevant and the AI was not called', async () => {
    vi.mocked(client.askKnowledge).mockResolvedValue(
      makeAskResponse({ answer: "I couldn't find this in your knowledge base.", grounded: false, used_llm: false, sources: [], sources_used: [] }),
    )
    render(<AskPanel hasNotes />)
    await ask('pizza')

    expect(await screen.findByText('No relevant note found, so the AI was not called')).toBeInTheDocument()
    expect(screen.getByText('No passage was relevant enough to use.')).toBeInTheDocument()
  })

  it('warns when the answer cites no valid note', async () => {
    vi.mocked(client.askKnowledge).mockResolvedValue(
      makeAskResponse({ answer: 'Trust me, it was great.', grounded: false, sources_used: [] }),
    )
    render(<AskPanel hasNotes />)
    await ask()

    expect(await screen.findByText('Not verified: the answer cites no valid note')).toBeInTheDocument()
  })

  it('shows a citation of an unknown source as plain text, not as a badge', async () => {
    vi.mocked(client.askKnowledge).mockResolvedValue(
      makeAskResponse({ answer: 'Claim [5].', sources: [makeSearchResult()], sources_used: [] }),
    )
    render(<AskPanel hasNotes />)
    await ask()

    expect((await screen.findByText('[5]')).tagName).toBe('SPAN')
  })

  it('asks for text before calling the backend', async () => {
    render(<AskPanel hasNotes />)
    await userEvent.click(screen.getByRole('button', { name: 'Ask your notes' }))

    expect(screen.getByText('Please type something first.')).toBeInTheDocument()
    expect(client.askKnowledge).not.toHaveBeenCalled()
  })

  it('shows backend errors', async () => {
    vi.mocked(client.askKnowledge).mockRejectedValue(new client.ApiError(429, 'Gemini rate limit reached.'))
    render(<AskPanel hasNotes />)
    await ask()

    expect(await screen.findByRole('alert')).toHaveTextContent('Gemini rate limit reached.')
  })

  it('tells you when there are no notes yet', () => {
    render(<AskPanel hasNotes={false} />)
    expect(screen.getByText('You have no notes yet, so there is nothing to answer from.')).toBeInTheDocument()
  })
})
