import { useCallback, useEffect, useState } from 'react'
import { errorMessage, listApplications } from '../api/client'
import type { Application } from '../api/types'

export interface ApplicationsState {
  applications: Application[]
  loading: boolean
  error: string | null
  reload: () => void
}

/**
 * Loads the application list and exposes reload().
 *
 * A "custom hook" is just a function whose name starts with "use" and that calls other hooks.
 * It lets several components share this loading logic instead of copy-pasting it.
 */
export function useApplications(): ApplicationsState {
  const [applications, setApplications] = useState<Application[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // Changing this number re-runs the effect below, which is how reload() works.
  const [version, setVersion] = useState(0)

  useEffect(() => {
    // `cancelled` stops a slow, outdated response from overwriting newer data:
    // when the effect re-runs (or the component disappears), the cleanup sets it to true.
    let cancelled = false
    setLoading(true)

    listApplications({ limit: 200 })
      .then((data) => {
        if (cancelled) return
        setApplications(data)
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

  return { applications, loading, error, reload }
}
