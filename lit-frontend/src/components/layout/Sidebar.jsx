import { useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import {
  Scale,
  Search,
  FileSearch,
  GitBranch,
  Brain,
  Settings,
  FlaskConical,
  ChevronsLeft,
  ChevronsRight,
} from 'lucide-react'
import { useSidebar } from '../../hooks/useSidebar'

const NAV_ITEMS = [
  { to: '/', label: 'Home', icon: Scale },
  { to: '/precedent-search', label: 'Precedent Search', icon: Search },
  { to: '/fact-extraction', label: 'Fact Extraction', icon: FileSearch },
  { to: '/argument-graph', label: 'Argument Graph', icon: GitBranch },
  { to: '/simulation', label: 'Simulation', icon: Brain },
  { to: '/what-if', label: 'What-If Analyzer', icon: FlaskConical },
  { to: '/settings', label: 'Settings', icon: Settings },
]

/* ------------------------------------------------------------------ */
/*  Logo — animated wordmark, always links home                       */
/* ------------------------------------------------------------------ */

function Logo({ expanded }) {
  return (
    <Link
      to="/"
      className="group flex items-center gap-3 outline-none"
      aria-label="LIT — go to home"
    >
      <span className="relative flex h-9 w-9 shrink-0 items-center justify-center">
        <span className="absolute inset-0 rounded-lg bg-navy-700 opacity-40 blur-[6px] transition-opacity duration-300 group-hover:opacity-70 dark:bg-navy-400" />
        <span className="absolute inset-0 rounded-lg bg-navy-700/50 dark:bg-navy-400/50 animate-ping-slow" />
        <span className="relative flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-navy-600 to-navy-800 shadow-sm transition-transform duration-300 ease-out group-hover:-rotate-6 group-hover:scale-110 dark:from-navy-500 dark:to-navy-700">
          <Scale className="h-[18px] w-[18px] text-white" strokeWidth={2.25} />
        </span>
      </span>
      {expanded && (
        <span className="flex flex-col leading-none">
          <span className="text-[15px] font-semibold tracking-tight text-navy-700 dark:text-gray-100">
            LIT
          </span>
          <span className="mt-0.5 text-[10px] font-medium uppercase tracking-wider text-gray-400 dark:text-gray-500">
            Legal Intelligence
          </span>
        </span>
      )}
    </Link>
  )
}

export default function Sidebar() {
  const { collapsed, toggle } = useSidebar()
  const [hovered, setHovered] = useState(false)

  // Visually expanded either because it's pinned open, or because the user
  // is hovering a collapsed rail (Notion-style peek). Peek never changes
  // the persisted `collapsed` value that Layout uses for content margin.
  const peeking = collapsed && hovered
  const expanded = !collapsed || peeking

  return (
    <aside
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={`fixed inset-y-0 left-0 z-40 flex flex-col border-r border-gray-200 bg-[#F9FAFB] transition-[width] duration-200 ease-out dark:border-gray-800 dark:bg-[#161B27] ${
        expanded ? 'w-60' : 'w-16'
      } ${peeking ? 'shadow-xl' : ''}`}
    >
      {/* Wordmark */}
      <div className="flex h-16 shrink-0 items-center justify-between border-b border-gray-200 px-4 dark:border-gray-800">
        <Logo expanded={expanded} />
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-0.5 overflow-hidden px-3 py-4">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            title={expanded ? undefined : label}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-150 ${
                isActive
                  ? 'border-l-[3px] border-navy-700 bg-navy-700/5 text-navy-700 dark:border-navy-400 dark:bg-navy-700/20 dark:text-navy-200'
                  : 'border-l-[3px] border-transparent text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200'
              }`
            }
          >
            <Icon className="h-[18px] w-[18px] shrink-0" />
            {expanded && <span className="whitespace-nowrap">{label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Footer — collapse toggle */}
      <div className="border-t border-gray-200 px-3 py-3 dark:border-gray-800">
        <button
          onClick={toggle}
          className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-xs font-medium text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 dark:text-gray-500 dark:hover:bg-gray-800 dark:hover:text-gray-300"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <ChevronsRight className="h-4 w-4 shrink-0" />
          ) : (
            <ChevronsLeft className="h-4 w-4 shrink-0" />
          )}
          {expanded && <span className="whitespace-nowrap">Collapse</span>}
        </button>
        {expanded && (
          <p className="mt-2 px-3 text-[11px] text-gray-400 dark:text-gray-600">
            v0.1.0 &middot; Indian Legal AI
          </p>
        )}
      </div>
    </aside>
  )
}
