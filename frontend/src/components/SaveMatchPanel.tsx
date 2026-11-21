import { useId, useState } from 'react'
import type { ChangeEvent } from 'react'
import { attachMatch, createApplication, errorMessage } from '../api/client'
import type { Application, MatchResult } from '../api/types'
import { buildSnapshot } from '../lib/matchSnapshot'
import { STATUS_LABELS } from '../lib/status'
import ErrorBanner from './ErrorBanner'
import { cardClass, inputClass, labelClass, primaryButton } from './ui'

interface Props {
  result: MatchResult
  jobText: string // the text that was analyzed (the textarea may have been edited since)
  applications: Application[]
  onSaved: () => void
}

const NEW_APPLICATION = 'new'

export default function SaveMatchPanel({ result, jobText, applications, onSaved }: Props) {
  const ids = useId()
  const [target, setTarget] = useState<string>(NEW_APPLICATION)
  const [company, setCompany] = useState(result.job.company ?? '')
  const [jobTitle, setJobTitle] = useState(result.job.job_title)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savedMessage, setSavedMessage] = useState<string | null>(null)

  async function handleSave() {
    setError(null)
    setSavedMessage(null)
    setSaving(true)
    try {
      const snapshot = buildSnapshot(jobText, result)

      if (target === NEW_APPLICATION) {
        if (!company.trim() || !jobTitle.trim()) {
          setError('Company and job title are required.')
          return
        }
        const created = await createApplication({
          company: company.trim(),
          job_title: jobTitle.trim(),
          status: 'wishlist',
        })
        onSaved() // refresh the list now, even if attaching fails below
        try {
          await attachMatch(created.id, snapshot)
        } catch (problem) {
          setError(`The application was created, but saving the match failed: ${errorMessage(problem)}`)
          return
        }
        setSavedMessage(`Saved to the new application "${created.company}".`)
      } else {
        const id = Number(target)
        await attachMatch(id, snapshot)
        const application = applications.find((candidate) => candidate.id === id)
        setSavedMessage(`Saved to "${application ? application.company : 'the application'}".`)
      }
      onSaved()
    } catch (problem) {
      setError(errorMessage(problem))
    } finally {
      setSaving(false)
    }
  }

  return (
    <section aria-label="Save match" className={`${cardClass} space-y-4`}>
      <div>
        <h2 className="text-lg font-semibold text-slate-900">4. Save to your tracker</h2>
        <p className="text-sm text-slate-500">
          Saves the job description, score and skill lists (never the resume). Saving replaces any match
          already saved on that application.
        </p>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
      {savedMessage && (
        <p role="status" className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {savedMessage}
        </p>
      )}

      <div>
        <label htmlFor={`${ids}-target`} className={labelClass}>
          Save to
        </label>
        <select
          id={`${ids}-target`}
          className={inputClass}
          value={target}
          onChange={(event: ChangeEvent<HTMLSelectElement>) => setTarget(event.target.value)}
        >
          <option value={NEW_APPLICATION}>Create a new application</option>
          {applications.map((application) => (
            <option key={application.id} value={String(application.id)}>
              {`${application.company} — ${application.job_title} (${STATUS_LABELS[application.status]})`}
            </option>
          ))}
        </select>
      </div>

      {target === NEW_APPLICATION && (
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor={`${ids}-company`} className={labelClass}>
              Company
            </label>
            <input
              id={`${ids}-company`}
              className={inputClass}
              value={company}
              onChange={(event: ChangeEvent<HTMLInputElement>) => setCompany(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor={`${ids}-title`} className={labelClass}>
              Job title
            </label>
            <input
              id={`${ids}-title`}
              className={inputClass}
              value={jobTitle}
              onChange={(event: ChangeEvent<HTMLInputElement>) => setJobTitle(event.target.value)}
            />
          </div>
        </div>
      )}

      <button type="button" onClick={handleSave} disabled={saving} className={primaryButton}>
        {saving ? 'Saving…' : 'Save match'}
      </button>
    </section>
  )
}
