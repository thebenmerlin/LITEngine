import { createContext, useCallback, useState } from 'react'
import { extractFacts, searchPrecedents, buildGraph, ApiError } from '../lib/api'

const ArgumentGraphContext = createContext(null)

/**
 * Owns Argument Graph page state at the app level so a built graph (or an
 * in-flight build) survives switching to another feature and back.
 */
export function ArgumentGraphProvider({ children }) {
  const [caseText, setCaseText] = useState('')
  const [graphData, setGraphData] = useState(null)
  const [selectedNode, setSelectedNode] = useState(null)
  const [building, setBuilding] = useState(false)
  const [buildError, setBuildError] = useState(null)

  const handleBuild = useCallback(async () => {
    if (!caseText.trim()) return
    setBuilding(true)
    setBuildError(null)
    setSelectedNode(null)
    setGraphData(null)

    try {
      // Step 1: extract facts
      const profile = await extractFacts({ caseText: caseText.trim(), useModel: true })

      // Step 2: pull real precedents so the graph includes PRECEDENT nodes
      // and "cites" edges — without this the graph is just claims/statutes.
      // Non-fatal: the graph still builds fine from facts alone if search fails.
      const query = profile.legal_issues?.length
        ? profile.legal_issues.join(' ')
        : caseText.trim()
      let precedents = []
      try {
        const searchRes = await searchPrecedents({ query, topK: 5, useKanoon: true })
        precedents = (searchRes.results || []).slice(0, 3)
      } catch {
        precedents = []
      }

      // Step 3: build graph
      const graph = await buildGraph({ caseProfile: profile, precedents })
      setGraphData(graph)
    } catch (err) {
      setBuildError(
        err instanceof ApiError ? err.detail || err.message : err.message,
      )
    } finally {
      setBuilding(false)
    }
  }, [caseText])

  const value = {
    caseText,
    setCaseText,
    graphData,
    selectedNode,
    setSelectedNode,
    building,
    buildError,
    setBuildError,
    handleBuild,
  }

  return (
    <ArgumentGraphContext.Provider value={value}>
      {children}
    </ArgumentGraphContext.Provider>
  )
}

export default ArgumentGraphContext
