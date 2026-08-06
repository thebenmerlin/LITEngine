import { createContext, useCallback, useState } from 'react'
import { extractFacts, searchPrecedents, runSimulation, ApiError } from '../lib/api'
import { DEFAULT_TWEAKS } from '../utils/whatIfCalculator'

const WhatIfContext = createContext(null)

/**
 * Owns What-If Analyzer page state at the app level so a loaded base case,
 * tweaks, and any in-flight load survive switching features and back.
 */
export function WhatIfProvider({ children }) {
  const [caseText, setCaseText] = useState('')
  const [baseResult, setBaseResult] = useState(null)
  const [baseWeakNodes, setBaseWeakNodes] = useState([])
  const [loading, setLoading] = useState(false)
  const [progressStep, setProgressStep] = useState(0)
  const [loadError, setLoadError] = useState(null)
  const [tweaks, setTweaks] = useState({ ...DEFAULT_TWEAKS })

  const setTweak = useCallback((key, value) => {
    setTweaks((prev) => ({ ...prev, [key]: value }))
  }, [])

  const toggleWeakArg = useCallback((id) => {
    setTweaks((prev) => ({
      ...prev,
      resolvedWeakArgs: prev.resolvedWeakArgs.includes(id)
        ? prev.resolvedWeakArgs.filter((x) => x !== id)
        : [...prev.resolvedWeakArgs, id],
    }))
  }, [])

  const resetTweaks = useCallback(() => setTweaks({ ...DEFAULT_TWEAKS }), [])

  const handleLoad = useCallback(async () => {
    if (!caseText.trim()) return
    setLoading(true)
    setLoadError(null)
    setBaseResult(null)
    setBaseWeakNodes([])
    setTweaks({ ...DEFAULT_TWEAKS })
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
        const sr = await searchPrecedents({ query, topK: 5, useKanoon: true })
        precedents = sr.results || []
      } catch {
        precedents = []
      }

      setProgressStep(2)
      const simRes = await runSimulation({
        caseProfile: profile,
        precedents: precedents.slice(0, 5),
        graphStats: null,
      })

      setBaseResult(simRes.result)
      setBaseWeakNodes(simRes.result?.weak_nodes || [])
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.detail || err.message : err.message)
    } finally {
      setLoading(false)
    }
  }, [caseText])

  const value = {
    caseText,
    setCaseText,
    baseResult,
    baseWeakNodes,
    loading,
    progressStep,
    loadError,
    setLoadError,
    tweaks,
    setTweak,
    toggleWeakArg,
    resetTweaks,
    handleLoad,
  }

  return (
    <WhatIfContext.Provider value={value}>{children}</WhatIfContext.Provider>
  )
}

export default WhatIfContext
