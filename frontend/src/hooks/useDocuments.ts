import { useCallback, useEffect, useState } from 'react'
import { errorMessage, listDocuments } from '../api/client'
import type { KnowledgeDocument } from '../api/types'

export interface DocumentsState {
  documents: KnowledgeDocument[]
  loading: boolean
  error: string | null
  reload: () => void
}

/** Loads the list of notes. Same pattern as useApplications. */
export function useDocuments(): DocumentsState {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [version, setVersion] = useState(0)

  useEffect(() => {
    let cancelled = false // ignore an outdated response if the effect re-runs or the page goes away
    setLoading(true)

    listDocuments()
      .then((data) => {
        if (cancelled) return
        setDocuments(data)
        setError(null)
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
  }, [version])

  const reload = useCallback(() => setVersion((current) => current + 1), [])
  return { documents, loading, error, reload }
}
