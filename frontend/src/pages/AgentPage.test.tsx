import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as client from '../api/client'
import { EXAMPLE_QUESTIONS } from '../lib/agent'
import { makeAgentResponse } from '../test/factories'
import AgentPage from './AgentPage'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return { ...actual, askAgent: vi.fn() }
})

describe('AgentPage', () => {
  beforeEach(() => {
    vi.mocked(client.askAgent).mockReset()
  })

  it('fills in an example question when you click it', async () => {
    render(<AgentPage />)
    await userEvent.click(screen.getByRole('button', { name: EXAMPLE_QUESTIONS[0] }))
    expect(screen.getByLabelText('Question for the agent')).toHaveValue(EXAMPLE_QUESTIONS[0])
  })

  it('shows the answer and the step trace', async () => {
    vi.mocked(client.askAgent).mockResolvedValue(makeAgentResponse())
    render(<AgentPage />)
    await userEvent.type(screen.getByLabelText('Question for the agent'), 'Which application is furthest along?')
    await userEvent.click(screen.getByRole('button', { name: 'Ask the agent' }))

    expect(await screen.findByText('Acme Corp is furthest along.')).toBeInTheDocument()
    expect(screen.getByText('list_applications')).toBeInTheDocument()
    expect(client.askAgent).toHaveBeenCalledWith('Which application is furthest along?')
  })

  it('warns when the agent ran out of steps', async () => {
    vi.mocked(client.askAgent).mockResolvedValue(makeAgentResponse({ stopped_reason: 'max_steps' }))
    render(<AgentPage />)
    await userEvent.type(screen.getByLabelText('Question for the agent'), 'A hard question')
    await userEvent.click(screen.getByRole('button', { name: 'Ask the agent' }))

    expect(await screen.findByRole('status')).toHaveTextContent('ran out of steps')
  })

  it('asks for text before calling the backend', async () => {
    render(<AgentPage />)
    await userEvent.click(screen.getByRole('button', { name: 'Ask the agent' }))
    expect(screen.getByText('Please type something first.')).toBeInTheDocument()
    expect(client.askAgent).not.toHaveBeenCalled()
  })

  it('shows backend errors', async () => {
    vi.mocked(client.askAgent).mockRejectedValue(new client.ApiError(429, 'Gemini rate limit reached.'))
    render(<AgentPage />)
    await userEvent.type(screen.getByLabelText('Question for the agent'), 'hi')
    await userEvent.click(screen.getByRole('button', { name: 'Ask the agent' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Gemini rate limit reached.')
  })
})
