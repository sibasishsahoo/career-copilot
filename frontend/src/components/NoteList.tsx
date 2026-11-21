import type { KnowledgeDocument } from '../api/types'
import NoteItem from './NoteItem'

interface Props {
  notes: KnowledgeDocument[]
  loading: boolean
  onChanged: () => void
}

export default function NoteList({ notes, loading, onChanged }: Props) {
  return (
    <section aria-label="Your notes" className="space-y-3">
      <h2 className="text-lg font-semibold text-slate-900">{`Your notes (${notes.length})`}</h2>
      {loading && notes.length === 0 && <p role="status" className="text-sm text-slate-500">Loading notes…</p>}
      {!loading && notes.length === 0 && (
        <p className="rounded-md border border-dashed border-slate-300 p-4 text-sm text-slate-500">
          You have no notes yet. Add your first one above: searching, asking and interview prep all work from your notes.
        </p>
      )}
      <ul className="space-y-3">
        {notes.map((note) => (
          <NoteItem key={note.id} note={note} onChanged={onChanged} />
        ))}
      </ul>
    </section>
  )
}
