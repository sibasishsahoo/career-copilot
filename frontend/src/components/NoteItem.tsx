import { useState } from 'react'
import { deleteDocument, errorMessage, getDocument } from '../api/client'
import type { KnowledgeChunk, KnowledgeDocument } from '../api/types'
import { formatDate } from '../lib/format'
import ErrorBanner from './ErrorBanner'
import { dangerButton, secondaryButton } from './ui'

interface Props {
  note: KnowledgeDocument
  onChanged: () => void // tells the page to reload the list after a delete
}

export default function NoteItem({ note, onChanged }: Props) {
  const [chunks, setChunks] = useState<KnowledgeChunk[] | null>(null)
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function toggleChunks() {
    if (open) {
      setOpen(false)
      return
    }
    setOpen(true)
    if (chunks !== null) return // already loaded once
    setLoading(true)
    setError(null)
    try {
      setChunks((await getDocument(note.id)).chunks)
    } catch (problem) {
      setError(errorMessage(problem))
    } finally {
      setLoading(false)
    }
  }

  async function remove() {
    setBusy(true)
    setError(null)
    try {
      await deleteDocument(note.id)
      onChanged()
    } catch (problem) {
      setError(errorMessage(problem))
      setBusy(false)
    }
  }

  return (
    <li className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-slate-900">{note.title}</h3>
          <p className="text-sm text-slate-500">
            {`${note.chunk_count} ${note.chunk_count === 1 ? 'passage' : 'passages'} · ${note.char_count.toLocaleString('en-US')} characters · added ${formatDate(note.created_at)}`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={toggleChunks}
            aria-expanded={open}
            aria-label={`${open ? 'Hide' : 'Show'} passages of ${note.title}`}
            className={secondaryButton}
          >
            {open ? 'Hide passages' : 'Show passages'}
          </button>
          {confirming ? (
            <>
              <span className="text-sm text-slate-700">Delete this note?</span>
              <button type="button" onClick={remove} disabled={busy} className={dangerButton}>
                Yes, delete
              </button>
              <button type="button" onClick={() => setConfirming(false)} className={secondaryButton}>
                Cancel
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => setConfirming(true)}
              aria-label={`Delete ${note.title}`}
              className={dangerButton}
            >
              Delete
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="mt-3">
          <ErrorBanner message={error} onDismiss={() => setError(null)} />
        </div>
      )}

      {open && (
        <div className="mt-3 space-y-2 border-t border-slate-100 pt-3">
          <p className="text-xs text-slate-500">
            This is how your note was split. Each passage is turned into numbers (an embedding) and searched separately.
          </p>
          {loading && <p role="status" className="text-sm text-slate-500">Loading…</p>}
          {chunks && (
            <ol className="space-y-2">
              {chunks.map((chunk) => (
                <li key={chunk.index} className="rounded-md bg-slate-50 p-3 text-sm">
                  <p className="mb-1 text-xs font-medium text-slate-500">{`Passage ${chunk.index + 1}`}</p>
                  <p className="whitespace-pre-wrap text-slate-700">{chunk.text}</p>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </li>
  )
}
