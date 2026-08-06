import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Sun, Moon, Settings, Info, ChevronDown, PanelLeftOpen } from 'lucide-react'
import { useTheme } from '../../hooks/useTheme'
import { useSidebar } from '../../hooks/useSidebar'

/* ------------------------------------------------------------------ */
/*  Clickable profile avatar with a small dropdown menu               */
/* ------------------------------------------------------------------ */

function ProfileMenu() {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    function onClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    function onEscape(e) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    document.addEventListener('keydown', onEscape)
    return () => {
      document.removeEventListener('mousedown', onClickOutside)
      document.removeEventListener('keydown', onEscape)
    }
  }, [])

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 rounded-full p-0.5 pr-1.5 transition-colors hover:bg-gray-100 dark:hover:bg-gray-800"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-navy-500 to-navy-700 text-xs font-semibold text-white dark:from-navy-400 dark:to-navy-600">
          LR
        </span>
        <ChevronDown
          className={`h-3.5 w-3.5 text-gray-400 transition-transform duration-150 ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-[calc(100%+8px)] w-56 animate-fade-in-up overflow-hidden rounded-lg border border-gray-200 bg-white py-1.5 shadow-lg dark:border-gray-800 dark:bg-surface-dark"
        >
          <div className="border-b border-gray-100 px-3.5 py-2.5 dark:border-gray-800">
            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
              Legal Researcher
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500">
              Local session &middot; no auth
            </p>
          </div>
          <Link
            to="/settings"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2.5 px-3.5 py-2 text-sm text-gray-600 transition-colors hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            <Settings className="h-4 w-4" />
            Settings
          </Link>
          <a
            href="#about"
            onClick={(e) => {
              e.preventDefault()
              setOpen(false)
            }}
            className="flex items-center gap-2.5 px-3.5 py-2 text-sm text-gray-600 transition-colors hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            <Info className="h-4 w-4" />
            LIT v0.1.0
          </a>
        </div>
      )}
    </div>
  )
}

export default function Topbar({ title }) {
  const { dark, toggle } = useTheme()
  const { collapsed, toggle: toggleSidebar } = useSidebar()

  return (
    <header className="flex h-[60px] items-center justify-between border-b border-gray-200 bg-white pl-6 pr-8 transition-colors duration-200 dark:border-gray-800 dark:bg-surface-dark">
      <div className="flex items-center gap-3">
        {collapsed && (
          <button
            onClick={toggleSidebar}
            className="rounded-md p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 dark:text-gray-500 dark:hover:bg-gray-800 dark:hover:text-gray-300"
            aria-label="Open sidebar"
            title="Open sidebar"
          >
            <PanelLeftOpen className="h-[18px] w-[18px]" />
          </button>
        )}
        <h1 className="text-base font-semibold text-gray-900 dark:text-gray-100">
          {title}
        </h1>
      </div>

      <div className="flex items-center gap-4">
        {/* Dark mode toggle */}
        <button
          onClick={toggle}
          className="rounded-md p-2 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200"
          aria-label="Toggle dark mode"
        >
          {dark ? (
            <Sun className="h-[18px] w-[18px]" />
          ) : (
            <Moon className="h-[18px] w-[18px]" />
          )}
        </button>

        <div className="h-5 w-px bg-gray-200 dark:bg-gray-800" />

        <ProfileMenu />
      </div>
    </header>
  )
}
