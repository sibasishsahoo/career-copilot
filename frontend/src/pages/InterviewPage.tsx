import { useEffect, useId, useState } from 'react'
import type { ChangeEvent } from 'react'
import { ApiError, deleteInterviewPrep, errorMessage, generateInterviewPrep, getInterviewPrep } from '../api/client'
import type { Application, InterviewPrep } from '../api/types'
import ErrorBanner from '../components/ErrorBanner'
import InterviewPrepView from '../components/InterviewPrepView'
import { cardClass, dangerButton, inputClass, labelClass, primaryButton, secondaryButton } from '../components/ui'
import { DEFAULT_QUESTION_COUNT, QUESTION_COUNT_OPTIONS, isNoSavedMatch, isNotFound } from '../lib/interview'
import { STATUS_LABELS } from '../lib/status'

interface Props {
  applications: Application[] // shared with the Tracker tab
}

interface Problem {
  message: string
  noSavedMatch: boolean // the backend said 409: this application has no saved job match yet
}

export default function InterviewPage({ applications }: Props) {
  const ids = useId()
  const [selected, setSelected] = useState('')
  const [prep, setPrep] = useState<InterviewPrep | null>(null)
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false) // generating or deleting
  const [problem, setProblem] = useState<Problem | null>(null)
  const [questionCount, setQuestionCount] = useState<number>(DEFAULT_QUESTION_COUNT)
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  // Whenever another application is chosen, look for a pack that was saved earlier (no AI involved).
  useEffect(() => {
    setPrep(null)
    setProblem(null)
    setConfirmingDelete(false)
    if (!selected) return

    let cancelled = false
    setLoading(true)
    getInterviewPrep(Number(selected))
      .then((saved) => {
        if (!cancelled) setPrep(saved)
      })
      .catch((caught: unknown) => {
        // 404 just means "no pack yet": not an error. Anything else is.
        if (!cancelled && !isNotFound(caught)) setProblem({ message: errorMessage(caught), noSavedMatch: false })
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selected])

  async function handleGenerate() {
    setBusy(true)
    setProblem(null)
    try {
      setPrep(await generateInterviewPrep(Number(selected), questionCount))
    } catch (caught) {
      setProblem({ message: errorMessage(caught), noSavedMatch: isNoSavedMatch(caught) })
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete() {
    setBusy(true)
    setProblem(null)
    try {
      await deleteInterviewPrep(Number(selected))
      setPrep(null)
      setConfirmingDelete(false)
    } catch (caught) {
      setProblem({ message: errorMessage(caught), noSavedMatch: caught instanceof ApiError && caught.status === 409 })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header>
        <h2 className="text-2xl font-bold text-slate-900">Interview prep</h2>
        <p className="text-sm text-slate-500">
          Likely questions for a job, each with an answer outline built only from your own notes, and a clear
          flag where you have no story yet. It uses the job description saved with the application (from the
          Match tool) and never your resume. Generating takes 2 AI calls, so allow up to half a minute.
        </p>
      </header>

      <section aria-label="Choose an application" className={`${cardClass} space-y-4`}>
        {applications.length === 0 ? (
          <p className="text-sm text-slate-500">Add an application in the Tracker tab first.</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor={`${ids}-application`} className={labelClass}>
                Application
              </label>
              <select
                id={`${ids}-application`}
                className={inputClass}
                value={selected}
                onChange={(event: ChangeEvent<HTMLSelectElement>) => setSelected(event.target.value)}
              >
                <option value="">Choose an application…</option>
                {applications.map((application) => (
                  <option key={application.id} value={String(application.id)}>
                    {`${application.company} — ${application.job_title} (${STATUS_LABELS[application.status]})`}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor={`${ids}-count`} className={labelClass}>
                Number of questions
              </label>
              <select
                id={`${ids}-count`}
                className={inputClass}
                value={questionCount}
                onChange={(event: ChangeEvent<HTMLSelectElement>) => setQuestionCount(Number(event.target.value))}
              >
                {QUESTION_COUNT_OPTIONS.map((count) => (
                  <option key={count} value={count}>
                    {count}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}

        {selected && (
          <div className="flex flex-wrap items-center gap-3">
            <button type="button" onClick={handleGenerate} disabled={busy || loading} className={primaryButton}>
              {busy && !confirmingDelete ? 'Generating… this can take up to 30 seconds' : prep ? 'Regenerate interview prep' : 'Generate interview prep'}
            </button>
            {prep &&
              (confirmingDelete ? (
                <>
                  <span className="text-sm text-slate-700">Delete the saved prep?</span>
                  <button type="button" onClick={handleDelete} disabled={busy} className={dangerButton}>
                    Yes, delete prep
                  </button>
                  <button type="button" onClick={() => setConfirmingDelete(false)} className={secondaryButton}>
                    Cancel
                  </button>
                </>
              ) : (
                <button type="button" onClick={() => setConfirmingDelete(true)} className={secondaryButton}>
                  Delete saved prep
                </button>
              ))}
          </div>
        )}
      </section>

      {loading && <p role="status" className="text-sm text-slate-500">Looking for a saved prep…</p>}

      {problem && (
        <div className="space-y-2">
          <ErrorBanner message={problem.message} onDismiss={() => setProblem(null)} />
          {problem.noSavedMatch && (
            <p className="text-sm text-slate-600">
              Open the Match tool, analyze this job, and use &quot;Save to your tracker&quot; to attach the match to this
              application. Then come back here.
            </p>
          )}
        </div>
      )}

      {selected && !loading && !prep && !problem && (
        <p className="rounded-md border border-dashed border-slate-300 p-4 text-sm text-slate-500">
          No interview prep has been generated for this application yet.
        </p>
      )}

      {prep && <InterviewPrepView prep={prep} />}
    </div>
  )
}
