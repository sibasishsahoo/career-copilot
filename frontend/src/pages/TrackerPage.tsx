import { useMemo, useState } from 'react'
import type { ChangeEvent } from 'react'
import { createApplication } from '../api/client'
import type { ApplicationsState } from '../hooks/useApplications'
import ApplicationCard from '../components/ApplicationCard'
import ApplicationDetailPanel from '../components/ApplicationDetailPanel'
import ApplicationForm from '../components/ApplicationForm'
import ErrorBanner from '../components/ErrorBanner'
import { inputClass, primaryButton } from '../components/ui'
import { EMPTY_VALUES } from '../lib/applicationForm'
import { BOARD_STATUSES, STATUS_LABELS, filterApplications, groupByStatus } from '../lib/status'

type Props = ApplicationsState

export default function TrackerPage({ applications, loading, error, reload }: Props) {
  const [search, setSearch] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)

  // useMemo: only recompute when the inputs change, not on every render.
  const visible = useMemo(() => filterApplications(applications, search), [applications, search])
  const columns = useMemo(() => groupByStatus(visible), [visible])

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-64 flex-1">
          <label htmlFor="tracker-search" className="sr-only">
            Search applications
          </label>
          <input
            id="tracker-search"
            type="search"
            className={inputClass}
            placeholder="Search company, title or location…"
            value={search}
            onChange={(event: ChangeEvent<HTMLInputElement>) => setSearch(event.target.value)}
          />
        </div>
        <button type="button" onClick={() => setShowCreate(true)} className={primaryButton}>
          New application
        </button>
      </div>

      {error && <ErrorBanner message={error} onRetry={reload} />}
      {loading && applications.length === 0 && <p role="status">Loading applications…</p>}

      <div className="grid auto-cols-[16rem] grid-flow-col gap-4 overflow-x-auto pb-4">
        {BOARD_STATUSES.map((status) => (
          <section
            key={status}
            aria-label={`${STATUS_LABELS[status]} column`}
            className="rounded-lg bg-slate-100 p-3"
          >
            <h2 className="mb-3 flex items-center justify-between text-sm font-semibold text-slate-700">
              {STATUS_LABELS[status]}
              <span className="rounded-full bg-white px-2 py-0.5 text-xs text-slate-500">
                {columns[status].length}
              </span>
            </h2>
            <div className="space-y-2">
              {columns[status].map((application) => (
                <ApplicationCard key={application.id} application={application} onOpen={setSelectedId} />
              ))}
              {columns[status].length === 0 && <p className="text-xs text-slate-400">No applications</p>}
            </div>
          </section>
        ))}
      </div>

      {showCreate && (
        <div className="fixed inset-0 z-40 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-slate-900/40" onClick={() => setShowCreate(false)} aria-hidden="true" />
          <div
            role="dialog"
            aria-modal="true"
            aria-label="New application"
            className="relative z-10 max-h-full w-full max-w-lg overflow-y-auto rounded-lg bg-white p-6 shadow-xl"
          >
            <h2 className="mb-4 text-xl font-bold text-slate-900">New application</h2>
            <ApplicationForm
              initialValues={EMPTY_VALUES}
              submitLabel="Create application"
              showStatus
              onCancel={() => setShowCreate(false)}
              onSubmit={async (payload) => {
                await createApplication(payload)
                reload()
                setShowCreate(false)
              }}
            />
          </div>
        </div>
      )}

      {selectedId !== null && (
        <ApplicationDetailPanel
          applicationId={selectedId}
          onClose={() => setSelectedId(null)}
          onChanged={reload}
        />
      )}
    </div>
  )
}
