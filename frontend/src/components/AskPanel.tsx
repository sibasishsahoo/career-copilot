import { useId, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { askKnowledge, errorMessage } from '../api/client'
import type { AskResponse } from '../api/types'
import { splitCitations, validateQuestion } from '../lib/knowledge'
import ErrorBanner from './ErrorBanner'
import SourceList from './SourceList'
import { cardClass, inputClass, labelClass, primaryButton } from './ui'

interface Props {
  hasNotes: boolean
}

function AnswerText({ response }: { response: AskResponse }) {
  const titles = new Map(response.sources.map((source) => [source.rank, source.title]))
  return (
    <p className="whitespace-pre-wrap text-slate-800">
      {splitCitations(response.answer).map((part, index) => {
        if (part.type === 'text') return <span key={index}>{part.text}</span>
        const title = titles.get(part.number)
        if (title === undefined) return <span key={index}>{`[${part.number}]`}</span> // cites a source we do not have
        return (
          <sup
            key={index}
            title={title}
            className="mx-0.5 rounded bg-emerald-100 px-1 text-xs font-semibold text-emerald-800"
          >
            {`[${part.number}]`}
          </sup>
        )
      })}
    </p>
  )
}

function Verdict({ response }: { response: AskResponse }) {
  if (!response.used_llm) {
    return <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">No relevant note found, so the AI was not called</span>
  }
  if (response.grounded) {
    return <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-800">Grounded in your notes</span>
  }
  return <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800">Not verified: the answer cites no valid note</span>
}

export default function AskPanel({ hasNotes }: Props) {
  const inputId = useId()
  const [question, setQuestion] = useState('')
  const [response, setResponse] = useState<AskResponse | null>(null)
  const [asking, setAsking] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const invalid = validateQuestion(question)
    if (invalid) {
      setProblem(invalid)
      return
    }
    setAsking(true)
    setProblem(null)
    try {
      setResponse(await askKnowledge(question.trim()))
    } catch (caught) {
      setProblem(errorMessage(caught))
    } finally {
      setAsking(false)
    }
  }

  return (
    <section aria-label="Ask your notes" className={`${cardClass} space-y-4`}>
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Ask your notes</h2>
        <p className="text-sm text-slate-500">
          The best matching passages are given to the AI, which must answer only from them and cite them. If
          nothing relevant is found it says so instead of guessing. Each question uses one AI call.
        </p>
        {!hasNotes && <p className="mt-1 text-sm text-amber-700">You have no notes yet, so there is nothing to answer from.</p>}
      </div>
      {problem && <ErrorBanner message={problem} onDismiss={() => setProblem(null)} />}
      <form onSubmit={handleSubmit} noValidate className="space-y-3">
        <div>
          <label htmlFor={inputId} className={labelClass}>
            Question for your notes
          </label>
          <textarea
            id={inputId}
            rows={2}
            className={inputClass}
            value={question}
            onChange={(event: ChangeEvent<HTMLTextAreaElement>) => setQuestion(event.target.value)}
            placeholder="for example: Which of my stories shows leadership?"
          />
        </div>
        <button type="submit" disabled={asking} className={primaryButton}>
          {asking ? 'Thinking…' : 'Ask your notes'}
        </button>
      </form>

      {response && (
        <div className="space-y-3 border-t border-slate-100 pt-4" aria-label="Answer">
          <Verdict response={response} />
          <AnswerText response={response} />
          <div>
            <h3 className="mb-2 text-sm font-medium text-slate-700">Passages found</h3>
            <SourceList
              sources={response.sources}
              highlight={response.sources_used}
              emptyText="No passage was relevant enough to use."
            />
          </div>
        </div>
      )}
    </section>
  )
}
