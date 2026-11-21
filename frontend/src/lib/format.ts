const PLACEHOLDER = '—'

/** "2026-10-01" -> "Oct 1, 2026". Date-only strings are read as calendar dates, not as UTC midnight,
 *  so the day never shifts because of the viewer's timezone. */
export function formatDate(value: string | null): string {
  if (!value) return PLACEHOLDER
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  const date = match
    ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
    : new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

/** "2026-10-01T10:30:00Z" -> "Oct 1, 2026, 4:00 PM" (shown in the viewer's own timezone). */
export function formatDateTime(value: string | null): string {
  if (!value) return PLACEHOLDER
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })
}
