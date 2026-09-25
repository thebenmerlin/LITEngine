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
const DRAFT_KEY = 'lit-active-case-draft'
const APPELLANT_KEY = 'lit-active-case-appellant'
const FILING_DATE_KEY = 'lit-active-case-filing-date'
const INITIAL_STATUS = { facts: 'idle', precedents: 'idle', graph: 'idle', simulation: 'idle' }

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
  const [caseText, setCaseText] = useState(() => {
    try { return sessionStorage.getItem(DRAFT_KEY) || '' } catch { return '' }
  })
  const [appellantType, setAppellantTypeState] = useState(() => {
    try { return sessionStorage.getItem(APPELLANT_KEY) || '' } catch { return '' }
  })
  const [filingDate, setFilingDateState] = useState(() => {
    try { return sessionStorage.getItem(FILING_DATE_KEY) || '' } catch { return '' }
  })
  const [analyzedText, setAnalyzedText] = useState('')
  const [query, setQuery] = useState('')
  const [profile, setProfile] = useState(null)
  const [precedents, setPrecedents] = useState(null)
  const [graph, setGraph] = useState(null)
  const [simulation, setSimulation] = useState(null)
  const [status, setStatus] = useState(INITIAL_STATUS)
  const [errors, setErrors] = useState({})
  const [health, setHealth] = useState('checking')
  const runId = useRef(0)
  const busy = Object.values(status).some((value) => value === 'running')

  useEffect(() => {
    try { sessionStorage.setItem(DRAFT_KEY, caseText) } catch { /* storage may be disabled */ }
  }, [caseText])

  useEffect(() => {
    try { sessionStorage.setItem(APPELLANT_KEY, appellantType) } catch { /* storage may be disabled */ }
  }, [appellantType])

  useEffect(() => {
    try { sessionStorage.setItem(FILING_DATE_KEY, filingDate) } catch { /* storage may be disabled */ }
  }, [filingDate])

  const setAppellantType = useCallback((value) => {
    setAppellantTypeState(value)
    setSimulation(null)
    setStatus((current) => ({ ...current, simulation: 'idle' }))
  }, [])

  const setFilingDate = useCallback((value) => {
    setFilingDateState(value)
    setProfile(null)
    setAnalyzedText('')
    setPrecedents(null)
    setGraph(null)
    setSimulation(null)
    setStatus(INITIAL_STATUS)
  }, [])

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
    setStatus(INITIAL_STATUS)
    setErrors({})
    try { sessionStorage.removeItem(DRAFT_KEY) } catch { /* storage may be disabled */ }
    try { sessionStorage.removeItem(APPELLANT_KEY) } catch { /* storage may be disabled */ }
    try { sessionStorage.removeItem(FILING_DATE_KEY) } catch { /* storage may be disabled */ }
  }, [])

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
      graph, simulation, status, errors, health, busy, stale, clearCase,
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
