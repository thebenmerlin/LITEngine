import { Link } from 'react-router-dom'
import { ArrowRight, ArrowUpRight, ChartNoAxesCombined, FileText, GitBranch, Search, SlidersHorizontal } from 'lucide-react'
import { CaseComposer, ErrorNotice, SectionTitle, WorkflowStrip, percent } from '../components/workspace/Primitives'
import { useWorkspace } from '../workspace/WorkspaceContext'

const destinations = [
  { number: '01', title: 'Case facts', caption: 'Parties, issues, statutes and material facts', to: '/fact-extraction', icon: FileText },
  { number: '02', title: 'Precedents', caption: 'Relevant judgments and their source excerpts', to: '/precedent-search', icon: Search },
  { number: '03', title: 'Argument map', caption: 'Claims, support, citations and weak points', to: '/argument-graph', icon: GitBranch },
  { number: '04', title: 'Outcome analysis', caption: 'Estimate and factor-level explanation', to: '/simulation', icon: ChartNoAxesCombined },
  { number: '05', title: 'Scenarios', caption: 'Explore how assumptions change the estimate', to: '/what-if', icon: SlidersHorizontal },
]

export default function Home() {
  const { caseText, profile, precedents, graph, simulation, errors } = useWorkspace()
  const caseName = profile?.parties?.petitioner && profile?.parties?.respondent
    ? `${profile.parties.petitioner} v. ${profile.parties.respondent}`
    : 'Your next case starts here.'
  const ready = Boolean(profile)

  return <div className="home-page">
    <div className="home-hero">
      <div className="home-intro">
        <span className="eyebrow accent">LEGAL INTELLIGENCE / WORKSPACE</span>
        <h1>{caseName}</h1>
        <p>{ready
          ? 'A connected view of the facts, precedent landscape, argument structure and outcome estimate for this matter.'
          : 'Turn case material into a clear line of reasoning. Follow the evidence, test the argument, and inspect every conclusion.'}</p>
        <div className="home-hero-meta"><span>INDIAN COURTS</span><span className="meta-separator" /><span>RESEARCH ENVIRONMENT</span></div>
      </div>
      <div className="home-editor"><CaseComposer /></div>
    </div>

    <WorkflowStrip />

    {ready && <div className="case-overview">
      <div className="case-overview-lead">
        <span className="eyebrow">CURRENT CASE</span>
        <strong>{profile.case_type || 'Matter'}</strong>
        <span>{profile.court_level || 'Court unspecified'}</span>
      </div>
      <div className="case-metric"><strong>{profile.legal_issues?.length || 0}</strong><span>Legal issues</span></div>
      <div className="case-metric"><strong>{precedents?.length ?? '—'}</strong><span>Precedents found</span></div>
      <div className="case-metric"><strong>{graph?.weak_nodes?.length ?? '—'}</strong><span>Claims to review</span></div>
      <div className="case-metric"><strong>{percent(simulation?.result?.win_probability)}</strong><span>Outcome estimate</span></div>
    </div>}

    <div className="home-lower">
      <section>
        <SectionTitle number="A" title="Explore the case" aside="EACH VIEW SHARES THIS MATTER" />
        <div className="destination-list">
          {destinations.map(({ number, title, caption, to, icon: Icon }) => <Link key={to} to={to} className="destination-row">
            <span className="destination-number">{number}</span><Icon size={21} strokeWidth={1.55} />
            <span className="destination-copy"><strong>{title}</strong><small>{caption}</small></span>
            <ArrowUpRight size={18} className="destination-arrow" />
          </Link>)}
        </div>
      </section>
      <aside className="home-aside">
        <span className="eyebrow">RESEARCH NOTE</span>
        <div className="aside-rule" />
        <h2>Good analysis is traceable.</h2>
        <p>Each view should make its inputs visible. The argument map shows generated relationships for review; the scenario tool shows estimates from changed assumptions.</p>
        {ready ? <Link to="/argument-graph" className="inline-link">Inspect the argument map <ArrowRight size={16} /></Link>
          : <span className="aside-footnote">Add a case description to begin.</span>}
      </aside>
    </div>
    {Object.entries(errors).filter(([key, value]) => key !== 'facts' && value).map(([key, value]) => <ErrorNotice key={key} title={`${key[0].toUpperCase()}${key.slice(1)} needs attention`} message={value} />)}
    {!caseText.trim() && <p className="session-note">Your draft stays in this browser tab. Analysis results are held only for the current session.</p>}
  </div>
}
