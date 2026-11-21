import { useId, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { errorMessage, searchKnowledge } from '../api/client'
import type { SearchResult } from '../api/types'
import { validateQuestion } from '../lib/knowledge'
import ErrorBanner from './ErrorBanner'
import SourceList from './SourceList'
import { cardClass, inputClass, labelClass, secondaryButton } from './ui'

export default function SearchPanel() {
  const inputId = useId()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const invalid = validateQuestion(query)
    if (invalid) {
      setProblem(invalid)
      return
    }
    setSearching(true)
    setProblem(null)
    try {
      setResults((await searchKnowledge(query.trim())).results)
    } catch (caught) {
      setProblem(errorMessage(caught))
    } finally {
      setSearching(false)
    }
  }

  return (
    <section aria-label="Search your notes" className={`${cardClass} space-y-4`}>
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Search your notes</h2>
        <p className="text-sm text-slate-500">
          Finds passages by meaning, not just matching words. No AI writes anything here: you see exactly what
          the AI would be given, and how closely each passage matches (1.00 is a perfect match).
        </p>
      </div>
      {problem && <ErrorBanner message={problem} onDismiss={() => setProblem(null)} />}
      <form onSubmit={handleSubmit} noValidate className="flex flex-wrap items-end gap-3">
        <div className="min-w-64 flex-1">
          <label htmlFor={inputId} className={labelClass}>
            Search text
          </label>
          <input
            id={inputId}
            className={inputClass}
            value={query}
            onChange={(event: ChangeEvent<HTMLInputElement>) => setQuery(event.target.value)}
            placeholder="for example: reducing deployment time"
          />
        </div>
        <button type="submit" disabled={searching} className={secondaryButton}>
          {searching ? 'Searching…' : 'Search'}
        </button>
      </form>
      {results && <SourceList sources={results} emptyText="Nothing in your notes matched." />}
    </section>
  )
}
