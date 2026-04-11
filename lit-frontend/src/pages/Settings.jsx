import { useState, useCallback } from 'react'
import { useSettings } from '../hooks/useSettings'
import { checkHealth, ApiError } from '../lib/api'
import { CheckCircle2, XCircle, Loader2, RotateCcw } from 'lucide-react'
import Button from '../components/ui/Button'

/* ------------------------------------------------------------------ */
/*  Section separator                                                  */
/* ------------------------------------------------------------------ */

function SectionSeparator() {
  return <div className="my-6 h-px bg-gray-200 dark:bg-gray-800" />
}

function SectionLabel({ children }) {
  return (
    <span className="mb-4 block text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
      {children}
    </span>
  )
}

/* ------------------------------------------------------------------ */
/*  Theme pill buttons                                                 */
/* ------------------------------------------------------------------ */

function ThemePills({ value, onChange }) {
  const options = [
    { label: 'Light', value: 'light' },
    { label: 'Dark', value: 'dark' },
    { label: 'System', value: 'system' },
  ]

  return (
    <div className="flex gap-2">
      {options.map(({ label, val }) => {
        const active = value === val
        return (
          <button
            key={val}
            onClick={() => onChange(val)}
            className={`rounded-full border px-5 py-2 text-sm font-medium transition-colors duration-150 ${
              active
                ? 'border-navy-700 bg-navy-700/5 text-navy-700 dark:border-navy-400 dark:bg-navy-700/20 dark:text-navy-200'
                : 'border-gray-300 bg-white text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:bg-surface-dark dark:text-gray-400 dark:hover:bg-gray-800'
            }`}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Toggle switch                                                      */
/* ------------------------------------------------------------------ */

function ToggleSwitch({ checked, onChange, id }) {
  return (
    <button
      id={id}
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200 ${
        checked ? 'bg-navy-700' : 'bg-gray-300 dark:bg-gray-700'
      }`}
    >
      <span
        className={`absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200 ${
          checked ? 'translate-x-4' : 'translate-x-0'
        }`}
      />
    </button>
  )
}

/* ------------------------------------------------------------------ */
/*  Settings page                                                      */
/* ------------------------------------------------------------------ */

export default function Settings() {
  const { settings, updateSetting, resetSettings } = useSettings()

  // API connection test
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null) // { ok, message }

  const handleTestConnection = useCallback(async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const res = await checkHealth()
      setTestResult({
        ok: true,
        message: `Connected — ${res.app} v${res.version}`,
      })
    } catch (err) {
      setTestResult({
        ok: false,
        message: err instanceof ApiError ? err.detail || err.message : 'Unreachable — check your backend URL',
      })
    } finally {
      setTesting(false)
    }
  }, [])

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h2 className="text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-100">
          Settings
        </h2>
        <p className="mt-1.5 text-sm text-gray-500 dark:text-gray-400">
          Manage your preferences and system configuration
        </p>
      </div>

      <div className="max-w-2xl">
        {/* ── Appearance ─────────────────────────────────────────── */}
        <SectionLabel>Appearance</SectionLabel>

        <div className="space-y-2">
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Theme
          </span>
          <ThemePills
            value={settings.theme}
            onChange={(v) => updateSetting('theme', v)}
          />
        </div>

        <SectionSeparator />

        {/* ── API Configuration ──────────────────────────────────── */}
        <SectionLabel>API Configuration</SectionLabel>

        <div className="space-y-3">
          <div>
            <label
              htmlFor="api-url"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              Backend URL
            </label>
            <input
              id="api-url"
              type="text"
              value={settings.apiBaseUrl}
              onChange={(e) => updateSetting('apiBaseUrl', e.target.value)}
              placeholder="Leave empty to use default"
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 transition-colors placeholder:text-gray-400 focus:border-navy-700 focus:outline-none focus:ring-1 focus:ring-navy-700 dark:border-gray-700 dark:bg-[#161B27] dark:text-gray-100 dark:placeholder:text-gray-500"
            />
          </div>

          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={handleTestConnection}
              disabled={testing}
              className="gap-2"
            >
              {testing ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Testing…
                </>
              ) : (
                'Test Connection'
              )}
            </Button>

            {testResult && (
              <span
                className={`flex items-center gap-1.5 text-sm font-medium ${
                  testResult.ok
                    ? 'text-green-600 dark:text-green-400'
                    : 'text-red-600 dark:text-red-400'
                }`}
              >
                {testResult.ok ? (
                  <CheckCircle2 className="h-4 w-4" />
                ) : (
                  <XCircle className="h-4 w-4" />
                )}
                {testResult.message}
              </span>
            )}
          </div>
        </div>

        <SectionSeparator />

        {/* ── Search Defaults ────────────────────────────────────── */}
        <SectionLabel>Search Defaults</SectionLabel>

        <div className="space-y-4">
          <div>
            <label
              htmlFor="result-count"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              Default Result Count
            </label>
            <select
              id="result-count"
              value={settings.defaultResultCount}
              onChange={(e) => updateSetting('defaultResultCount', Number(e.target.value))}
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 transition-colors focus:border-navy-700 focus:outline-none focus:ring-1 focus:ring-navy-700 dark:border-gray-700 dark:bg-[#161B27] dark:text-gray-100"
            >
              {[3, 5, 10].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <label
                htmlFor="include-kanoon"
                className="text-sm font-medium text-gray-700 dark:text-gray-300"
              >
                Include Live Kanoon Results
              </label>
            </div>
            <ToggleSwitch
              id="include-kanoon"
              checked={settings.includeKanoon}
              onChange={(v) => updateSetting('includeKanoon', v)}
            />
          </div>
        </div>

        <SectionSeparator />

        {/* ── Extraction Defaults ────────────────────────────────── */}
        <SectionLabel>Extraction Defaults</SectionLabel>

        <div className="flex items-center justify-between">
          <div>
            <label
              htmlFor="use-ai-model"
              className="text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              Use AI Model by Default
            </label>
            <p className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">
              Uses InLegalBERT via Hugging Face Inference API
            </p>
          </div>
          <ToggleSwitch
            id="use-ai-model"
            checked={settings.useAiModel}
            onChange={(v) => updateSetting('useAiModel', v)}
          />
        </div>

        <SectionSeparator />

        {/* ── About ──────────────────────────────────────────────── */}
        <SectionLabel>About</SectionLabel>

        <dl className="space-y-2 text-sm">
          <div className="flex justify-between">
            <dt className="text-gray-500 dark:text-gray-400">Product</dt>
            <dd className="font-medium text-gray-900 dark:text-gray-100">
              Legal Intelligence Terminal
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-gray-500 dark:text-gray-400">Version</dt>
            <dd className="font-medium text-gray-900 dark:text-gray-100">
              1.0.0
            </dd>
          </div>
          <div>
            <dt className="text-gray-500 dark:text-gray-400">Built for</dt>
            <dd className="mt-0.5 font-medium text-gray-900 dark:text-gray-100">
              Final Year Project — JSPM's Rajarshi Shahu College of Engineering, Pune
            </dd>
          </div>
          <div>
            <dt className="text-gray-500 dark:text-gray-400">Stack</dt>
            <dd className="mt-0.5 text-gray-900 dark:text-gray-100">
              FastAPI · Sentence-BERT · InLegalBERT · FAISS · React · Cytoscape.js
            </dd>
          </div>
        </dl>

        <SectionSeparator />

        {/* ── Reset ──────────────────────────────────────────────── */}
        <div className="flex justify-end">
          <Button
            variant="ghost"
            size="sm"
            className="gap-2 text-gray-500 dark:text-gray-400"
            onClick={resetSettings}
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Reset to defaults
          </Button>
        </div>
      </div>
    </div>
  )
}
