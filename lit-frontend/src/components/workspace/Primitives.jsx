import { Link } from 'react-router-dom'
import { ArrowRight, CircleCheck, CircleDot, LoaderCircle, RotateCcw, Sparkles } from 'lucide-react'
import { SAMPLE_CASE_TEXT } from '../../data/sampleCases'
import { useWorkspace } from '../../workspace/WorkspaceContext'

export const percent = (value) => value == null ? '—' : `${Math.round(value * 100)}%`

export function PageHeading({ eyebrow, title, description, action }) {
  return <div className="page-heading">
    <div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>
    {action && <div className="page-heading-action">{action}</div>}
  </div>
}

export function SectionTitle({ number, title, aside }) {
  return <div className="section-title"><div><span>{number}</span><h2>{title}</h2></div>{aside && <small>{aside}</small>}</div>
}

export function ErrorNotice({ message, title = 'Unable to complete this step' }) {
  if (!message) return null
  return <div className="notice notice-error" role="alert"><strong>{title}</strong><span>{message}</span></div>
}

export function InfoNotice({ children }) {
  return <div className="notice notice-info">{children}</div>
}

export function EmptyPanel({ number, title, body, action, icon: Icon }) {
  return <div className="empty-panel">
    <div className="empty-panel-symbol">{Icon ? <Icon size={28} strokeWidth={1.4} /> : <span>{number || '—'}</span>}</div>
    <h2>{title}</h2><p>{body}</p>{action && <div className="empty-panel-action">{action}</div>}
  </div>
}

export function CaseComposer({ compact = false, showHeading = true }) {
  const { caseText, setCaseText, runAnalysis, busy, stale, status, errors } = useWorkspace()
  const activeStep = Object.entries(status).find(([, value]) => value === 'running')?.[0]
  const labels = { facts: 'Extracting case facts', precedents: 'Finding precedents', graph: 'Mapping arguments', simulation: 'Estimating outcome' }

  return <div className={`case-composer ${compact ? 'compact' : ''}`}>
    {showHeading && <div className="composer-header"><span className="eyebrow">CASE MATERIAL</span><span>DRAFT STORED FOR THIS SESSION</span></div>}
    <label htmlFor="case-description" className="sr-only">Case description</label>
    <textarea id="case-description" value={caseText} onChange={(event) => setCaseText(event.target.value)}
      placeholder="Paste a case description, brief, FIR, or judgment excerpt. Include the legal questions and material facts for a stronger analysis." />
    <div className="composer-footer">
      <div className="composer-note">{caseText.length ? `${caseText.trim().split(/\s+/).length} words` : 'Start with the facts of the matter'}</div>
      <div className="composer-buttons">
        <button className="text-button" onClick={() => setCaseText(SAMPLE_CASE_TEXT)} disabled={busy}><Sparkles size={15} /> Try sample</button>
        <button className="button button-primary" onClick={runAnalysis} disabled={!caseText.trim() || busy}>
          {busy ? <><LoaderCircle size={16} className="spin" /> {labels[activeStep] || 'Analyzing'}</> : <>{stale ? 'Reanalyze case' : 'Analyze case'} <ArrowRight size={16} /></>}
        </button>
      </div>
    </div>
    {stale && <p className="composer-stale">The case text has changed since the current results were generated.</p>}
    <ErrorNotice message={errors.facts} title="Fact extraction failed" />
  </div>
}

export function WorkflowStrip() {
  const { status, profile, precedents, graph, simulation } = useWorkspace()
  const steps = [
    { key: 'facts', label: 'Facts', to: '/fact-extraction', ready: Boolean(profile) },
    { key: 'precedents', label: 'Precedents', to: '/precedent-search', ready: Boolean(precedents) },
    { key: 'graph', label: 'Argument map', to: '/argument-graph', ready: Boolean(graph) },
    { key: 'simulation', label: 'Outcome', to: '/simulation', ready: Boolean(simulation) },
  ]
  return <div className="workflow-strip" aria-label="Analysis progress">
    {steps.map((step, index) => <Link to={step.to} className={`workflow-step ${step.ready ? 'ready' : ''} ${status[step.key] === 'running' ? 'running' : ''} ${status[step.key] === 'error' ? 'error' : ''}`} key={step.key}>
      <span className="workflow-index">{status[step.key] === 'running' ? <LoaderCircle size={15} className="spin" /> : step.ready ? <CircleCheck size={16} /> : <CircleDot size={16} />}</span>
      <span>{String(index + 1).padStart(2, '0')} / {step.label}</span>
    </Link>)}
  </div>
}

export function RebuildButton({ onClick, disabled, children = 'Refresh analysis' }) {
  return <button className="button button-outline" onClick={onClick} disabled={disabled}><RotateCcw size={15} />{children}</button>
}
