import { createContext, useCallback, useEffect, useRef, useState } from 'react'
import { useApi } from '../hooks/useApi'
import { extractFacts } from '../lib/api'

const FactExtractionContext = createContext(null)

/**
 * Owns Fact Extraction page state at the app level so an in-flight or
 * completed extraction survives switching to another feature and back.
 */
export function FactExtractionProvider({ children }) {
  const [caseText, setCaseText] = useState('')
  const [useModel, setUseModel] = useState(true)
  const [elapsed, setElapsed] = useState(0)

  const { data: profile, loading, error, execute } = useApi(extractFacts)

  // Elapsed-seconds timer lives here (provider never unmounts) so it keeps
  // counting correctly even while the user is looking at another page.
  const timerRef = useRef(null)
  useEffect(() => {
    if (loading) {
      setElapsed(0)
      timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000)
    } else {
      clearInterval(timerRef.current)
    }
    return () => clearInterval(timerRef.current)
  }, [loading])

  const handleExtract = useCallback(() => {
    if (!caseText.trim()) return
    execute({ caseText: caseText.trim(), useModel })
  }, [caseText, useModel, execute])

  const value = {
    caseText,
    setCaseText,
    useModel,
    setUseModel,
    profile,
    loading,
    error,
    elapsed,
    handleExtract,
  }

  return (
    <FactExtractionContext.Provider value={value}>
      {children}
    </FactExtractionContext.Provider>
  )
}

export default FactExtractionContext
