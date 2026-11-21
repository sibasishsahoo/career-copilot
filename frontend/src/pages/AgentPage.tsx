import { useId, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { askAgent, errorMessage } from '../api/client'
import type { AgentAskResponse } from '../api/types'
import AgentTrace from '../components/AgentTrace'
import ErrorBanner from '../components/ErrorBanner'
import { cardClass, inputClass, labelClass, primaryButton, secondaryButton } from '../components/ui'
import { EXAMPLE_QUESTIONS } from '../lib/agent'
import { validateQuestion } from '../lib/knowledge'

export default function AgentPage() {
  const inputId = useId()
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState<AgentAskResponse | null>(null)
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
      setResult(await askAgent(question.trim()))
    } catch (caught) {
      setProblem(errorMessage(caught))
    } finally {
      setAsking(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <h2 className="text-2xl font-bold text-slate-900">Ask the agent</h2>
        <p className="text-sm text-slate-500">
          The agent decides which tools to use (searching your notes, listing your applications, opening one),
          looks things up, and then answers. It can only read: it cannot change anything. Each step is one AI
          call, so a question takes about 2 to 4 calls and 10 to 30 seconds; on the free tier, wait a minute
          between questions.
        </p>
      </header>

      <section aria-label="Ask" className={`${cardClass} space-y-4`}>
        {problem && <ErrorBanner message={problem} onDismiss={() => setProblem(null)} />}
        <form onSubmit={handleSubmit} noValidate className="space-y-3">
          <div>
            <label htmlFor={inputId} className={labelClass}>
              Question for the agent
            </label>
            <textarea
              id={inputId}
              rows={3}
              className={inputClass}
              value={question}
              onChange={(event: ChangeEvent<HTMLTextAreaElement>) => setQuestion(event.target.value)}
            />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button type="submit" disabled={asking} className={primaryButton}>
              {asking ? 'Working… this can take a while' : 'Ask the agent'}
            </button>
            <span className="text-xs text-slate-500">or try:</span>
            {EXAMPLE_QUESTIONS.map((example) => (
              <button key={example} type="button" onClick={() => setQuestion(example)} className={secondaryButton}>
                {example}
              </button>
            ))}
          </div>
        </form>
      </section>

      {result && (
        <section aria-label="Agent answer" className={`${cardClass} space-y-4`}>
          <h3 className="text-lg font-semibold text-slate-900">Answer</h3>
          {result.stopped_reason === 'max_steps' && (
            <p role="status" className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              The agent ran out of steps before it could finish, so this is a partial result.
            </p>
          )}
          <p className="whitespace-pre-wrap text-slate-800">{result.answer}</p>
          <AgentTrace steps={result.steps} />
        </section>
      )}
    </div>
  )
}
