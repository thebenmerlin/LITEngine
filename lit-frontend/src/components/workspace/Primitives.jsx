import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, ChevronDown, CircleCheck, CircleDot, LoaderCircle, RotateCcw, Sparkles } from 'lucide-react'
import { SAMPLE_CASES } from '../../data/sampleCases'
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

export function SampleCaseMenu({ disabled = false }) {
  const { setCaseText, setAppellantType, setFilingDate } = useWorkspace()
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    function onPointerDown(event) {
      if (rootRef.current && !rootRef.current.contains(event.target)) setOpen(false)
    }
    function onKeyDown(event) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  function pick(sample) {
    setCaseText(sample.text)
    setAppellantType(sample.appellantType)
    setFilingDate(sample.filingDate)
    setOpen(false)
  }

  return <div className="sample-menu" ref={rootRef}>
    <button type="button" className="text-button" onClick={() => setOpen((value) => !value)} disabled={disabled} aria-haspopup="menu" aria-expanded={open}>
      <Sparkles size={15} /> Try sample <ChevronDown size={13} />
    </button>
    {open && <ul className="sample-menu-list" role="menu">
      {SAMPLE_CASES.map((sample) => (
        <li key={sample.id} role="none">
          <button type="button" role="menuitem" onClick={() => pick(sample)}>{sample.label}</button>
        </li>
      ))}
    </ul>}
  </div>
}

export function CaseComposer({ compact = false, showHeading = true }) {
  const { caseText, setCaseText, appellantType, filingDate, runAnalysis, busy, stale, status, errors } = useWorkspace()
  const activeStep = Object.entries(status).find(([, value]) => value === 'running')?.[0]
  const labels = { facts: 'Extracting case facts', precedents: 'Finding precedents', graph: 'Mapping arguments', simulation: 'Estimating outcome' }

  return <div className={`case-composer ${compact ? 'compact' : ''}`}>
    {showHeading && <div className="composer-header"><span className="eyebrow">CASE MATERIAL</span><span>DRAFT STORED FOR THIS SESSION</span></div>}
    <label htmlFor="case-description" className="sr-only">Case description</label>
    <textarea id="case-description" value={caseText} onChange={(event) => setCaseText(event.target.value)}
      placeholder="Paste pre-decision case facts, a brief, or a petition. Include the legal questions and material facts for a stronger analysis." />
    <AppellantTypeField disabled={busy} />
    <FilingDateField disabled={busy} />
    <div className="composer-footer">
      <div className="composer-note">{caseText.length ? `${caseText.trim().split(/\s+/).length} words` : 'Start with the facts of the matter'}</div>
      <div className="composer-buttons">
        <SampleCaseMenu disabled={busy} />
        <button className="button button-primary" onClick={runAnalysis} disabled={!caseText.trim() || !appellantType || !filingDate || busy}>
          {busy ? <><LoaderCircle size={16} className="spin" /> {labels[activeStep] || 'Analyzing'}</> : <>{stale ? 'Reanalyze case' : 'Analyze case'} <ArrowRight size={16} /></>}
        </button>
      </div>
    </div>
    {stale && <p className="composer-stale">The case text has changed since the current results were generated.</p>}
    <ErrorNotice message={errors.facts} title="Fact extraction failed" />
  </div>
}

export function AppellantTypeField({ disabled = false }) {
  const { appellantType, setAppellantType } = useWorkspace()
  return <div className="appellant-field">
    <label htmlFor="appellant-type">Who is bringing the appeal?</label>
    <select id="appellant-type" required value={appellantType} disabled={disabled} onChange={(event) => setAppellantType(event.target.value)}>
      <option value="" disabled>Select appellant type</option>
      <option value="accused_appeal">Accused person appealing a conviction</option>
      <option value="state_appeal">State or complainant appealing an acquittal</option>
      <option value="unclear">Other or unsure</option>
    </select>
  </div>
}

export function FilingDateField({ disabled = false }) {
  const { filingDate, setFilingDate } = useWorkspace()
  return <div className="appellant-field">
    <label htmlFor="filing-date">Appeal filing date</label>
    <input id="filing-date" type="date" required value={filingDate} disabled={disabled} onChange={(event) => setFilingDate(event.target.value)} />
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
