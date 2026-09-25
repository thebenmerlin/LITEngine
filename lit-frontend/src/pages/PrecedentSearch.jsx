import { useEffect, useState } from 'react'
import { ArrowRight, ArrowUpRight, Search } from 'lucide-react'
import { EmptyPanel, ErrorNotice, PageHeading, percent } from '../components/workspace/Primitives'
import { useWorkspace } from '../workspace/WorkspaceContext'
import { useSettings } from '../hooks/useSettings.jsx'

export default function PrecedentSearch() {
  const { settings } = useSettings()
  const { query, setQuery, search, precedents, status, errors, profile, busy } = useWorkspace()
  const [topK, setTopK] = useState(settings.defaultResultCount)
  const [useKanoon, setUseKanoon] = useState(settings.includeKanoon)
  const [selectedId, setSelectedId] = useState(null)
  const selected = precedents?.find((item) => item.doc_id === selectedId) || precedents?.[0]

  useEffect(() => { setSelectedId(null) }, [precedents])

  const submit = (event) => {
    event.preventDefault()
    search({ searchQuery: query, topK, useKanoon })
  }

  return <div className="page-stack">
    <PageHeading eyebrow="02 / RESEARCH" title="Precedents" description="Find judgments related to the legal issues in this matter, then inspect the source material." />
    <form className="search-form panel" onSubmit={submit}>
      <label htmlFor="precedent-query" className="eyebrow">SEARCH THE CASE LAW</label>
      <div className="search-input-row"><Search size={21} /><textarea id="precedent-query" value={query} onChange={(event) => setQuery(event.target.value)} rows={2} placeholder="Describe the legal issue or paste a case question…" /></div>
      <div className="search-form-footer">
        <div className="search-options"><label>Results <select value={profile ? 5 : topK} disabled={Boolean(profile)} onChange={(event) => setTopK(Number(event.target.value))}><option value={3}>3</option><option value={5}>5</option><option value={10}>10</option></select></label><label className="checkbox-line"><input type="checkbox" checked={useKanoon && !profile} disabled={Boolean(profile)} onChange={(event) => setUseKanoon(event.target.checked)} /> Include live Kanoon results</label></div>
        <button className="button button-primary" disabled={!query.trim() || busy}>{status.precedents === 'running' ? 'Searching…' : 'Search precedents'} <ArrowRight size={16} /></button>
      </div>
    </form>
    {profile && <p className="context-note">Case analysis uses five matches from the dated precedent index. A new search updates the case’s precedent set; refresh the map and outcome afterward.</p>}
    <ErrorNotice message={errors.precedents} title="Precedent search failed" />
    {status.precedents === 'running' && <div className="loading-line"><span className="spin-dot" /> Searching the index and live source…</div>}
    {precedents && status.precedents !== 'running' && <>
      <div className="results-header"><span className="eyebrow">SEARCH RESULTS</span><strong>{precedents.length} judgments</strong></div>
      {precedents.length ? <div className="precedent-layout">
        <div className="precedent-list">{precedents.map((result, index) => <button key={result.doc_id || index} className={`precedent-row ${selected?.doc_id === result.doc_id ? 'selected' : ''}`} onClick={() => setSelectedId(result.doc_id)}>
          <span className="result-index">{String(index + 1).padStart(2, '0')}</span>
          <span className="result-main"><strong>{result.title}</strong><small>{[result.court, result.date].filter(Boolean).join(' · ') || 'Court and date unavailable'}</small></span>
          <span className="result-score">{percent(result.similarity_score)}</span>
        </button>)}</div>
        {selected && <aside className="precedent-inspector panel"><span className="eyebrow">JUDGMENT / {selected.source?.toUpperCase() || 'SOURCE'}</span><h2>{selected.title}</h2><div className="inspector-meta"><span>{selected.court || 'Court unavailable'}</span><span>{selected.date || 'Date unavailable'}</span></div><p>{selected.snippet || 'No excerpt is available for this judgment.'}</p><div className="inspector-score"><span>Semantic match</span><strong>{percent(selected.similarity_score)}</strong><span className="score-track"><i style={{ width: `${Math.round((selected.similarity_score || 0) * 100)}%` }} /></span></div><a className="button button-outline" href={selected.url || `https://indiankanoon.org/doc/${selected.doc_id}/`} target="_blank" rel="noreferrer">Open judgment <ArrowUpRight size={16} /></a></aside>}
      </div> : <EmptyPanel icon={Search} title="No judgments found" body={profile ? 'Try a broader legal question or add more dated judgments to the local index.' : 'Try a broader legal question or enable live Kanoon results.'} />}
    </>}
    {!precedents && status.precedents !== 'running' && <EmptyPanel icon={Search} title="Find the closest authorities" body="Search a question from your case or enter another legal issue to inspect relevant judgments." />}
  </div>
}
