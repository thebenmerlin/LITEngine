import { useContext } from 'react'
import SimulationContext from '../context/SimulationContext'

export function useSimulation() {
  const ctx = useContext(SimulationContext)
  if (!ctx) {
    throw new Error('useSimulation must be used within a SimulationProvider')
  }
  return ctx
}
