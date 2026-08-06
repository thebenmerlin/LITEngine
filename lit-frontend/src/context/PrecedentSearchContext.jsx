import { createContext, useCallback, useState } from 'react'
import { useApi } from '../hooks/useApi'
import { searchPrecedents, getIndexStats } from '../lib/api'

const PrecedentSearchContext = createContext(null)

/**
 * Owns Precedent Search page state at the app level (mounted once, never
 * unmounted by route changes) so query/results survive switching features.
 */
export function PrecedentSearchProvider({ children }) {
  const [query, setQuery] = useState('')
  const [topK, setTopK] = useState(5)
  const [useKanoon, setUseKanoon] = useState(true)

  const { data: statsData } = useApi(getIndexStats, { immediate: true })
  const {
    data: results,
    loading: searching,
    error: searchError,
    execute,
  } = useApi(searchPrecedents)

  const handleSearch = useCallback(
    (e) => {
      e.preventDefault()
      if (!query.trim()) return
      execute({ query: query.trim(), topK, useKanoon })
    },
    [query, topK, useKanoon, execute],
  )

  const value = {
    query,
    setQuery,
    topK,
    setTopK,
    useKanoon,
    setUseKanoon,
    statsData,
    results,
    searching,
    searchError,
    handleSearch,
  }

  return (
    <PrecedentSearchContext.Provider value={value}>
      {children}
    </PrecedentSearchContext.Provider>
  )
}

export default PrecedentSearchContext
