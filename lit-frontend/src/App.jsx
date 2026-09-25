import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { ThemeProvider } from './context/ThemeContext'
import { SidebarProvider } from './context/SidebarContext'
import { SettingsProvider } from './hooks/useSettings.jsx'
import { WorkspaceProvider } from './workspace/WorkspaceContext'
import Layout from './components/layout/Layout'
import Home from './pages/Home'
import FactExtraction from './pages/FactExtraction'
import PrecedentSearch from './pages/PrecedentSearch'
import ArgumentGraph from './pages/ArgumentGraph'
import Simulation from './pages/Simulation'
import WhatIf from './pages/WhatIf'
import Settings from './pages/Settings'
import './styles/globals.css'

export default function App() {
  return (
    <ThemeProvider>
      <SidebarProvider>
        <SettingsProvider>
          <WorkspaceProvider>
            <BrowserRouter>
              <Routes>
                <Route element={<Layout />}>
                  <Route path="/" element={<Home />} />
                  <Route path="/fact-extraction" element={<FactExtraction />} />
                  <Route path="/precedent-search" element={<PrecedentSearch />} />
                  <Route path="/argument-graph" element={<ArgumentGraph />} />
                  <Route path="/simulation" element={<Simulation />} />
                  <Route path="/what-if" element={<WhatIf />} />
                  <Route path="/settings" element={<Settings />} />
                </Route>
              </Routes>
            </BrowserRouter>
          </WorkspaceProvider>
        </SettingsProvider>
      </SidebarProvider>
    </ThemeProvider>
  )
}
