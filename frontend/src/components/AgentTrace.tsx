import type { AgentStep } from '../api/types'
import { formatArguments, prettyObservation, stepCountText } from '../lib/agent'

/** Every tool call the agent made: what it asked for, and exactly what came back. */
export default function AgentTrace({ steps }: { steps: AgentStep[] }) {
  return (
    <section aria-label="Agent steps" className="space-y-3">
      <h3 className="text-sm font-medium text-slate-700">{stepCountText(steps.length)}</h3>
      <ol className="space-y-3">
        {steps.map((step) => (
          <li
            key={step.number}
            className={`rounded-md border p-3 text-sm ${step.ok ? 'border-slate-200 bg-white' : 'border-red-200 bg-red-50'}`}
          >
            <p className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-slate-700">{`Step ${step.number}`}</span>
              <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-800">{step.tool}</code>
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium ${step.ok ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}`}
              >
                {step.ok ? 'ok' : 'error'}
              </span>
            </p>
            {step.thought && <p className="mt-1 italic text-slate-600">{`“${step.thought}”`}</p>}
            <p className="mt-1 text-xs text-slate-500">{`with ${formatArguments(step.arguments)}`}</p>
            <details className="mt-2">
              <summary className="cursor-pointer text-xs font-medium text-slate-600">What the tool returned</summary>
              <pre className="mt-1 max-h-72 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs text-slate-700">
                {prettyObservation(step.observation)}
              </pre>
            </details>
          </li>
        ))}
      </ol>
    </section>
  )
}
