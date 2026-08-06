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
  PanelLeftClose,
  PanelLeftOpen,
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

function Logo() {
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
      <span className="flex flex-col leading-none">
        <span className="text-[15px] font-semibold tracking-tight text-navy-700 dark:text-gray-100">
          LIT
        </span>
        <span className="mt-0.5 text-[10px] font-medium uppercase tracking-wider text-gray-400 dark:text-gray-500">
          Legal Intelligence
        </span>
      </span>
    </Link>
  )
}

/* ------------------------------------------------------------------ */
/*  Full nav panel — shared by the pinned-open and peek states         */
/* ------------------------------------------------------------------ */

function SidebarPanel({ collapsed, onToggle }) {
  return (
    <>
      {/* Header — logo + pin/collapse toggle live together at the TOP */}
      <div className="flex h-16 shrink-0 items-center justify-between border-b border-gray-200 px-4 dark:border-gray-800">
        <Logo />
        <button
          onClick={onToggle}
          className="rounded-md p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 dark:text-gray-500 dark:hover:bg-gray-800 dark:hover:text-gray-300"
          aria-label={collapsed ? 'Pin sidebar open' : 'Collapse sidebar'}
          title={collapsed ? 'Pin sidebar open' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <PanelLeftOpen className="h-[18px] w-[18px]" />
          ) : (
            <PanelLeftClose className="h-[18px] w-[18px]" />
          )}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-4">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-150 ${
                isActive
                  ? 'border-l-[3px] border-navy-700 bg-navy-700/5 text-navy-700 dark:border-navy-400 dark:bg-navy-700/20 dark:text-navy-200'
                  : 'border-l-[3px] border-transparent text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200'
              }`
            }
          >
            <Icon className="h-[18px] w-[18px] shrink-0" />
            <span className="whitespace-nowrap">{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-gray-200 px-6 py-3 dark:border-gray-800">
        <p className="text-[11px] text-gray-400 dark:text-gray-600">
          v0.1.0 &middot; Indian Legal AI
        </p>
      </div>
    </>
  )
}

export default function Sidebar() {
  const { collapsed, toggle } = useSidebar()
  const [peeking, setPeeking] = useState(false)

  /* ---- Pinned open — normal, in-flow sidebar ---------------------- */
  if (!collapsed) {
    return (
      <aside className="fixed inset-y-0 left-0 z-30 flex w-60 flex-col border-r border-gray-200 bg-[#F9FAFB] dark:border-gray-800 dark:bg-[#161B27]">
        <SidebarPanel collapsed={false} onToggle={toggle} />
      </aside>
    )
  }

  /* ---- Collapsed — sidebar is gone; a thin edge zone reveals a      */
  /* Notion-style peek overlay on hover, without touching page layout. */
  return (
    <div
      onMouseEnter={() => setPeeking(true)}
      onMouseLeave={() => setPeeking(false)}
      className="fixed inset-y-0 left-0 z-40"
    >
      {/* Slim always-present edge strip — hover target + visual hint */}
      <div className="group flex h-full w-3 items-center justify-center border-r border-transparent bg-transparent">
        <span className="h-10 w-[3px] rounded-full bg-gray-300/70 transition-colors group-hover:bg-navy-700/50 dark:bg-gray-700/70 dark:group-hover:bg-navy-400/50" />
      </div>

      {/* Peek overlay — full sidebar, floats above content, doesn't reflow it */}
      {peeking && (
        <aside className="absolute inset-y-0 left-0 flex w-60 animate-fade-in-up flex-col border-r border-gray-200 bg-[#F9FAFB] shadow-2xl dark:border-gray-800 dark:bg-[#161B27]">
          <SidebarPanel collapsed onToggle={toggle} />
        </aside>
      )}
    </div>
  )
}
