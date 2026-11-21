import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { EMPTY_VALUES } from '../lib/applicationForm'
import ApplicationForm from './ApplicationForm'

function setup(onSubmit = vi.fn().mockResolvedValue(undefined)) {
  render(
    <ApplicationForm initialValues={EMPTY_VALUES} submitLabel="Create" showStatus onSubmit={onSubmit} />,
  )
  return onSubmit
}

describe('ApplicationForm', () => {
  it('shows validation messages and sends nothing when required fields are empty', async () => {
    const onSubmit = setup()
    await userEvent.click(screen.getByRole('button', { name: 'Create' }))

    expect(screen.getByText('Company is required.')).toBeInTheDocument()
    expect(screen.getByText('Job title is required.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits trimmed values and turns empty optional fields into null', async () => {
    const onSubmit = setup()
    await userEvent.type(screen.getByLabelText('Company *'), '  Acme  ')
    await userEvent.type(screen.getByLabelText('Job title *'), 'Backend Engineer')
    await userEvent.click(screen.getByRole('button', { name: 'Create' }))

    expect(onSubmit).toHaveBeenCalledWith({
      company: 'Acme',
      job_title: 'Backend Engineer',
      status: 'wishlist',
      job_url: null,
      location: null,
      applied_date: null,
      notes: null,
    })
  })

  it('rejects a job link that is not http(s)', async () => {
    const onSubmit = setup()
    await userEvent.type(screen.getByLabelText('Company *'), 'Acme')
    await userEvent.type(screen.getByLabelText('Job title *'), 'Dev')
    await userEvent.type(screen.getByLabelText('Job link'), 'javascript:alert(1)')
    await userEvent.click(screen.getByRole('button', { name: 'Create' }))

    expect(screen.getByText('The link must start with http:// or https://')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('shows the error when the server rejects the submission', async () => {
    setup(vi.fn().mockRejectedValue(new Error('Server said no')))
    await userEvent.type(screen.getByLabelText('Company *'), 'Acme')
    await userEvent.type(screen.getByLabelText('Job title *'), 'Dev')
    await userEvent.click(screen.getByRole('button', { name: 'Create' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Server said no')
  })
})
