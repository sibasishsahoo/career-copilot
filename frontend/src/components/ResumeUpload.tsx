import { useId, useState } from 'react'
import type { ChangeEvent } from 'react'
import { errorMessage, parseResume } from '../api/client'
import type { ParsedResume } from '../api/types'
import { validateResumeFile } from '../lib/files'
import ErrorBanner from './ErrorBanner'
import { cardClass, inputClass, labelClass, primaryButton, secondaryButton } from './ui'

interface Props {
  parsed: ParsedResume | null
  onParsed: (resume: ParsedResume | null) => void
}

export default function ResumeUpload({ parsed, onParsed }: Props) {
  const inputId = useId()
  const [file, setFile] = useState<File | null>(null)
  const [parsing, setParsing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Changing a React `key` throws the old <input> away and creates a fresh one. That is the
  // only way to clear a file input, because browsers do not let code set its value.
  const [inputKey, setInputKey] = useState(0)

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const chosen = event.target.files?.[0] ?? null
    setError(null)
    if (chosen) {
      const problem = validateResumeFile(chosen.name, chosen.size)
      if (problem) {
        setError(problem)
        setFile(null)
        return
      }
    }
    setFile(chosen)
  }

  async function handleParse() {
    if (!file) return
    setParsing(true)
    setError(null)
    try {
      const response = await parseResume(file)
      onParsed(response.parsed)
    } catch (problem) {
      setError(errorMessage(problem))
    } finally {
      setParsing(false)
    }
  }

  function handleRemove() {
    onParsed(null)
    setFile(null)
    setError(null)
    setInputKey((current) => current + 1)
  }

  return (
    <section aria-label="Resume" className={`${cardClass} space-y-4`}>
      <div>
        <h2 className="text-lg font-semibold text-slate-900">1. Your resume</h2>
        <p className="text-sm text-slate-500">
          The resume is kept only in this page&apos;s memory and is never saved by this app. To read it, the
          backend sends its text to your configured AI provider (for example Gemini). Use an anonymized
          resume if you are on a free tier.
        </p>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {parsed ? (
        <div className="space-y-3">
          <p className="text-sm text-slate-700">
            <span className="font-semibold">{parsed.full_name}</span>
            {parsed.location ? ` · ${parsed.location}` : ''}
          </p>
          <p className="text-sm text-slate-500">
            {`${parsed.skills.length} skills · ${parsed.experience.length} positions · ${parsed.education.length} education entries`}
          </p>
          {parsed.skills.length > 0 && (
            <ul className="flex flex-wrap gap-2" aria-label="Skills found in your resume">
              {parsed.skills.map((skill, index) => (
                <li key={`${skill}-${index}`} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">
                  {skill}
                </li>
              ))}
            </ul>
          )}
          <button type="button" onClick={handleRemove} className={secondaryButton}>
            Remove resume
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          <div>
            <label htmlFor={inputId} className={labelClass}>
              Resume file (PDF or DOCX, up to 5 MB)
            </label>
            <input
              key={inputKey}
              id={inputId}
              type="file"
              accept=".pdf,.docx"
              onChange={handleFileChange}
              className={inputClass}
            />
          </div>
          <button type="button" onClick={handleParse} disabled={!file || parsing} className={primaryButton}>
            {parsing ? 'Parsing…' : 'Parse resume'}
          </button>
        </div>
      )}
    </section>
  )
}
