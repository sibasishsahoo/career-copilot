import type { SearchResult } from '../api/types'
import { formatScore } from '../lib/knowledge'

interface Props {
  sources: SearchResult[]
  highlight?: number[] // source numbers the answer actually used
  emptyText: string
}

/** The passages that were found, best first, each with its similarity score. */
export default function SourceList({ sources, highlight = [], emptyText }: Props) {
  if (sources.length === 0) {
    return <p className="text-sm text-slate-500">{emptyText}</p>
  }
  return (
    <ol className="space-y-2">
      {sources.map((source) => {
        const used = highlight.includes(source.rank)
        return (
          <li
            key={`${source.doc_id}-${source.chunk_index}`}
            className={`rounded-md border p-3 text-sm ${used ? 'border-emerald-300 bg-emerald-50' : 'border-slate-200 bg-white'}`}
          >
            <p className="mb-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span className="font-semibold text-slate-700">{`Source ${source.rank}`}</span>
              <span>{source.title}</span>
              <span>{`similarity ${formatScore(source.score)}`}</span>
              {used && <span className="font-medium text-emerald-700">used in the answer</span>}
            </p>
            <p className="whitespace-pre-wrap text-slate-700">{source.text}</p>
          </li>
        )
      })}
    </ol>
  )
}
