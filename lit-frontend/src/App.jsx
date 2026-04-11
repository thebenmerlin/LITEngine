import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from './context/ThemeContext'
import Layout from './components/layout/Layout'
import Home from './pages/Home'
import PrecedentSearch from './pages/PrecedentSearch'
import FactExtraction from './pages/FactExtraction'
import ArgumentGraph from './pages/ArgumentGraph'
import Simulation from './pages/Simulation'
import Settings from './pages/Settings'
import './styles/globals.css'

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Home />} />
            <Route path="/precedent-search" element={<PrecedentSearch />} />
            <Route path="/fact-extraction" element={<FactExtraction />} />
            <Route path="/argument-graph" element={<ArgumentGraph />} />
            <Route path="/simulation" element={<Simulation />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  )
}
