import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { makeAgentResponse } from '../test/factories'
import AgentTrace from './AgentTrace'

describe('AgentTrace', () => {
  it('shows each step with its tool, arguments, thought and result', () => {
    render(<AgentTrace steps={makeAgentResponse().steps} />)

    expect(screen.getByText('The agent used 1 tool call.')).toBeInTheDocument()
    expect(screen.getByText('Step 1')).toBeInTheDocument()
    expect(screen.getByText('list_applications')).toBeInTheDocument()
    expect(screen.getByText('ok')).toBeInTheDocument()
    expect(screen.getByText('“I need the list.”')).toBeInTheDocument()
    expect(screen.getByText('with status: "applied"')).toBeInTheDocument()
    expect(screen.getByText(/"company": "Acme Corp"/)).toBeInTheDocument() // the result, indented
  })

  it('marks a failed step as an error', () => {
    const steps = [{ ...makeAgentResponse().steps[0], ok: false, observation: 'Error: Application 9 was not found.' }]
    render(<AgentTrace steps={steps} />)

    expect(screen.getByText('error')).toBeInTheDocument()
    expect(screen.getByText('Error: Application 9 was not found.')).toBeInTheDocument()
  })

  it('says so when the agent used no tools', () => {
    render(<AgentTrace steps={[]} />)
    expect(screen.getByText('The agent answered without using any tools.')).toBeInTheDocument()
  })

  it('shows the steps in order', () => {
    const first = makeAgentResponse().steps[0]
    render(<AgentTrace steps={[first, { ...first, number: 2, tool: 'get_application', arguments: { id: 1 } }]} />)

    expect(screen.getByText('The agent used 2 tool calls.')).toBeInTheDocument()
    expect(screen.getByText('Step 2')).toBeInTheDocument()
    expect(screen.getByText('with id: 1')).toBeInTheDocument()
  })
})
