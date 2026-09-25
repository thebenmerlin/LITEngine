import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import {
  ApiError,
  buildGraph,
  checkHealth,
  checkTaskStatus,
  extractFacts,
  runSimulation,
  searchPrecedents,
} from '../lib/api'
import { useSettings } from '../hooks/useSettings.jsx'

const WorkspaceContext = createContext(null)
const INITIAL_STATUS = { facts: 'idle', precedents: 'idle', graph: 'idle', simulation: 'idle' }

// Everything about "the current case" lives in localStorage (not
// sessionStorage) so it survives a closed tab or a restarted browser, not
// just a reload — the whole point being a demo can be picked back up
// exactly where it left off. Every persisted value goes through the same
// JSON helpers so the persistence layer is uniform and each add is a
// one-line change instead of a bespoke effect.
const STORE_KEYS = {
  caseText: 'lit-workspace.case-text',
  appellantType: 'lit-workspace.appellant-type',
  filingDate: 'lit-workspace.filing-date',
  analyzedText: 'lit-workspace.analyzed-text',
  query: 'lit-workspace.query',
  profile: 'lit-workspace.profile',
  precedents: 'lit-workspace.precedents',
  graph: 'lit-workspace.graph',
  simulation: 'lit-workspace.simulation',
  chatMessages: 'lit-workspace.chat-messages',
}

function readStored(key, fallback) {
  try {
    const raw = localStorage.getItem(key)
    return raw === null ? fallback : JSON.parse(raw)
  } catch {
    return fallback
  }
}

function writeStored(key, value) {
  try {
    if (value === null || value === undefined) localStorage.removeItem(key)
    else localStorage.setItem(key, JSON.stringify(value))
  } catch { /* storage may be disabled or full — persistence is a convenience, not a requirement */ }
}

function usePersistedState(key, fallback) {
  const [value, setValue] = useState(() => readStored(key, fallback))
  useEffect(() => { writeStored(key, value) }, [key, value])
  return [value, setValue]
}

function messageFor(error) {
  if (error instanceof ApiError) return error.detail || error.message
  return error?.message || 'Something went wrong. Please try again.'
}

async function resolveExtraction(caseText, useModel) {
  let result = await extractFacts({ caseText, useModel })
  if (!result?.task_id) return result

  for (let attempt = 0; attempt < 90; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 2000))
    result = await checkTaskStatus(result.task_id)
    if (result.status === 'completed' && result.result) return result.result
    if (result.status === 'failed') throw new Error(result.error || 'Fact extraction failed')
  }
  throw new Error('Fact extraction is still processing. Please try again shortly.')
}

export function WorkspaceProvider({ children }) {
  const { settings } = useSettings()
  const [caseText, setCaseText] = usePersistedState(STORE_KEYS.caseText, '')
  const [appellantType, setAppellantTypeState] = usePersistedState(STORE_KEYS.appellantType, '')
  const [filingDate, setFilingDateState] = usePersistedState(STORE_KEYS.filingDate, '')
  const [analyzedText, setAnalyzedText] = usePersistedState(STORE_KEYS.analyzedText, '')
  const [query, setQuery] = usePersistedState(STORE_KEYS.query, '')
  const [profile, setProfile] = usePersistedState(STORE_KEYS.profile, null)
  const [precedents, setPrecedents] = usePersistedState(STORE_KEYS.precedents, null)
  const [graph, setGraph] = usePersistedState(STORE_KEYS.graph, null)
  const [simulation, setSimulation] = usePersistedState(STORE_KEYS.simulation, null)
  const [chatMessages, setChatMessages] = usePersistedState(STORE_KEYS.chatMessages, [])
  // Restored results should read as "done", not "idle" — WorkflowStrip
  // already keys off presence of the data itself, but this keeps the
  // running-spinner/empty-panel logic on every page consistent on a
  // freshly reloaded workspace too, not just a freshly computed one.
  const [status, setStatus] = useState(() => ({
    facts: readStored(STORE_KEYS.profile, null) ? 'done' : 'idle',
    precedents: readStored(STORE_KEYS.precedents, null) ? 'done' : 'idle',
    graph: readStored(STORE_KEYS.graph, null) ? 'done' : 'idle',
    simulation: readStored(STORE_KEYS.simulation, null) ? 'done' : 'idle',
  }))
  const [errors, setErrors] = useState({})
  const [health, setHealth] = useState('checking')
  const runId = useRef(0)
  const busy = Object.values(status).some((value) => value === 'running')

  const setAppellantType = useCallback((value) => {
    setAppellantTypeState(value)
    setSimulation(null)
    setStatus((current) => ({ ...current, simulation: 'idle' }))
  }, [setAppellantTypeState, setSimulation])

  const setFilingDate = useCallback((value) => {
    setFilingDateState(value)
    setProfile(null)
    setAnalyzedText('')
    setPrecedents(null)
    setGraph(null)
    setSimulation(null)
    setStatus(INITIAL_STATUS)
  }, [setFilingDateState, setProfile, setAnalyzedText, setPrecedents, setGraph, setSimulation])

  useEffect(() => {
    let active = true
    const refreshHealth = () => checkHealth().then(() => {
      if (active) setHealth('online')
    }).catch(() => {
      if (active) setHealth('offline')
    })
    refreshHealth()
    const interval = setInterval(refreshHealth, 30000)
    return () => { active = false; clearInterval(interval) }
  }, [])

  const setStep = useCallback((step, value) => {
    setStatus((current) => ({ ...current, [step]: value }))
  }, [])
  const setStepError = useCallback((step, error) => {
    setErrors((current) => ({ ...current, [step]: messageFor(error) }))
  }, [])

  const clearCase = useCallback(() => {
    runId.current += 1
    setCaseText('')
    setAppellantTypeState('')
    setFilingDateState('')
    setAnalyzedText('')
    setQuery('')
    setProfile(null)
    setPrecedents(null)
    setGraph(null)
    setSimulation(null)
    setChatMessages([])
    setStatus(INITIAL_STATUS)
    setErrors({})
  }, [setCaseText, setAppellantTypeState, setFilingDateState, setAnalyzedText, setQuery, setProfile, setPrecedents, setGraph, setSimulation, setChatMessages])

  const runAnalysis = useCallback(async () => {
    const text = caseText.trim()
    if (!text || !appellantType || !filingDate) return
    const id = ++runId.current
    const current = () => runId.current === id
    setErrors({})
    setStatus({ facts: 'running', precedents: 'idle', graph: 'idle', simulation: 'idle' })
    setProfile(null)
    setPrecedents(null)
    setGraph(null)
    setSimulation(null)

    let extracted
    try {
      extracted = await resolveExtraction(text, settings.useAiModel)
      if (!current()) return
      setHealth('online')
      setProfile(extracted)
      setAnalyzedText(text)
      setStep('facts', 'done')
    } catch (error) {
      if (!current()) return
      setStep('facts', 'error')
      setStepError('facts', error)
      return
    }

    const searchQuery = extracted.legal_issues?.filter(Boolean).join(' ') || text
    setQuery(searchQuery)
    setStep('precedents', 'running')
    let matches = []
    try {
      const result = await searchPrecedents({ query: searchQuery, topK: 5, useKanoon: false, beforeDate: filingDate })
      if (!current()) return
      matches = result.results || []
      setHealth('online')
      setPrecedents(matches)
      setStep('precedents', 'done')
    } catch (error) {
      if (!current()) return
      setPrecedents([])
      setStep('precedents', 'error')
      setStepError('precedents', error)
    }

    setStep('graph', 'running')
    let builtGraph = null
    try {
      builtGraph = await buildGraph({ caseProfile: extracted, precedents: matches.slice(0, 3) })
      if (!current()) return
      setGraph(builtGraph)
      setHealth('online')
      setStep('graph', 'done')
    } catch (error) {
      if (!current()) return
      setStep('graph', 'error')
      setStepError('graph', error)
    }

    setStep('simulation', 'running')
    try {
      const response = await runSimulation({
        caseProfile: extracted,
        precedents: matches.slice(0, 5),
        graphStats: builtGraph ? { node_count: builtGraph.node_count, weak_nodes: builtGraph.weak_nodes } : null,
        appellantType,
        filingDate,
      })
      if (!current()) return
      setSimulation(response)
      setHealth('online')
      setStep('simulation', 'done')
    } catch (error) {
      if (!current()) return
      setStep('simulation', 'error')
      setStepError('simulation', error)
    }
  }, [caseText, appellantType, filingDate, settings, setStep, setStepError])

  const search = useCallback(async ({ searchQuery = query, topK = 5, useKanoon = true } = {}) => {
    if (!searchQuery.trim() || busy) return
    const id = ++runId.current
    setQuery(searchQuery)
    setStep('precedents', 'running')
    setErrors((current) => ({ ...current, precedents: null }))
    try {
      const response = await searchPrecedents({ query: searchQuery.trim(), topK: profile ? 5 : topK, useKanoon: profile ? false : useKanoon, beforeDate: filingDate || null })
      if (runId.current !== id) return
      setHealth('online')
      setPrecedents(response.results || [])
      setGraph(null)
      setSimulation(null)
      setStep('graph', 'idle')
      setStep('simulation', 'idle')
      setStep('precedents', 'done')
    } catch (error) {
      if (runId.current !== id) return
      setStep('precedents', 'error')
      setStepError('precedents', error)
    }
  }, [query, filingDate, profile, busy, setStep, setStepError])

  const refreshGraph = useCallback(async () => {
    if (!profile || busy) return
    const id = ++runId.current
    setStep('graph', 'running')
    setErrors((current) => ({ ...current, graph: null }))
    try {
      const result = await buildGraph({ caseProfile: profile, precedents: (precedents || []).slice(0, 3) })
      if (runId.current !== id) return
      setHealth('online')
      setGraph(result)
      setSimulation(null)
      setStep('simulation', 'idle')
      setStep('graph', 'done')
    } catch (error) {
      if (runId.current !== id) return
      setStep('graph', 'error')
      setStepError('graph', error)
    }
  }, [profile, precedents, busy, setStep, setStepError])

  const refreshSimulation = useCallback(async () => {
    if (!profile || !appellantType || !filingDate || busy) return
    const id = ++runId.current
    setStep('simulation', 'running')
    setErrors((current) => ({ ...current, simulation: null }))
    try {
      const result = await runSimulation({
        caseProfile: profile,
        precedents: (precedents || []).slice(0, 5),
        graphStats: graph ? { node_count: graph.node_count, weak_nodes: graph.weak_nodes } : null,
        appellantType,
        filingDate,
      })
      if (runId.current !== id) return
      setHealth('online')
      setSimulation(result)
      setStep('simulation', 'done')
    } catch (error) {
      if (runId.current !== id) return
      setStep('simulation', 'error')
      setStepError('simulation', error)
    }
  }, [profile, precedents, graph, appellantType, filingDate, busy, setStep, setStepError])

  const stale = Boolean(profile && caseText.trim() !== analyzedText)

  return (
    <WorkspaceContext.Provider value={{
      caseText, setCaseText, appellantType, setAppellantType, filingDate, setFilingDate, analyzedText, query, setQuery, profile, precedents,
      graph, simulation, chatMessages, setChatMessages, status, errors, health, busy, stale, clearCase,
      runAnalysis, search, refreshGraph, refreshSimulation,
    }}>
      {children}
    </WorkspaceContext.Provider>
  )
}

export function useWorkspace() {
  const context = useContext(WorkspaceContext)
  if (!context) throw new Error('useWorkspace must be used within WorkspaceProvider')
  return context
}
