import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { makeApplication } from '../test/factories'
import TrackerPage from './TrackerPage'

const applications = [
  makeApplication({ id: 1, company: 'Acme Corp', job_title: 'Backend Engineer', status: 'wishlist' }),
  makeApplication({ id: 2, company: 'Globex', job_title: 'Data Scientist', status: 'applied' }),
  makeApplication({ id: 3, company: 'Initech', job_title: 'Designer', status: 'applied' }),
]

function renderPage(overrides = {}) {
  const reload = vi.fn()
  render(<TrackerPage applications={applications} loading={false} error={null} reload={reload} {...overrides} />)
  return reload
}

describe('TrackerPage', () => {
  it('shows one column per status, with each application in the right one', () => {
    renderPage()

    const wishlist = screen.getByRole('region', { name: 'Wishlist column' })
    const applied = screen.getByRole('region', { name: 'Applied column' })
    expect(within(wishlist).getByText('Acme Corp')).toBeInTheDocument()
    expect(within(applied).getByText('Globex')).toBeInTheDocument()
    expect(within(applied).getByText('Initech')).toBeInTheDocument()
    expect(within(applied).queryByText('Acme Corp')).not.toBeInTheDocument()
  })

  it('shows a message in empty columns', () => {
    renderPage()
    const offer = screen.getByRole('region', { name: 'Offer column' })
    expect(within(offer).getByText('No applications')).toBeInTheDocument()
  })

  it('filters cards as you type in the search box', async () => {
    renderPage()
    await userEvent.type(screen.getByLabelText('Search applications'), 'globex')

    expect(screen.getByText('Globex')).toBeInTheDocument()
    expect(screen.queryByText('Acme Corp')).not.toBeInTheDocument()
    expect(screen.queryByText('Initech')).not.toBeInTheDocument()
  })

  it('opens the new-application form', async () => {
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: 'New application' }))
    expect(screen.getByRole('dialog', { name: 'New application' })).toBeInTheDocument()
  })

  it('shows a loading message while the first load is in progress', () => {
    renderPage({ applications: [], loading: true })
    expect(screen.getByRole('status')).toHaveTextContent('Loading applications')
  })

  it('shows load errors with a working Retry button', async () => {
    const reload = renderPage({ applications: [], error: 'Cannot reach the server.' })
    expect(screen.getByRole('alert')).toHaveTextContent('Cannot reach the server.')

    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(reload).toHaveBeenCalledTimes(1)
  })
})
