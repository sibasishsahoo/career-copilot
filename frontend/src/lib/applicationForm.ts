import type { Application, ApplicationCreate, ApplicationStatus } from '../api/types'

/** Everything in a form input is a string, even dates and "empty". These types describe that. */
export interface FormValues {
  company: string
  job_title: string
  status: ApplicationStatus
  job_url: string
  location: string
  applied_date: string
  notes: string
}

export type FormErrors = Partial<Record<keyof FormValues, string>>

export const EMPTY_VALUES: FormValues = {
  company: '',
  job_title: '',
  status: 'wishlist',
  job_url: '',
  location: '',
  applied_date: '',
  notes: '',
}

export function valuesFromApplication(application: Application): FormValues {
  return {
    company: application.company,
    job_title: application.job_title,
    status: application.status,
    job_url: application.job_url ?? '',
    location: application.location ?? '',
    applied_date: application.applied_date ?? '',
    notes: application.notes ?? '',
  }
}

/** Same rules as the backend (backend/app/schemas/application.py), so mistakes are caught instantly
 *  in the browser. The backend still re-checks everything: never trust the client. */
export function validate(values: FormValues): FormErrors {
  const errors: FormErrors = {}

  const company = values.company.trim()
  if (!company) errors.company = 'Company is required.'
  else if (company.length > 200) errors.company = 'Company must be 200 characters or fewer.'

  const title = values.job_title.trim()
  if (!title) errors.job_title = 'Job title is required.'
  else if (title.length > 200) errors.job_title = 'Job title must be 200 characters or fewer.'

  const url = values.job_url.trim()
  if (url && !/^https?:\/\//i.test(url)) errors.job_url = 'The link must start with http:// or https://'
  else if (url.length > 2000) errors.job_url = 'The link is too long.'

  if (values.location.trim().length > 200) errors.location = 'Location must be 200 characters or fewer.'
  if (values.notes.trim().length > 5000) errors.notes = 'Notes must be 5000 characters or fewer.'

  return errors
}

function emptyToNull(value: string): string | null {
  const trimmed = value.trim()
  return trimmed === '' ? null : trimmed
}

/** Form strings -> the JSON the API expects. An empty input becomes null (the API rejects "" for
 *  dates and links). `includeStatus` is false when editing, because status has its own endpoint. */
export function buildPayload(values: FormValues, includeStatus: boolean): ApplicationCreate {
  const payload: ApplicationCreate = {
    company: values.company.trim(),
    job_title: values.job_title.trim(),
    job_url: emptyToNull(values.job_url),
    location: emptyToNull(values.location),
    applied_date: emptyToNull(values.applied_date),
    notes: emptyToNull(values.notes),
  }
  if (includeStatus) payload.status = values.status
  return payload
}
