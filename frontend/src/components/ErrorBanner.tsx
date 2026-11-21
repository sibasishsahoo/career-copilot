interface Props {
  message: string
  onDismiss?: () => void
  onRetry?: () => void
}

/** role="alert" makes screen readers announce the message as soon as it appears. */
export default function ErrorBanner({ message, onDismiss, onRetry }: Props) {
  return (
    <div
      role="alert"
      className="flex items-start justify-between gap-3 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
    >
      <p>{message}</p>
      <div className="flex shrink-0 gap-3">
        {onRetry && (
          <button type="button" onClick={onRetry} className="font-medium underline">
            Retry
          </button>
        )}
        {onDismiss && (
          <button type="button" onClick={onDismiss} aria-label="Dismiss error" className="font-medium">
            ✕
          </button>
        )}
      </div>
    </div>
  )
}
