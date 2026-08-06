import { useContext } from 'react'
import ArgumentGraphContext from '../context/ArgumentGraphContext'

export function useArgumentGraph() {
  const ctx = useContext(ArgumentGraphContext)
  if (!ctx) {
    throw new Error('useArgumentGraph must be used within an ArgumentGraphProvider')
  }
  return ctx
}
