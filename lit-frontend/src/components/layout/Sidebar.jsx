import { NavLink } from 'react-router-dom'
import {
  ArrowUpRight,
  ChartNoAxesCombined,
  FileText,
  GitBranch,
  LayoutDashboard,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Settings2,
  SlidersHorizontal,
  X,
} from 'lucide-react'
import { useWorkspace } from '../../workspace/WorkspaceContext'
import { useSidebar } from '../../hooks/useSidebar'

const links = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/fact-extraction', label: 'Case facts', icon: FileText },
  { to: '/precedent-search', label: 'Precedents', icon: Search },
  { to: '/argument-graph', label: 'Argument map', icon: GitBranch },
  { to: '/simulation', label: 'Outcome analysis', icon: ChartNoAxesCombined },
  { to: '/what-if', label: 'Scenarios', icon: SlidersHorizontal },
]

export default function Sidebar({ open, onClose, pathname }) {
  const { profile, caseText, graph, precedents, simulation } = useWorkspace()
  const { collapsed, toggle } = useSidebar()

  const caseName = profile?.parties?.petitioner && profile?.parties?.respondent
    ? `${profile.parties.petitioner} v. ${profile.parties.respondent}`
    : caseText.trim() ? 'Untitled case' : 'No active case'
  const completed = [profile, precedents, graph, simulation].filter(Boolean).length

  return (
    <>
      {open && <button className="sidebar-backdrop" onClick={onClose} aria-label="Close navigation" />}
      <aside className={`sidebar ${open ? 'is-open' : ''} ${collapsed ? 'is-collapsed' : ''}`}>
        <div className="sidebar-top">
          <NavLink to="/" className="brand" onClick={onClose} aria-label="LIT overview" title="LIT Legal Intelligence">
            <span className="brand-mark">L<span>.</span></span>
            <span className="brand-copy"><strong>LIT</strong><small>LEGAL INTELLIGENCE</small></span>
          </NavLink>
          <button
            type="button"
            className="collapse-toggle icon-button"
            onClick={toggle}
            title={collapsed ? 'Expand sidebar (Ctrl+B)' : 'Collapse sidebar (Ctrl+B)'}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
          </button>
          <button className="mobile-close icon-button" onClick={onClose} aria-label="Close navigation">
            <X size={18} />
          </button>
        </div>

        <div
          className="sidebar-case"
          title={`${caseName} • ${completed ? `${completed} of 4 stages ready` : 'No active case'}`}
        >
          <div className="sidebar-case-expanded">
            <span className="sidebar-eyebrow">ACTIVE MATTER</span>
            <strong title={caseName}>{caseName}</strong>
            <div className="sidebar-progress"><span style={{ width: `${completed * 25}%` }} /></div>
            <small>{completed ? `${completed} of 4 analysis stages ready` : 'Start with a case description'}</small>
          </div>
          <div className="sidebar-case-mini">
            <div className="sidebar-case-mini-badge">
              <span className="sidebar-case-mini-dot" style={{ backgroundColor: completed > 0 ? '#d89172' : '#52625c' }} />
              <span className="sidebar-case-mini-count">{completed}/4</span>
            </div>
            <div className="sidebar-progress"><span style={{ width: `${completed * 25}%` }} /></div>
          </div>
        </div>

        <nav className="sidebar-nav" aria-label="Primary navigation">
          <span className="sidebar-eyebrow">WORKSPACE</span>
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={onClose}
              title={label}
              aria-label={label}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              <Icon size={17} strokeWidth={1.8} />
              <span className="nav-label">{label}</span>
              {pathname === to && <span className="nav-active-dot" />}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <NavLink
            to="/settings"
            className="nav-link"
            onClick={onClose}
            title="Settings"
            aria-label="Settings"
          >
            <Settings2 size={17} />
            <span className="nav-label">Settings</span>
          </NavLink>
          <a
            href="https://indiankanoon.org/"
            target="_blank"
            rel="noreferrer"
            className="sidebar-source"
            title="Indian Kanoon (External database)"
            aria-label="Indian Kanoon"
          >
            <span className="source-label">Indian Kanoon</span>
            <ArrowUpRight size={14} />
          </a>
          <span className="sidebar-version">LIT / RESEARCH WORKSPACE · V0.2</span>
        </div>
      </aside>
    </>
  )
}
