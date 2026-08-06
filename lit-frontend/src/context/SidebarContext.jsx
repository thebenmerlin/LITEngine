import { createContext, useCallback, useEffect, useState } from 'react'

const SidebarContext = createContext({
  collapsed: false,
  toggle: () => {},
})

const STORAGE_KEY = 'lit-sidebar-collapsed'

export function SidebarProvider({ children }) {
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === 'undefined') return false
    return localStorage.getItem(STORAGE_KEY) === 'true'
  })

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, collapsed ? 'true' : 'false')
  }, [collapsed])

  const toggle = useCallback(() => setCollapsed((prev) => !prev), [])

  return (
    <SidebarContext.Provider value={{ collapsed, toggle }}>
      {children}
    </SidebarContext.Provider>
  )
}

export default SidebarContext
