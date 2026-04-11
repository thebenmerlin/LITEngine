import { createContext, useCallback, useContext, useEffect, useState } from 'react'

const STORAGE_KEY = 'lit-settings'

const DEFAULTS = {
  theme: 'light',            // 'light' | 'dark' | 'system'
  apiBaseUrl: '',            // empty = use env default
  defaultResultCount: 5,     // 3 | 5 | 10
  includeKanoon: true,
  useAiModel: true,
}

function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULTS }
    const parsed = JSON.parse(raw)
    return { ...DEFAULTS, ...parsed }
  } catch {
    return { ...DEFAULTS }
  }
}

function saveSettings(s) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(s))
}

const SettingsContext = createContext(null)

export function SettingsProvider({ children }) {
  const [settings, setSettings] = useState(loadSettings)

  // Persist on every change
  useEffect(() => { saveSettings(settings) }, [settings])

  // Apply theme immediately when it changes
  useEffect(() => {
    const root = document.documentElement
    let isDark

    if (settings.theme === 'system') {
      isDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    } else {
      isDark = settings.theme === 'dark'
    }

    if (isDark) {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
    // Also persist theme for ThemeContext compatibility
    localStorage.setItem('lit-theme', isDark ? 'dark' : 'light')
  }, [settings.theme])

  // Listen for system theme changes when in "system" mode
  useEffect(() => {
    if (settings.theme !== 'system') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => {
      const root = document.documentElement
      if (mq.matches) {
        root.classList.add('dark')
        localStorage.setItem('lit-theme', 'dark')
      } else {
        root.classList.remove('dark')
        localStorage.setItem('lit-theme', 'light')
      }
    }
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [settings.theme])

  const updateSetting = useCallback((key, value) => {
    setSettings((prev) => ({ ...prev, [key]: value }))
  }, [])

  const resetSettings = useCallback(() => {
    setSettings({ ...DEFAULTS })
  }, [])

  return (
    <SettingsContext.Provider value={{ settings, updateSetting, resetSettings }}>
      {children}
    </SettingsContext.Provider>
  )
}

export function useSettings() {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error('useSettings must be used within a SettingsProvider')
  return ctx
}
