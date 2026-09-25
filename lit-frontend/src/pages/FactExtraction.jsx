import { Link } from 'react-router-dom'
import { ArrowRight, Download, FileText } from 'lucide-react'
import { CaseComposer, EmptyPanel, PageHeading, SectionTitle, percent } from '../components/workspace/Primitives'
import { useWorkspace } from '../workspace/WorkspaceContext'

function downloadProfile(profile) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(profile, null, 2)], { type: 'application/json' }))
  const link = document.createElement('a')
  link.href = url
  link.download = 'lit-case-profile.json'
  link.click()
  URL.revokeObjectURL(url)
}

export default function FactExtraction() {
  const { profile, status, stale } = useWorkspace()
  return <div className="page-stack">
    <PageHeading eyebrow="01 / CASE MATERIAL" title="Case facts" description="A structured reading of the parties, legal questions, statutory references and material facts."
      action={profile && <button className="button button-outline" onClick={() => downloadProfile(profile)}><Download size={15} /> Export profile</button>} />
    <CaseComposer compact />
    {stale && <div className="notice notice-info">These facts were generated from the previous version of the case text. Reanalyze to update them.</div>}
    {status.facts === 'running' && <div className="loading-line"><span className="spin-dot" /> Extracting parties, issues and material facts…</div>}
    {!profile && status.facts !== 'running' && <EmptyPanel icon={FileText} title="The case profile will appear here" body="Analyze a case description to organize its facts and legal questions into a usable brief." />}
    {profile && <>
      <div className="facts-summary">
        <div><span className="eyebrow">PETITIONER / APPELLANT</span><strong>{profile.parties?.petitioner || 'Not identified'}</strong></div>
        <div className="facts-versus">v.</div>
        <div><span className="eyebrow">RESPONDENT</span><strong>{profile.parties?.respondent || 'Not identified'}</strong></div>
        <div className="facts-summary-meta"><span>{profile.court_level || 'Court unknown'}</span><span>{profile.case_type || 'Matter'}</span><span>Extraction confidence {percent(profile.metadata?.confidence)}</span></div>
      </div>

      <div className="facts-grid">
        <section className="panel facts-primary">
          <SectionTitle number="01" title="Questions before the court" aside={`${profile.legal_issues?.length || 0} IDENTIFIED`} />
          {profile.legal_issues?.length ? <ol className="numbered-list">{profile.legal_issues.map((issue, index) => <li key={index}><span>{String(index + 1).padStart(2, '0')}</span><p>{issue}</p></li>)}</ol> : <p className="muted">No explicit legal questions were identified.</p>}
          <SectionTitle number="02" title="Material facts" aside={`${profile.key_facts?.length || 0} IDENTIFIED`} />
          {profile.key_facts?.length ? <ol className="numbered-list">{profile.key_facts.map((fact, index) => <li key={index}><span>{String(index + 1).padStart(2, '0')}</span><p>{fact}</p></li>)}</ol> : <p className="muted">No material facts were identified.</p>}
        </section>
        <aside className="facts-aside">
          <section className="panel inset-panel"><span className="eyebrow">STATUTORY REFERENCES</span><div className="tag-wrap">{profile.ipc_sections?.length ? profile.ipc_sections.map((section) => <span className="tag" key={section}>{section}</span>) : <span className="muted">None extracted</span>}</div></section>
          <section className="panel inset-panel"><span className="eyebrow">ACTS REFERENCED</span><ul className="plain-list">{profile.acts_referenced?.length ? profile.acts_referenced.map((act) => <li key={act}>{act}</li>) : <li className="muted">None extracted</li>}</ul></section>
          <section className="panel inset-panel"><span className="eyebrow">RELIEF SOUGHT</span><p>{profile.relief_sought || 'Not identified in the supplied text.'}</p></section>
          <Link className="next-link" to="/precedent-search">Review precedents <ArrowRight size={17} /></Link>
        </aside>
      </div>
    </>}
  </div>
}
