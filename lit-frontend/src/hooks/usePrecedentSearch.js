import { useContext } from 'react'
import PrecedentSearchContext from '../context/PrecedentSearchContext'

export function usePrecedentSearch() {
  const ctx = useContext(PrecedentSearchContext)
  if (!ctx) {
    throw new Error('usePrecedentSearch must be used within a PrecedentSearchProvider')
  }
  return ctx
}
