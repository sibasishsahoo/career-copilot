// Shared Tailwind class strings, so every button and input looks the same.
// (Tailwind finds these because they are complete strings in the source code.)

export const inputClass =
  'mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500'

export const labelClass = 'block text-sm font-medium text-slate-700'

const buttonBase =
  'inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-semibold shadow-sm disabled:cursor-not-allowed disabled:opacity-50'

export const primaryButton = `${buttonBase} bg-blue-600 text-white hover:bg-blue-700`
export const secondaryButton = `${buttonBase} border border-slate-300 bg-white text-slate-700 hover:bg-slate-50`
export const dangerButton = `${buttonBase} bg-red-600 text-white hover:bg-red-700`

export const cardClass = 'rounded-lg border border-slate-200 bg-white p-5 shadow-sm'
