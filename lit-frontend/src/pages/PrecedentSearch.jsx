import { useState } from 'react'
import { Search as SearchIcon } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import { searchPrecedents, getIndexStats } from '../lib/api'
import Button from '../components/ui/Button'
import EmptyState from '../components/ui/EmptyState'
import ErrorBanner from '../components/ui/ErrorBanner'
import Spinner from '../components/ui/Spinner'
import PrecedentCard from '../components/PrecedentCard'

/* ------------------------------------------------------------------ */
/*  Skeleton card — animated pulse placeholder                        */
/* ------------------------------------------------------------------ */

function SkeletonCard() {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-surface-dark">
      {/* Title skeleton */}
      <div className="h-5 w-3/4 animate-pulse rounded-md bg-gray-200 dark:bg-gray-700" />
      {/* Meta skeleton */}
      <div className="mt-2 h-4 w-1/2 animate-pulse rounded-md bg-gray-100 dark:bg-gray-800" />
      {/* Snippet skeleton — 2 lines */}
      <div className="mt-4 h-4 animate-pulse rounded-md bg-gray-100 dark:bg-gray-800" />
      <div className="mt-2 h-4 w-5/6 animate-pulse rounded-md bg-gray-100 dark:bg-gray-800" />
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  PrecedentSearch page                                              */
/* ------------------------------------------------------------------ */

const TOP_K_OPTIONS = [3, 5, 10]

export default function PrecedentSearch() {
  // Form state
  const [query, setQuery] = useState('')
  const [topK, setTopK] = useState(5)
  const [useKanoon, setUseKanoon] = useState(true)

  // Index stats (fetched once on mount)
  const { data: statsData } = useApi(getIndexStats, { immediate: true })

  // Search
  const {
    data: results,
    loading: searching,
    error: searchError,
    execute: handleSearch,
  } = useApi(searchPrecedents)

  const onSubmit = (e) => {
    e.preventDefault()
    if (!query.trim()) return
    handleSearch({ query: query.trim(), topK, useKanoon })
  }

  const hasSearched = results !== null || searchError !== null

  return (
    <div>
      {/* ---- Header ---- */}
      <div className="mb-8 flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-100">
            Precedent Search
          </h2>
          <p className="mt-1.5 text-sm text-gray-500 dark:text-gray-400">
            Find semantically similar Indian court judgments
          </p>
        </div>

        {/* Index stats — top right */}
        <div className="shrink-0 text-right text-xs text-gray-400 dark:text-gray-500">
          {statsData && statsData.total_documents > 0 ? (
            <span>
              Index:{' '}
              <span className="font-medium text-gray-600 dark:text-gray-300">
                {statsData.total_documents} documents
              </span>
            </span>
          ) : (
            <span>
              Index empty — results from live Kanoon only
            </span>
          )}
        </div>
      </div>

      {/* ---- Search Form ---- */}
      <form onSubmit={onSubmit}>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          rows={5}
          placeholder="Describe the facts of your case. The system will find similar judgments from the Supreme Court and High Courts."
          className="block w-full resize-y rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm leading-relaxed text-gray-900 placeholder:text-gray-400 focus:border-navy-700 focus:outline-none focus:ring-1 focus:ring-navy-700 dark:border-gray-700 dark:bg-surface-dark dark:text-gray-100 dark:placeholder:text-gray-500 dark:focus:border-navy-500 dark:focus:ring-navy-500"
          style={{ minHeight: 140 }}
        />

        {/* Controls row */}
        <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-3">
          {/* Top K selector */}
          <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
            Top results
            <select
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm focus:border-navy-700 focus:outline-none focus:ring-1 focus:ring-navy-700 dark:border-gray-700 dark:bg-surface-dark dark:text-gray-100"
            >
              {TOP_K_OPTIONS.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>

          {/* Kanoon toggle */}
          <label className="flex cursor-pointer items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
            <input
              type="checkbox"
              checked={useKanoon}
              onChange={(e) => setUseKanoon(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-navy-700 focus:ring-navy-700 dark:border-gray-600 dark:bg-surface-dark"
            />
            Include live Kanoon results
          </label>

          {/* Search button — pushed right */}
          <div className="ml-auto">
            <Button
              type="submit"
              variant="primary"
              size="md"
              disabled={searching || !query.trim()}
              className="gap-2"
            >
              {searching ? (
                <>
                  <Spinner size="sm" />
                  Searching…
                </>
              ) : (
                <>
                  <SearchIcon className="h-4 w-4" />
                  Search
                </>
              )}
            </Button>
          </div>
        </div>
      </form>

      {/* ---- Results ---- */}
      <div className="mt-8">
        {/* Loading skeletons */}
        {searching && (
          <div className="space-y-4">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        )}

        {/* Error */}
        {searchError && (
          <ErrorBanner message={searchError.detail || searchError.message} />
        )}

        {/* Empty — user searched but got zero results */}
        {!searching && hasSearched && !searchError && (!results || results.total === 0) && (
          <EmptyState
            title="No precedents found"
            message="Try rephrasing your case description or include live Kanoon results for broader coverage."
            icon={SearchIcon}
          />
        )}

        {/* Results list */}
        {!searching && results && results.total > 0 && (
          <div>
            <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
              {results.total} result{results.total !== 1 ? 's' : ''} for &ldquo;
              <span className="font-medium text-gray-700 dark:text-gray-300">
                {results.query}
              </span>
              &rdquo;
            </p>
            <div className="space-y-4">
              {results.results.map((r) => (
                <PrecedentCard key={r.doc_id || r.url} result={r} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
