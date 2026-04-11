import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import Topbar from './Topbar'

const PAGE_TITLES = {
  '/': 'Home',
  '/precedent-search': 'Precedent Search',
  '/fact-extraction': 'Fact Extraction',
  '/argument-graph': 'Argument Graph',
  '/simulation': 'Judicial Simulation',
  '/settings': 'Settings',
}

export default function Layout() {
  const { pathname } = useLocation()
  const title = PAGE_TITLES[pathname] || 'Legal Intelligence Terminal'

  return (
    <div className="min-h-screen bg-white transition-colors duration-200 dark:bg-surface-dark">
      <Sidebar />

      <div className="ml-60 flex min-h-screen flex-col">
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
