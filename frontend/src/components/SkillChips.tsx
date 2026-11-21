export interface SkillChip {
  label: string
  hint?: string // small extra text, e.g. "in skills list"
}

interface Props {
  title: string
  items: SkillChip[]
  tone: 'good' | 'bad'
  emptyText: string
}

export default function SkillChips({ title, items, tone, emptyText }: Props) {
  const chipStyle =
    tone === 'good'
      ? 'bg-emerald-50 text-emerald-800 ring-emerald-200'
      : 'bg-red-50 text-red-800 ring-red-200'
  const icon = tone === 'good' ? '✓' : '✗'

  return (
    <div>
      <h4 className="text-sm font-medium text-slate-700">{title}</h4>
      {items.length === 0 ? (
        <p className="mt-1 text-sm text-slate-500">{emptyText}</p>
      ) : (
        <ul className="mt-2 flex flex-wrap gap-2">
          {items.map((item, index) => (
            <li
              // the index is part of the key because the same skill can appear in two lists
              key={`${item.label}-${index}`}
              className={`rounded-full px-3 py-1 text-sm ring-1 ring-inset ${chipStyle}`}
            >
              <span aria-hidden="true">{icon} </span>
              {item.label}
              {item.hint && <span className="ml-1 text-xs opacity-70">({item.hint})</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
