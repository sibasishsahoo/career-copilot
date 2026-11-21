import { addDocument } from '../api/client'
import AskPanel from '../components/AskPanel'
import ErrorBanner from '../components/ErrorBanner'
import NoteForm from '../components/NoteForm'
import NoteList from '../components/NoteList'
import SearchPanel from '../components/SearchPanel'
import { useDocuments } from '../hooks/useDocuments'

export default function KnowledgePage() {
  const { documents, loading, error, reload } = useDocuments()

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header>
        <h2 className="text-2xl font-bold text-slate-900">Your career notes</h2>
        <p className="text-sm text-slate-500">
          Your own stories and achievements. They are the raw material for answers and for interview prep. Your
          resume is never stored here.
        </p>
      </header>

      {error && <ErrorBanner message={error} onRetry={reload} />}

      <NoteForm
        onSubmit={async (values) => {
          await addDocument(values)
          reload()
        }}
      />
      <NoteList notes={documents} loading={loading} onChanged={reload} />
      <SearchPanel />
      <AskPanel hasNotes={documents.length > 0} />
    </div>
  )
}
