// Same limits as the backend (backend/app/schemas/knowledge.py).
export const MAX_NOTE_TITLE_CHARS = 200
export const MAX_NOTE_CHARS = 50_000
export const MAX_QUESTION_CHARS = 500

export interface NoteValues {
  title: string
  text: string
}

export type NoteErrors = Partial<Record<keyof NoteValues, string>>

/** Rules mirrored from the backend so mistakes show up instantly. The backend re-checks everything. */
export function validateNote(values: NoteValues): NoteErrors {
  const errors: NoteErrors = {}
  const title = values.title.trim()
  if (!title) errors.title = 'Title is required.'
  else if (title.length > MAX_NOTE_TITLE_CHARS) errors.title = `Title must be ${MAX_NOTE_TITLE_CHARS} characters or fewer.`

  const text = values.text.trim()
  if (!text) errors.text = 'Note text is required.'
  else if (text.length > MAX_NOTE_CHARS) errors.text = `Note text must be ${MAX_NOTE_CHARS.toLocaleString('en-US')} characters or fewer.`
  return errors
}

/** A question or search text: returns a message if unusable, or null. */
export function validateQuestion(text: string): string | null {
  const trimmed = text.trim()
  if (!trimmed) return 'Please type something first.'
  if (trimmed.length > MAX_QUESTION_CHARS) return `Please keep it to ${MAX_QUESTION_CHARS} characters or fewer.`
  return null
}

export function formatScore(score: number): string {
  return score.toFixed(2)
}

export type AnswerPart = { type: 'text'; text: string } | { type: 'citation'; number: number }

/** Split "I cut it to 12 minutes [1] and mentored two interns [2]." into text and citation parts,
 *  so the UI can show the [1] and [2] as small badges that point at the sources. */
export function splitCitations(answer: string): AnswerPart[] {
  const parts: AnswerPart[] = []
  let last = 0
  for (const match of answer.matchAll(/\[(\d+)\]/g)) {
    const index = match.index ?? 0
    if (index > last) parts.push({ type: 'text', text: answer.slice(last, index) })
    parts.push({ type: 'citation', number: Number(match[1]) })
    last = index + match[0].length
  }
  if (last < answer.length) parts.push({ type: 'text', text: answer.slice(last) })
  return parts
}
