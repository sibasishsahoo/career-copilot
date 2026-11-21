import type { Application, ApplicationStatus } from '../api/types'
import { APPLICATION_STATUSES } from '../api/types'

export const STATUS_LABELS: Record<ApplicationStatus, string> = {
  wishlist: 'Wishlist',
  applied: 'Applied',
  interviewing: 'Interviewing',
  offer: 'Offer',
  rejected: 'Rejected',
  withdrawn: 'Withdrawn',
}

// Tailwind only generates the classes it can SEE as complete strings in the source code,
// so every class is written out in full here instead of being built from pieces.
export const STATUS_STYLES: Record<ApplicationStatus, string> = {
  wishlist: 'bg-slate-100 text-slate-700 ring-slate-300',
  applied: 'bg-blue-100 text-blue-800 ring-blue-300',
  interviewing: 'bg-amber-100 text-amber-800 ring-amber-300',
  offer: 'bg-emerald-100 text-emerald-800 ring-emerald-300',
  rejected: 'bg-red-100 text-red-800 ring-red-300',
  withdrawn: 'bg-zinc-100 text-zinc-600 ring-zinc-300',
}

/** Board columns, left to right. */
export const BOARD_STATUSES: readonly ApplicationStatus[] = APPLICATION_STATUSES

/** Put each application into the list for its status. Every status always has a (maybe empty) list. */
export function groupByStatus(applications: Application[]): Record<ApplicationStatus, Application[]> {
  const groups: Record<ApplicationStatus, Application[]> = {
    wishlist: [],
    applied: [],
    interviewing: [],
    offer: [],
    rejected: [],
    withdrawn: [],
  }
  for (const application of applications) {
    groups[application.status].push(application)
  }
  return groups
}

/** Case-insensitive search over company, job title and location. A blank query keeps everything. */
export function filterApplications(applications: Application[], query: string): Application[] {
  const needle = query.trim().toLowerCase()
  if (!needle) return applications
  return applications.filter((application) =>
    [application.company, application.job_title, application.location ?? '']
      .join(' ')
      .toLowerCase()
      .includes(needle),
  )
}
