import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, RotateCcw, SlidersHorizontal } from 'lucide-react'
import { DEFAULT_TWEAKS, recalculate } from '../utils/whatIfCalculator'
import { CaseComposer, EmptyPanel, PageHeading, percent } from '../components/workspace/Primitives'
import { useWorkspace } from '../workspace/WorkspaceContext'

function Range({ label, value, min = 0, max = 5, suffix = '', onChange }) {
  return <label className="scenario-control"><span><strong>{label}</strong><em>{value}{suffix}</em></span><input type="range" min={min} max={max} step={1} value={value} onChange={(event) => onChange(Number(event.target.value))} /></label>
}

function Choice({ label, value, options, onChange }) {
  return <div className="scenario-control"><span><strong>{label}</strong></span><div className="segmented">{options.map(([id, text]) => <button key={id} className={value === id ? 'active' : ''} onClick={() => onChange(id)} aria-pressed={value === id}>{text}</button>)}</div></div>
}

export default function WhatIf() {
  const { profile, graph, simulation } = useWorkspace()
  const [tweaks, setTweaks] = useState({ ...DEFAULT_TWEAKS })
  const [saved, setSaved] = useState([])
  const baseline = simulation?.result?.win_probability
  const result = useMemo(() => baseline == null ? null : recalculate(baseline, tweaks), [baseline, tweaks])
  const effectiveDelta = result ? result.adjusted - baseline : 0
  const weakNodes = graph?.nodes?.filter((node) => graph.weak_nodes?.includes(node.id)) || []
  const set = (key, value) => setTweaks((current) => ({ ...current, [key]: value }))
  const toggleWeak = (id) => setTweaks((current) => ({ ...current, resolvedWeakArgs: current.resolvedWeakArgs.includes(id) ? current.resolvedWeakArgs.filter((item) => item !== id) : [...current.resolvedWeakArgs, id] }))
  const save = () => setSaved((current) => [...current, { name: `Scenario ${String(current.length + 1).padStart(2, '0')}`, adjusted: result.adjusted, tweaks: { ...tweaks, resolvedWeakArgs: [...tweaks.resolvedWeakArgs] } }])

  return <div className="page-stack">
    <PageHeading eyebrow="05 / EXPLORATION" title="Scenarios" description="Change assumptions and see how a simple sensitivity estimate moves from the original outcome." />
    {!profile && <CaseComposer compact />}
    {baseline == null && <EmptyPanel icon={SlidersHorizontal} title="Start from an analyzed case" body="A base outcome is needed before you can explore different assumptions." action={profile && <Link to="/simulation" className="button button-primary">Run outcome analysis <ArrowRight size={16} /></Link>} />}
    {result && <>
      <div className="scenario-banner"><span className="eyebrow">HOW TO READ THIS VIEW</span><p>Scenario changes are calculated in your browser using a simple heuristic. They are sensitivity estimates, not fresh predictions from the backend.</p></div>
      <div className="scenario-layout">
        <div className="scenario-controls panel">
          <div className="scenario-controls-header"><div><span className="eyebrow">ADJUST ASSUMPTIONS</span><h2>Build a scenario</h2></div><button className="text-button" onClick={() => setTweaks({ ...DEFAULT_TWEAKS })}><RotateCcw size={15} /> Reset</button></div>
          <div className="control-section"><span className="eyebrow">01 / EVIDENCE</span><Range label="Additional evidence pieces" value={tweaks.additionalEvidence} onChange={(value) => set('additionalEvidence', value)} /><Choice label="Evidence quality" value={tweaks.evidenceQuality} onChange={(value) => set('evidenceQuality', value)} options={[["weak", "Weak"], ["moderate", "Moderate"], ["strong", "Strong"]]} /></div>
          <div className="control-section"><span className="eyebrow">02 / LAW & FORUM</span><Range label="Additional sections" value={tweaks.additionalIpcSections} max={4} onChange={(value) => set('additionalIpcSections', value)} /><label className="scenario-control"><span><strong>Jurisdiction</strong></span><select value={tweaks.jurisdiction} onChange={(event) => set('jurisdiction', event.target.value)}><option value="same">Same court</option><option value="high">High Court</option><option value="supreme">Supreme Court</option><option value="district">District Court</option></select></label></div>
          <div className="control-section"><span className="eyebrow">03 / ARGUMENT SUPPORT</span>{weakNodes.length ? weakNodes.map((node) => <label className="weak-checkbox" key={node.id}><input type="checkbox" checked={tweaks.resolvedWeakArgs.includes(node.id)} onChange={() => toggleWeak(node.id)} /><span>{node.label}</span></label>) : <p className="muted">No graph-flagged weak claims are available for this case.</p>}</div>
          <div className="control-section"><span className="eyebrow">04 / PRECEDENTS</span><Range label="Additional supporting precedents" value={tweaks.additionalPrecedents} onChange={(value) => set('additionalPrecedents', value)} /><Choice label="Precedent similarity" value={tweaks.precedentSimilarity} onChange={(value) => set('precedentSimilarity', value)} options={[["low", "Low"], ["medium", "Medium"], ["high", "High"]]} /></div>
        </div>
        <div className="scenario-results">
          <div className="scenario-result-card"><span className="eyebrow">ESTIMATED OUTCOME</span><div className="scenario-delta"><div><small>BASE CASE</small><strong>{percent(baseline)}</strong></div><ArrowRight size={22} /><div><small>THIS SCENARIO</small><strong>{percent(result.adjusted)}</strong></div></div><div className="scenario-track"><i style={{ left: `${Math.round(baseline * 100)}%` }} /><span style={{ left: `${Math.round(result.adjusted * 100)}%` }} /></div><p className={effectiveDelta >= 0 ? 'delta-positive' : 'delta-negative'}>{effectiveDelta > 0 ? '+' : ''}{Math.round(effectiveDelta * 100)} percentage points from baseline</p></div>
          <div className="panel scenario-changes"><span className="eyebrow">WHAT CHANGED</span>{result.changelog.length ? <ul>{result.changelog.map((item, index) => <li key={index}>{item.replace(/^[✓✗]\s*/, '')}</li>)}</ul> : <p className="muted">Adjust a control to see the estimated effect.</p>}</div>
          <button className="button button-outline scenario-save" onClick={save}>Save scenario to comparison</button>
          {saved.length > 0 && <div className="panel scenario-saved"><span className="eyebrow">SESSION COMPARISON / {saved.length}</span><div className="saved-row"><span>Base case</span><strong>{percent(baseline)}</strong></div>{saved.map((item, index) => <button className="saved-row" key={index} onClick={() => setTweaks(item.tweaks)} title="Load this scenario"><span>{item.name}</span><strong>{percent(item.adjusted)}</strong></button>)}</div>}
        </div>
      </div>
    </>}
  </div>
}
