import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from './context/ThemeContext'
import { SettingsProvider } from './hooks/useSettings.jsx'
import Layout from './components/layout/Layout'
import OfflineBanner from './components/ui/OfflineBanner'
import LoadingScreen from './components/ui/LoadingScreen'
import Home from './pages/Home'
import PrecedentSearch from './pages/PrecedentSearch'
import FactExtraction from './pages/FactExtraction'
import ArgumentGraph from './pages/ArgumentGraph'
import Simulation from './pages/Simulation'
import WhatIf from './pages/WhatIf'
import Settings from './pages/Settings'
import { checkHealth } from './lib/api'
import './styles/globals.css'

function AppRoutes() {
  return (
    <>
      <OfflineBanner />
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Home />} />
            <Route path="/precedent-search" element={<PrecedentSearch />} />
            <Route path="/fact-extraction" element={<FactExtraction />} />
            <Route path="/argument-graph" element={<ArgumentGraph />} />
            <Route path="/simulation" element={<Simulation />} />
            <Route path="/what-if" element={<WhatIf />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </>
  )
}

export default function App() {
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let cancelled = false
    checkHealth()
      .catch(() => {
        // Health check failed — app still loads, OfflineBanner will show
      })
      .finally(() => {
        if (!cancelled) setReady(true)
      })
    return () => { cancelled = true }
  }, [])

  return (
    <ThemeProvider>
      <SettingsProvider>
        {!ready && <LoadingScreen onDone={() => setReady(true)} />}
        <AppRoutes />
      </SettingsProvider>
    </ThemeProvider>
  )
}