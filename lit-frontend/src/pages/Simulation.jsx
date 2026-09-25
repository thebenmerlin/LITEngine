import { Link } from 'react-router-dom'
import { ArrowRight, ChartNoAxesCombined, Download } from 'lucide-react'
import { AppellantTypeField, EmptyPanel, ErrorNotice, FilingDateField, InfoNotice, PageHeading, RebuildButton, SampleCaseMenu, SectionTitle, percent } from '../components/workspace/Primitives'
import { useWorkspace } from '../workspace/WorkspaceContext'

function exportResult(simulation) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(simulation, null, 2)], { type: 'application/json' }))
  const link = document.createElement('a')
  link.href = url
  link.download = 'lit-outcome-analysis.json'
  link.click()
  URL.revokeObjectURL(url)
}

export default function Simulation() {
  const { profile, precedents, graph, simulation, status, errors, refreshSimulation, stale, busy, appellantType, filingDate } = useWorkspace()
  const result = simulation?.result
  const comparison = simulation?.old_vs_new
  const model = comparison?.new_model
  const modelSuccess = model?.probabilities?.succeeds

  return <div className="page-stack">
    <PageHeading eyebrow="04 / ASSESSMENT" title="Outcome analysis" description="An inspectable estimate based on the case profile, retrieved precedents and argument structure."
      action={result && <button className="button button-outline" onClick={() => exportResult(simulation)}><Download size={15} /> Export data</button>} />
    {stale && <InfoNotice>The case text changed. Reanalyze before relying on these results.</InfoNotice>}
    <ErrorNotice message={errors.simulation} title="Outcome analysis failed" />
    <SampleCaseMenu />
    {profile && <><AppellantTypeField disabled={busy} /><FilingDateField disabled={busy} /></>}
    {!result && status.simulation !== 'running' && <EmptyPanel icon={ChartNoAxesCombined} title="A factor-by-factor assessment" body={profile ? 'The case profile is ready. Run the assessment to inspect the estimate and its contributing factors.' : 'Analyze a case to generate an outcome assessment.'} action={profile && <RebuildButton onClick={refreshSimulation} disabled={stale || busy || !appellantType || !filingDate}>Run assessment</RebuildButton>} />}
    {status.simulation === 'running' && <div className="loading-line"><span className="spin-dot" /> Weighing case factors and precedents…</div>}
    {result && <>
      <div className="outcome-hero">
        <div className="outcome-score"><span className="eyebrow">ESTIMATED CHANCE OF ANY APPELLATE RELIEF</span><strong>{percent(result.win_probability)}</strong><span className="outcome-risk">{result.risk_assessment?.level || 'Assessment'}</span></div>
        <div className="outcome-explanation"><span className="eyebrow">READING THE RESULT</span><h2>{result.recommendation || 'Review the evidence and precedent picture before drawing conclusions.'}</h2><p>Primary method: {comparison?.primary === 'new_model' ? 'trained outcome model' : 'rule-based heuristic'}. This is a research estimate drawn from the supplied case material.</p><div className="outcome-track"><span style={{ left: `${Math.round(result.win_probability * 100)}%` }} /><i style={{ width: `${Math.round(result.win_probability * 100)}%` }} /></div><div className="track-labels"><span>UNFAVORABLE</span><span>UNCERTAIN</span><span>FAVORABLE</span></div></div>
      </div>

      <div className="outcome-grid">
        <section className="panel outcome-factors"><SectionTitle number="01" title="Factor breakdown" aside="WHAT SHAPED THIS ESTIMATE" />
          {result.score_breakdown?.length ? result.score_breakdown.map((factor) => <div className="factor-row" key={factor.component}><div><strong>{factor.component}</strong><span>{percent(factor.raw_score)} raw · {percent(factor.weight)} weight</span></div><div className="factor-meter"><i style={{ width: `${Math.round(factor.raw_score * 100)}%` }} /></div><p>{factor.explanation}</p></div>) : <p className="muted">No factor breakdown was provided.</p>}
        </section>
        <aside className="outcome-side">
          <div className="panel inset-panel"><span className="eyebrow">MODEL COMPARISON</span>{comparison && model?.model_loaded ? <><div className="compare-row"><span>Trained model</span><strong>{percent(modelSuccess)}</strong></div><div className="compare-row"><span>Rule-based heuristic</span><strong>{percent(comparison.old_heuristic?.win_probability)}</strong></div><p>Two methods, shown separately. The primary method above is marked in the result description.</p></> : <p>Only the available assessment method was returned.</p>}</div>
          <div className="panel inset-panel"><span className="eyebrow">INPUT COVERAGE</span><div className="coverage-row"><span>Case profile</span><strong>Included</strong></div><div className="coverage-row"><span>Precedents</span><strong>{precedents?.length || 0} used</strong></div><div className="coverage-row"><span>Argument map</span><strong>{graph ? `${graph.node_count} nodes` : 'Not available'}</strong></div></div>
          <Link to="/what-if" className="next-link">Explore scenarios <ArrowRight size={17} /></Link>
        </aside>
      </div>

      <div className="strength-grid"><section className="panel"><span className="eyebrow">FACTORS IN FAVOR</span><ul className="signal-list positive">{result.key_strengths?.length ? result.key_strengths.map((item, index) => <li key={index}>{item}</li>) : <li>No strengths were returned.</li>}</ul></section><section className="panel"><span className="eyebrow">POINTS TO EXAMINE</span><ul className="signal-list caution">{result.key_weaknesses?.length ? result.key_weaknesses.map((item, index) => <li key={index}>{item}</li>) : <li>No weaknesses were returned.</li>}</ul></section></div>
    </>}
  </div>
}
