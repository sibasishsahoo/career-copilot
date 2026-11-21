import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import NoteForm from './NoteForm'

function setup(onSubmit = vi.fn().mockResolvedValue(undefined)) {
  render(<NoteForm onSubmit={onSubmit} />)
  return onSubmit
}

describe('NoteForm', () => {
  it('shows both messages and sends nothing when the form is empty', async () => {
    const onSubmit = setup()
    await userEvent.click(screen.getByRole('button', { name: 'Add note' }))

    expect(screen.getByText('Title is required.')).toBeInTheDocument()
    expect(screen.getByText('Note text is required.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits trimmed values, confirms, and clears the form', async () => {
    const onSubmit = setup()
    await userEvent.type(screen.getByLabelText('Note title'), '  Faster deploys  ')
    await userEvent.type(screen.getByLabelText('Note text'), 'I cut deploys to 12 minutes.')
    await userEvent.click(screen.getByRole('button', { name: 'Add note' }))

    expect(onSubmit).toHaveBeenCalledWith({ title: 'Faster deploys', text: 'I cut deploys to 12 minutes.' })
    expect(await screen.findByText('Saved "Faster deploys".')).toBeInTheDocument()
    expect(screen.getByLabelText('Note title')).toHaveValue('')
    expect(screen.getByLabelText('Note text')).toHaveValue('')
  })

  it('shows the error and keeps what was typed when saving fails', async () => {
    setup(vi.fn().mockRejectedValue(new Error('The local embedding model failed.')))
    await userEvent.type(screen.getByLabelText('Note title'), 'T')
    await userEvent.type(screen.getByLabelText('Note text'), 'Body')
    await userEvent.click(screen.getByRole('button', { name: 'Add note' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('The local embedding model failed.')
    expect(screen.getByLabelText('Note text')).toHaveValue('Body')
  })

  it('counts characters as you type', async () => {
    setup()
    await userEvent.type(screen.getByLabelText('Note text'), 'hello')
    expect(screen.getByText('5 / 50,000 characters')).toBeInTheDocument()
  })
})
