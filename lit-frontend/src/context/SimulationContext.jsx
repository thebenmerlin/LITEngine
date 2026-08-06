import { createContext, useCallback, useState } from 'react'
import { extractFacts, searchPrecedents, runSimulation, ApiError } from '../lib/api'

const SimulationContext = createContext(null)

/**
 * Owns Judicial Simulation page state at the app level so an in-flight run
 * or completed result survives switching to another feature and back.
 */
export function SimulationProvider({ children }) {
  const [caseText, setCaseText] = useState('')
  const [simResult, setSimResult] = useState(null)
  const [error, setError] = useState(null)
  const [running, setRunning] = useState(false)
  const [progressStep, setProgressStep] = useState(0)

  const handleRun = useCallback(async () => {
    if (!caseText.trim()) return
    setRunning(true)
    setError(null)
    setSimResult(null)
    setProgressStep(0)

    try {
      setProgressStep(0)
      const profile = await extractFacts({ caseText: caseText.trim(), useModel: true })

      setProgressStep(1)
      const query = profile.legal_issues
        ? profile.legal_issues.join(' ')
        : caseText.trim()
      let precedents = []
      try {
        const searchRes = await searchPrecedents({ query, topK: 5, useKanoon: true })
        precedents = searchRes.results || []
      } catch {
        precedents = []
      }

      setProgressStep(2)
      const simRes = await runSimulation({
        caseProfile: profile,
        precedents: precedents.slice(0, 5),
        graphStats: null,
      })

      setSimResult(simRes.result)
    } catch (err) {
      setError(
        err instanceof ApiError ? err.detail || err.message : err.message,
      )
    } finally {
      setRunning(false)
    }
  }, [caseText])

  const value = {
    caseText,
    setCaseText,
    simResult,
    error,
    running,
    progressStep,
    handleRun,
  }

  return (
    <SimulationContext.Provider value={value}>
      {children}
    </SimulationContext.Provider>
  )
}

export default SimulationContext
