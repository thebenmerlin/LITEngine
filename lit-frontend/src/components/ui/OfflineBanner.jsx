import { useEffect, useState, useCallback } from 'react'
import { WifiOff, X } from 'lucide-react'
import { checkHealth } from '../../lib/api'

const POLL_INTERVAL_MS = 30_000

export default function OfflineBanner() {
  const [offline, setOffline] = useState(false)
  const [dismissed, setDismissed] = useState(false)

  const probe = useCallback(async () => {
    try {
      await checkHealth()
      setOffline(false)
      if (dismissed) setDismissed(false)
    } catch {
      setOffline(true)
    }
  }, [dismissed])

  // Initial check on mount
  useEffect(() => {
    probe()
    const timer = setInterval(probe, POLL_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [probe])

  if (!offline || dismissed) return null

  return (
    <div className="relative z-50 flex items-center justify-between bg-red-50 px-4 py-2 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
      <div className="flex items-center gap-2">
        <WifiOff className="h-4 w-4 shrink-0" />
        <span className="text-xs">
          Backend unreachable — some features may not work. Check your connection.
        </span>
      </div>
      <button
        onClick={() => setDismissed(true)}
        className="shrink-0 rounded p-0.5 text-red-400 hover:text-red-600 dark:hover:text-red-300"
        aria-label="Dismiss"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}