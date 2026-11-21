import { useId, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { errorMessage } from '../api/client'
import { MAX_NOTE_CHARS, validateNote } from '../lib/knowledge'
import type { NoteErrors } from '../lib/knowledge'
import ErrorBanner from './ErrorBanner'
import { cardClass, inputClass, labelClass, primaryButton } from './ui'

interface Props {
  onSubmit: (values: { title: string; text: string }) => Promise<void>
}

export default function NoteForm({ onSubmit }: Props) {
  const ids = useId()
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [errors, setErrors] = useState<NoteErrors>({})
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [savedMessage, setSavedMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const found = validateNote({ title, text })
    setErrors(found)
    setSubmitError(null)
    setSavedMessage(null)
    if (Object.keys(found).length > 0) return

    setSubmitting(true)
    try {
      await onSubmit({ title: title.trim(), text: text.trim() })
      setSavedMessage(`Saved "${title.trim()}".`)
      setTitle('')
      setText('')
    } catch (problem) {
      setSubmitError(errorMessage(problem))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section aria-label="Add a note" className={`${cardClass} space-y-4`}>
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Add a note</h2>
        <p className="text-sm text-slate-500">
          Write a project, an achievement or a STAR story (Situation, Task, Action, Result) in your own words.
          The more concrete (numbers, tools, outcomes), the better your interview prep will be. Notes are split
          into passages and stored on your own machine.
        </p>
      </div>

      {submitError && <ErrorBanner message={submitError} onDismiss={() => setSubmitError(null)} />}
      {savedMessage && (
        <p role="status" className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {savedMessage}
        </p>
      )}

      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div>
          <label htmlFor={`${ids}-title`} className={labelClass}>
            Note title
          </label>
          <input
            id={`${ids}-title`}
            className={inputClass}
            value={title}
            onChange={(event: ChangeEvent<HTMLInputElement>) => setTitle(event.target.value)}
            aria-invalid={errors.title ? true : undefined}
            aria-describedby={errors.title ? `${ids}-title-error` : undefined}
          />
          {errors.title && (
            <p id={`${ids}-title-error`} className="mt-1 text-sm text-red-600">
              {errors.title}
            </p>
          )}
        </div>

        <div>
          <label htmlFor={`${ids}-text`} className={labelClass}>
            Note text
          </label>
          <textarea
            id={`${ids}-text`}
            rows={7}
            className={inputClass}
            value={text}
            onChange={(event: ChangeEvent<HTMLTextAreaElement>) => setText(event.target.value)}
            aria-invalid={errors.text ? true : undefined}
            aria-describedby={errors.text ? `${ids}-text-error` : undefined}
          />
          <p className="mt-1 text-xs text-slate-500">{`${text.trim().length.toLocaleString('en-US')} / ${MAX_NOTE_CHARS.toLocaleString('en-US')} characters`}</p>
          {errors.text && (
            <p id={`${ids}-text-error`} className="mt-1 text-sm text-red-600">
              {errors.text}
            </p>
          )}
        </div>

        <button type="submit" disabled={submitting} className={primaryButton}>
          {submitting ? 'Saving…' : 'Add note'}
        </button>
      </form>
    </section>
  )
}
