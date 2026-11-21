import { useId, useState } from 'react'
import type { ChangeEvent, FormEvent, ReactNode } from 'react'
import { errorMessage } from '../api/client'
import { APPLICATION_STATUSES } from '../api/types'
import type { ApplicationCreate } from '../api/types'
import { buildPayload, validate } from '../lib/applicationForm'
import type { FormErrors, FormValues } from '../lib/applicationForm'
import { STATUS_LABELS } from '../lib/status'
import ErrorBanner from './ErrorBanner'
import { inputClass, labelClass, primaryButton, secondaryButton } from './ui'

interface Props {
  initialValues: FormValues
  submitLabel: string
  showStatus: boolean // true when creating (a new application picks its first status)
  onSubmit: (payload: ApplicationCreate) => Promise<void>
  onCancel?: () => void
}

interface FieldProps {
  id: string
  label: string
  error?: string
  children: ReactNode
}

/** A label, an input (passed in as children) and an optional error message. */
function Field({ id, label, error, children }: FieldProps) {
  return (
    <div>
      <label htmlFor={id} className={labelClass}>
        {label}
      </label>
      {children}
      {error && (
        <p id={`${id}-error`} className="mt-1 text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  )
}

type AnyInputEvent = ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>

export default function ApplicationForm({ initialValues, submitLabel, showStatus, onSubmit, onCancel }: Props) {
  const formId = useId() // unique prefix, so two forms on one page never share element ids
  const [values, setValues] = useState<FormValues>(initialValues)
  const [errors, setErrors] = useState<FormErrors>({})
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const idOf = (field: keyof FormValues) => `${formId}-${field}`

  // A "controlled input": React state is the single source of truth for what the input shows.
  function handleChange(field: keyof FormValues) {
    return (event: AnyInputEvent) => {
      setValues((previous) => ({ ...previous, [field]: event.target.value }))
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault() // stop the browser from reloading the page

    const found = validate(values)
    setErrors(found)
    setSubmitError(null)
    if (Object.keys(found).length > 0) return // show the messages, send nothing

    setSubmitting(true)
    try {
      await onSubmit(buildPayload(values, showStatus))
    } catch (problem) {
      setSubmitError(errorMessage(problem))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      {submitError && <ErrorBanner message={submitError} onDismiss={() => setSubmitError(null)} />}

      <Field id={idOf('company')} label="Company *" error={errors.company}>
        <input
          id={idOf('company')}
          className={inputClass}
          value={values.company}
          onChange={handleChange('company')}
          aria-invalid={errors.company ? true : undefined}
          aria-describedby={errors.company ? `${idOf('company')}-error` : undefined}
        />
      </Field>

      <Field id={idOf('job_title')} label="Job title *" error={errors.job_title}>
        <input
          id={idOf('job_title')}
          className={inputClass}
          value={values.job_title}
          onChange={handleChange('job_title')}
          aria-invalid={errors.job_title ? true : undefined}
          aria-describedby={errors.job_title ? `${idOf('job_title')}-error` : undefined}
        />
      </Field>

      {showStatus && (
        <Field id={idOf('status')} label="Status">
          <select
            id={idOf('status')}
            className={inputClass}
            value={values.status}
            onChange={handleChange('status')}
          >
            {APPLICATION_STATUSES.map((status) => (
              <option key={status} value={status}>
                {STATUS_LABELS[status]}
              </option>
            ))}
          </select>
        </Field>
      )}

      <Field id={idOf('job_url')} label="Job link" error={errors.job_url}>
        <input
          id={idOf('job_url')}
          className={inputClass}
          value={values.job_url}
          onChange={handleChange('job_url')}
          placeholder="https://..."
          aria-invalid={errors.job_url ? true : undefined}
          aria-describedby={errors.job_url ? `${idOf('job_url')}-error` : undefined}
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field id={idOf('location')} label="Location" error={errors.location}>
          <input
            id={idOf('location')}
            className={inputClass}
            value={values.location}
            onChange={handleChange('location')}
          />
        </Field>
        <Field id={idOf('applied_date')} label="Applied date">
          <input
            id={idOf('applied_date')}
            type="date"
            className={inputClass}
            value={values.applied_date}
            onChange={handleChange('applied_date')}
          />
        </Field>
      </div>

      <Field id={idOf('notes')} label="Notes" error={errors.notes}>
        <textarea
          id={idOf('notes')}
          rows={3}
          className={inputClass}
          value={values.notes}
          onChange={handleChange('notes')}
        />
      </Field>

      <div className="flex gap-3">
        <button type="submit" disabled={submitting} className={primaryButton}>
          {submitting ? 'Saving…' : submitLabel}
        </button>
        {onCancel && (
          <button type="button" onClick={onCancel} className={secondaryButton}>
            Cancel
          </button>
        )}
      </div>
    </form>
  )
}
