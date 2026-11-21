export const EXAMPLE_QUESTIONS = [
  'Which of my applications is furthest along?',
  'Which of my stories shows leadership?',
  'What happened with my most recent application?',
] as const

/** {"status":"applied","limit":3} -> 'status: "applied", limit: 3' */
export function formatArguments(args: Record<string, unknown>): string {
  const entries = Object.entries(args)
  if (entries.length === 0) return 'no arguments'
  return entries.map(([name, value]) => `${name}: ${JSON.stringify(value)}`).join(', ')
}

/** Tool results are JSON text; show them indented. Anything else (like "Error: ...") is shown as is. */
export function prettyObservation(observation: string, limit = 2000): string {
  let text = observation
  try {
    text = JSON.stringify(JSON.parse(observation), null, 2)
  } catch {
    // not JSON (an error message, or a result the backend had to cut short): keep the original text
  }
  return text.length > limit ? `${text.slice(0, limit)}\n… (${text.length - limit} more characters)` : text
}

export function stepCountText(count: number): string {
  if (count === 0) return 'The agent answered without using any tools.'
  return count === 1 ? 'The agent used 1 tool call.' : `The agent used ${count} tool calls.`
}
