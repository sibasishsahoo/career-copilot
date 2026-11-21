import type { Application } from '../api/types'
import { formatDate } from '../lib/format'

interface Props {
  application: Application
  onOpen: (id: number) => void
}

export default function ApplicationCard({ application, onOpen }: Props) {
  return (
    <button
      type="button"
      onClick={() => onOpen(application.id)}
      className="block w-full rounded-lg border border-slate-200 bg-white p-3 text-left shadow-sm hover:border-blue-400 hover:shadow"
    >
      <span className="block font-semibold text-slate-900">{application.company}</span>
      <span className="block text-sm text-slate-600">{application.job_title}</span>
      {application.location && (
        <span className="mt-1 block text-xs text-slate-500">{application.location}</span>
      )}
      <span className="mt-2 block text-xs text-slate-400">Updated {formatDate(application.updated_at)}</span>
    </button>
  )
}
