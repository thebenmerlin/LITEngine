import { AlertTriangle } from 'lucide-react'

export default function ErrorBanner({ message, className = '', onDismiss }) {
  return (
    <div
      className={`flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 dark:border-red-900/50 dark:bg-red-900/10 ${className}`}
      role="alert"
    >
      <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-500" />
      <p className="text-sm text-red-700 dark:text-red-400">{message}</p>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="ml-auto text-red-400 hover:text-red-600"
          aria-label="Dismiss"
        >
          &times;
        </button>
      )}
    </div>
  )
}
