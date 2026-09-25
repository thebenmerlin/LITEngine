import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ArrowRight, Menu, Moon, PanelLeftClose, PanelLeftOpen, Plus, Sun } from 'lucide-react'
import { useTheme } from '../../hooks/useTheme'
import { useWorkspace } from '../../workspace/WorkspaceContext'
import { useSidebar } from '../../hooks/useSidebar'

const titles = {
  '/': 'Overview',
  '/fact-extraction': 'Case facts',
  '/precedent-search': 'Precedents',
  '/argument-graph': 'Argument map',
  '/simulation': 'Outcome analysis',
  '/what-if': 'Scenarios',
  '/settings': 'Settings',
}

export default function Topbar({ onOpenMenu }) {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { dark, toggle } = useTheme()
  const { health, clearCase, caseText } = useWorkspace()
  const { collapsed, toggle: toggleSidebar } = useSidebar()

  const newCase = () => {
    clearCase()
    navigate('/')
  }

  return (
    <header className="topbar">
      <div className="topbar-path">
        <button className="mobile-menu icon-button" onClick={onOpenMenu} aria-label="Open navigation"><Menu size={20} /></button>
        <button
          type="button"
          className="desktop-sidebar-toggle icon-button"
          onClick={toggleSidebar}
          aria-label={collapsed ? 'Expand sidebar (Ctrl+B)' : 'Collapse sidebar (Ctrl+B)'}
          title={collapsed ? 'Expand sidebar (Ctrl+B)' : 'Collapse sidebar (Ctrl+B)'}
        >
          {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
        </button>
        <Link to="/" className="topbar-root">WORKSPACE</Link>
        <span className="topbar-slash">/</span>
        <span>{titles[pathname] || 'Overview'}</span>
      </div>
      <div className="topbar-actions">
        <span className={`connection ${health}`}><span className="connection-dot" />{health === 'online' ? 'CONNECTED' : health === 'offline' ? 'OFFLINE' : 'CONNECTING'}</span>
        <button className="icon-button theme-button" onClick={toggle} aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}>{dark ? <Sun size={18} /> : <Moon size={18} />}</button>
        {caseText.trim() ? (
          <button className="button button-quiet topbar-new" onClick={newCase}><Plus size={16} /> New case</button>
        ) : (
          <Link to="/" className="button button-quiet topbar-new">Start a case <ArrowRight size={15} /></Link>
        )}
      </div>
    </header>
  )
}
