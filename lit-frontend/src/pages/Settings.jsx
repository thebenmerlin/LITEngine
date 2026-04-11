import { useTheme } from '../hooks/useTheme'
import { Sun, Moon } from 'lucide-react'

export default function Settings() {
  const { dark, toggle } = useTheme()

  return (
    <div>
      <h2 className="mb-6 text-lg font-semibold text-gray-900 dark:text-gray-100">
        Settings
      </h2>

      {/* Appearance */}
      <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-surface-dark">
        <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">
          Appearance
        </h3>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Choose your preferred theme for the interface.
        </p>

        <div className="mt-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {dark ? (
              <Moon className="h-5 w-5 text-gray-500 dark:text-gray-400" />
            ) : (
              <Sun className="h-5 w-5 text-gray-500" />
            )}
            <span className="text-sm text-gray-700 dark:text-gray-300">
              {dark ? 'Dark mode' : 'Light mode'}
            </span>
          </div>

          <button
            onClick={toggle}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 ${
              dark ? 'bg-navy-700' : 'bg-gray-300'
            }`}
            aria-label="Toggle dark mode"
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 ${
                dark ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>
      </div>

      {/* API Configuration (placeholder) */}
      <div className="mt-6 rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-surface-dark">
        <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">
          API Configuration
        </h3>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Backend API settings for the LIT system.
        </p>

        <div className="mt-4">
          <label
            htmlFor="api-url"
            className="block text-sm font-medium text-gray-700 dark:text-gray-300"
          >
            API Base URL
          </label>
          <input
            id="api-url"
            type="text"
            defaultValue="/api"
            className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 transition-colors focus:border-navy-700 focus:outline-none focus:ring-1 focus:ring-navy-700 dark:border-gray-700 dark:bg-surface-dark dark:text-gray-100"
          />
          <p className="mt-2 text-xs text-gray-400 dark:text-gray-500">
            The backend must be running on the same origin or a proxied route.
          </p>
        </div>
      </div>
    </div>
  )
}
