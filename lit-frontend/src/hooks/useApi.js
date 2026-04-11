import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, checkTaskStatus } from '../lib/api'

const POLL_INTERVAL_MS = 2000
const TERMINAL_STATES = new Set(['completed', 'failed'])

/**
 * Generic data-fetching hook for any LIT API function.
 *
 * @template T
 * @param {(...args: any[]) => Promise<T>} apiFn  – The API function to call
 * @param {{ immediate?: boolean }} [opts]        – Call on mount if true
 *
 * @returns {{
 *   data: T | null,
 *   loading: boolean,
 *   error: ApiError | null,
 *   execute: (...args: any[]) => Promise<T | null>,
 * }}
 */
export function useApi(apiFn, { immediate = false } = {}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Keep a stable ref to apiFn across renders
  const apiFnRef = useRef(apiFn)
  apiFnRef.current = apiFn

  /**
   * Poll a 202-accepted task until it reaches a terminal state.
   */
  const pollTask = useCallback(async (taskId) => {
    return new Promise((resolve, reject) => {
      const interval = setInterval(async () => {
        try {
          const status = await checkTaskStatus(taskId)

          if (status.status === 'completed') {
            clearInterval(interval)
            resolve(status.result ?? null)
          } else if (status.status === 'failed') {
            clearInterval(interval)
            reject(
              new ApiError(
                status.error ?? 'Task failed',
                500,
                status.error,
              ),
            )
          }
          // 'pending' or 'processing' — keep polling
        } catch (err) {
          clearInterval(interval)
          reject(err)
        }
      }, POLL_INTERVAL_MS)
    })
  }, [])

  /**
   * Execute the API function with the given arguments.
   *
   * If the response contains a `task_id` (202 Accepted), the hook
   * automatically begins polling `checkTaskStatus` until completion.
   *
   * @param  {...any} args
   * @returns {Promise<T | null>}  The resolved data, or null on error
   */
  const execute = useCallback(async (...args) => {
    setLoading(true)
    setError(null)

    try {
      const result = await apiFnRef.current(...args)

      // ---- 202 Accepted with task_id → auto-poll ----
      if (result && typeof result === 'object' && 'task_id' in result) {
        const taskId = result.task_id
        const finalResult = await pollTask(taskId)
        setData(finalResult)
        setLoading(false)
        return finalResult
      }

      // ---- Normal 200 response ----
      setData(result)
      setLoading(false)
      return result
    } catch (err) {
      const apiErr =
        err instanceof ApiError
          ? err
          : new ApiError(err.message ?? 'Unknown error', 0, err.message)

      setError(apiErr)
      setLoading(false)
      return null
    }
  }, [pollTask])

  // Mount-time execution when `immediate: true`
  useEffect(() => {
    if (immediate) {
      execute()
    }
    // Only run on mount; we intentionally omit `execute` to avoid re-firing
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { data, loading, error, execute }
}
