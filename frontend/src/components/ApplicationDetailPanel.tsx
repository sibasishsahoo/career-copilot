import { useEffect, useId, useState } from 'react'
import type { ChangeEvent } from 'react'
import {
  changeStatus,
  deleteApplication,
  errorMessage,
  getApplication,
  removeMatch,
  updateApplication,
} from '../api/client'
import { APPLICATION_STATUSES } from '../api/types'
import type { ApplicationCreate, ApplicationDetail, ApplicationStatus } from '../api/types'
import { valuesFromApplication } from '../lib/applicationForm'
import { formatDateTime } from '../lib/format'
import { STATUS_LABELS } from '../lib/status'
import ApplicationForm from './ApplicationForm'
import ErrorBanner from './ErrorBanner'
import MatchSnapshotView from './MatchSnapshotView'
import StatusBadge from './StatusBadge'
import { dangerButton, inputClass, labelClass, primaryButton, secondaryButton } from './ui'

interface Props {
  applicationId: number
  onClose: () => void
  onChanged: () => void // tells the page to reload its list after any change
}

export default function ApplicationDetailPanel({ applicationId, onClose, onChanged }: Props) {
  const ids = useId()
  const [detail, setDetail] = useState<ApplicationDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [targetStatus, setTargetStatus] = useState<ApplicationStatus>('applied')
  const [statusNote, setStatusNote] = useState('')
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    getApplication(applicationId)
      .then((loaded) => {
        if (cancelled) return
        setDetail(loaded)
        setTargetStatus(loaded.status)
      })
      .catch((problem: unknown) => {
        if (!cancelled) setError(errorMessage(problem))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [applicationId])

  /** Run an async action with shared "busy" and error handling. */
  async function run(action: () => Promise<void>) {
    setBusy(true)
    setError(null)
    try {
      await action()
    } catch (problem) {
      setError(errorMessage(problem))
    } finally {
      setBusy(false)
    }
  }

  function moveStatus() {
    if (!detail) return
    void run(async () => {
      const updated = await changeStatus(detail.id, targetStatus, statusNote.trim() || undefined)
      setDetail(updated)
      setStatusNote('')
      onChanged()
    })
  }

  // Used by the form: errors are thrown (not caught here) so the form can display them itself.
  async function saveDetails(payload: ApplicationCreate) {
    if (!detail) return
    const updated = await updateApplication(detail.id, payload)
    setDetail(updated)
    onChanged()
  }

  function removeSavedMatch() {
    if (!detail) return
    void run(async () => {
      await removeMatch(detail.id)
      setDetail(await getApplication(detail.id))
      onChanged()
    })
  }

  function deleteThisApplication() {
    if (!detail) return
    void run(async () => {
      await deleteApplication(detail.id)
      onChanged()
      onClose()
    })
  }

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-slate-900/40" onClick={onClose} aria-hidden="true" />

      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Application details"
        className="relative z-10 h-full w-full max-w-xl space-y-6 overflow-y-auto bg-white p-6 shadow-xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-slate-900">
              {detail ? detail.company : 'Application'}
            </h2>
            {detail && <p className="text-slate-600">{detail.job_title}</p>}
          </div>
          <div className="flex items-center gap-3">
            {detail && <StatusBadge status={detail.status} />}
            <button type="button" onClick={onClose} aria-label="Close" className={secondaryButton}>
              ✕
            </button>
          </div>
        </div>

        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
        {loading && <p role="status">Loading…</p>}

        {detail && (
          <>
            <section aria-label="Change status" className="space-y-3">
              <h3 className="font-semibold text-slate-900">Move to another status</h3>
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label htmlFor={`${ids}-status`} className={labelClass}>
                    New status
                  </label>
                  <select
                    id={`${ids}-status`}
                    className={inputClass}
                    value={targetStatus}
                    onChange={(event: ChangeEvent<HTMLSelectElement>) =>
                      setTargetStatus(event.target.value as ApplicationStatus)
                    }
                  >
                    {APPLICATION_STATUSES.map((status) => (
                      <option key={status} value={status}>
                        {STATUS_LABELS[status]}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor={`${ids}-note`} className={labelClass}>
                    Note (optional)
                  </label>
                  <input
                    id={`${ids}-note`}
                    className={inputClass}
                    value={statusNote}
                    onChange={(event: ChangeEvent<HTMLInputElement>) => setStatusNote(event.target.value)}
                  />
                </div>
              </div>
              <button
                type="button"
                onClick={moveStatus}
                disabled={busy || targetStatus === detail.status}
                className={primaryButton}
              >
                Move
              </button>
            </section>

            <section aria-label="Details" className="space-y-3">
              <h3 className="font-semibold text-slate-900">Details</h3>
              <ApplicationForm
                key={detail.id}
                initialValues={valuesFromApplication(detail)}
                submitLabel="Save changes"
                showStatus={false}
                onSubmit={saveDetails}
              />
            </section>

            <section aria-label="History" className="space-y-3">
              <h3 className="font-semibold text-slate-900">History</h3>
              <ol className="space-y-2 border-l-2 border-slate-200 pl-4 text-sm">
                {detail.status_history.map((change) => (
                  <li key={change.id}>
                    <p className="font-medium text-slate-800">
                      {change.from_status === null
                        ? `Created as ${STATUS_LABELS[change.to_status]}`
                        : `${STATUS_LABELS[change.from_status]} → ${STATUS_LABELS[change.to_status]}`}
                    </p>
                    {change.note && <p className="text-slate-600">{change.note}</p>}
                    <p className="text-xs text-slate-400">{formatDateTime(change.changed_at)}</p>
                  </li>
                ))}
              </ol>
            </section>

            <section aria-label="Saved match" className="space-y-3">
              <h3 className="font-semibold text-slate-900">Saved match</h3>
              {detail.match_snapshot ? (
                <>
                  <MatchSnapshotView snapshot={detail.match_snapshot} />
                  <button type="button" onClick={removeSavedMatch} disabled={busy} className={secondaryButton}>
                    Remove saved match
                  </button>
                </>
              ) : (
                <p className="text-sm text-slate-500">
                  No match saved yet. Use the Match tool to analyze a job and save the result here.
                </p>
              )}
            </section>

            <section aria-label="Danger zone" className="border-t border-slate-200 pt-4">
              {confirmingDelete ? (
                <div className="flex items-center gap-3">
                  <p className="text-sm text-slate-700">Delete this application and its history?</p>
                  <button type="button" onClick={deleteThisApplication} disabled={busy} className={dangerButton}>
                    Yes, delete
                  </button>
                  <button type="button" onClick={() => setConfirmingDelete(false)} className={secondaryButton}>
                    Cancel
                  </button>
                </div>
              ) : (
                <button type="button" onClick={() => setConfirmingDelete(true)} className={dangerButton}>
                  Delete application
                </button>
              )}
            </section>
          </>
        )}
      </aside>
    </div>
  )
}
