import { useState } from 'react'
import { useApplications } from './hooks/useApplications'
import AgentPage from './pages/AgentPage'
import InterviewPage from './pages/InterviewPage'
import KnowledgePage from './pages/KnowledgePage'
import MatchPage from './pages/MatchPage'
import TrackerPage from './pages/TrackerPage'

type Tab = 'tracker' | 'match' | 'notes' | 'agent' | 'interview'

const TABS: { id: Tab; label: string }[] = [
  { id: 'tracker', label: 'Tracker' },
  { id: 'match', label: 'Match tool' },
  { id: 'notes', label: 'Notes' },
  { id: 'agent', label: 'Ask the agent' },
  { id: 'interview', label: 'Interview prep' },
]

export default function App() {
  const [tab, setTab] = useState<Tab>('tracker')
  // Pages stay mounted once opened (so nothing you typed or generated is lost when you switch tabs).
  // The newer tabs are only mounted on their first visit, so opening the app does not fire their requests.
  const [visited, setVisited] = useState<ReadonlySet<Tab>>(new Set<Tab>(['tracker', 'match']))

  // "Lifting state up": the application list is loaded ONCE here and handed down to the pages that need it.
  const applicationsState = useApplications()

  function openTab(next: Tab) {
    setTab(next)
    setVisited((previous) => (previous.has(next) ? previous : new Set(previous).add(next)))
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-4">
          <h1 className="text-xl font-bold">AI Career Copilot</h1>
          <nav aria-label="Main" className="flex flex-wrap gap-2">
            {TABS.map(({ id, label }) => (
              <button
                key={id}
                type="button"
                onClick={() => openTab(id)}
                aria-current={tab === id ? 'page' : undefined}
                className={`rounded-md px-4 py-2 text-sm font-medium ${
                  tab === id ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                {label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-6">
        <div hidden={tab !== 'tracker'}>
          <TrackerPage {...applicationsState} />
        </div>
        <div hidden={tab !== 'match'}>
          <MatchPage
            applications={applicationsState.applications}
            reloadApplications={applicationsState.reload}
          />
        </div>
        <div hidden={tab !== 'notes'}>{visited.has('notes') && <KnowledgePage />}</div>
        <div hidden={tab !== 'agent'}>{visited.has('agent') && <AgentPage />}</div>
        <div hidden={tab !== 'interview'}>
          {visited.has('interview') && <InterviewPage applications={applicationsState.applications} />}
        </div>
      </main>
    </div>
  )
}
