import { NavLink } from 'react-router-dom'
import {
  Scale,
  Search,
  FileSearch,
  GitBranch,
  Brain,
  Settings,
  FlaskConical,
} from 'lucide-react'

const NAV_ITEMS = [
  { to: '/', label: 'Home', icon: Scale },
  { to: '/precedent-search', label: 'Precedent Search', icon: Search },
  { to: '/fact-extraction', label: 'Fact Extraction', icon: FileSearch },
  { to: '/argument-graph', label: 'Argument Graph', icon: GitBranch },
  { to: '/simulation', label: 'Simulation', icon: Brain },
  { to: '/what-if', label: 'What-If Analyzer', icon: FlaskConical },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export default function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-60 flex-col border-r border-gray-200 bg-[#F9FAFB] transition-colors duration-200 dark:border-gray-800 dark:bg-[#161B27]">
      {/* Wordmark */}
      <div className="flex h-16 items-center border-b border-gray-200 px-6 dark:border-gray-800">
        <span className="text-lg font-semibold tracking-tight text-navy-700 dark:text-gray-100">
          LIT
        </span>
        <span className="ml-2 text-xs font-medium text-gray-400 dark:text-gray-500">
          Legal Intelligence
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-0.5 px-3 py-4">
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
            <Icon className="h-[18px] w-[18px]" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-gray-200 px-6 py-4 dark:border-gray-800">
        <p className="text-xs text-gray-400 dark:text-gray-600">
          v0.1.0 &middot; Indian Legal AI
        </p>
      </div>
    </aside>
  )
}
