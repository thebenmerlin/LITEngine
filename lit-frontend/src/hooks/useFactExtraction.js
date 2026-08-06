import { useContext } from 'react'
import FactExtractionContext from '../context/FactExtractionContext'

export function useFactExtraction() {
  const ctx = useContext(FactExtractionContext)
  if (!ctx) {
    throw new Error('useFactExtraction must be used within a FactExtractionProvider')
  }
  return ctx
}
