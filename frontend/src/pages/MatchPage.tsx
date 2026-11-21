import { useId, useState } from 'react'
import type { ChangeEvent } from 'react'
import { errorMessage, matchJob } from '../api/client'
import type { Application, MatchResult, ParsedResume } from '../api/types'
import ErrorBanner from '../components/ErrorBanner'
import MatchResultView from '../components/MatchResultView'
import ResumeUpload from '../components/ResumeUpload'
import SaveMatchPanel from '../components/SaveMatchPanel'
import { cardClass, inputClass, labelClass, primaryButton } from '../components/ui'

const MIN_JOB_CHARS = 50 // same limits as the backend (backend/app/schemas/job.py)
const MAX_JOB_CHARS = 15000

interface Props {
  applications: Application[]
  reloadApplications: () => void
}

interface Outcome {
  result: MatchResult
  jobText: string // the exact text that was analyzed
  runNumber: number // changes on every analysis, so the save panel starts fresh each time
}

export default function MatchPage({ applications, reloadApplications }: Props) {
  const jobFieldId = useId()
  // The parsed resume lives ONLY here, in memory. Not in localStorage, not in the database.
  const [resume, setResume] = useState<ParsedResume | null>(null)
  const [jobText, setJobText] = useState('')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [outcome, setOutcome] = useState<Outcome | null>(null)
  const [runCount, setRunCount] = useState(0)

  const trimmedLength = jobText.trim().length
  const canAnalyze = resume !== null && trimmedLength >= MIN_JOB_CHARS && !running

  async function handleAnalyze() {
    if (!resume) return
    const text = jobText.trim()
    setRunning(true)
    setError(null)
    try {
      const result = await matchJob(resume, text)
      const runNumber = runCount + 1
      setRunCount(runNumber)
      setOutcome({ result, jobText: text, runNumber })
    } catch (problem) {
      setError(errorMessage(problem))
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <ResumeUpload parsed={resume} onParsed={setResume} />

      <section aria-label="Job posting" className={`${cardClass} space-y-3`}>
        <h2 className="text-lg font-semibold text-slate-900">2. The job</h2>
        <div>
          <label htmlFor={jobFieldId} className={labelClass}>
            Job description
          </label>
          <textarea
            id={jobFieldId}
            rows={10}
            maxLength={MAX_JOB_CHARS}
            className={inputClass}
            placeholder="Paste the full job posting here…"
            value={jobText}
            onChange={(event: ChangeEvent<HTMLTextAreaElement>) => setJobText(event.target.value)}
          />
          <p className="mt-1 text-xs text-slate-500">
            {`${trimmedLength} / ${MAX_JOB_CHARS} characters (at least ${MIN_JOB_CHARS} needed)`}
          </p>
        </div>
      </section>

      <section aria-label="Analyze" className="space-y-3">
        <button type="button" onClick={handleAnalyze} disabled={!canAnalyze} className={primaryButton}>
          {running ? 'Analyzing… this can take a few seconds' : '3. Analyze match'}
        </button>
        {!resume && <p className="text-sm text-slate-500">Parse your resume first.</p>}
        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
      </section>

      {outcome && (
        <>
          <MatchResultView result={outcome.result} />
          <SaveMatchPanel
            key={outcome.runNumber}
            result={outcome.result}
            jobText={outcome.jobText}
            applications={applications}
            onSaved={reloadApplications}
          />
        </>
      )}
    </div>
  )
}
