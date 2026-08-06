import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import { useSidebar } from '../../hooks/useSidebar'

const PAGE_TITLES = {
  '/': 'Home',
  '/precedent-search': 'Precedent Search',
  '/fact-extraction': 'Fact Extraction',
  '/argument-graph': 'Argument Graph',
  '/simulation': 'Judicial Simulation',
  '/what-if': 'What-If Analyzer',
  '/settings': 'Settings',
}

export default function Layout() {
  const { pathname } = useLocation()
  const { collapsed } = useSidebar()
  const title = PAGE_TITLES[pathname] || 'Legal Intelligence Terminal'

  return (
    <div className="min-h-screen bg-white transition-colors duration-200 dark:bg-surface-dark">
      <Sidebar />

      <div
        className={`flex min-h-screen flex-col transition-[margin] duration-200 ease-out ${
          collapsed ? 'ml-0' : 'ml-60'
        }`}
      >
        <Topbar title={title} />

        <main className="flex-1">
          <div className="mx-auto w-full max-w-[1100px] p-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
