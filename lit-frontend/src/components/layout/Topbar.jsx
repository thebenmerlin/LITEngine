import { Sun, Moon, UserCircle } from 'lucide-react'
import { useTheme } from '../../hooks/useTheme'

export default function Topbar({ title }) {
  const { dark, toggle } = useTheme()

  return (
    <header className="flex h-[60px] items-center justify-between border-b border-gray-200 bg-white px-8 transition-colors duration-200 dark:border-gray-800 dark:bg-surface-dark">
      <h1 className="text-base font-semibold text-gray-900 dark:text-gray-100">
        {title}
      </h1>

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

        {/* User avatar placeholder */}
        <UserCircle className="h-7 w-7 text-gray-400 dark:text-gray-500" />
      </div>
    </header>
  )
}
