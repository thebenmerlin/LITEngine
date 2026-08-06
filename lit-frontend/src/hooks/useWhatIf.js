import { useContext } from 'react'
import WhatIfContext from '../context/WhatIfContext'

export function useWhatIf() {
  const ctx = useContext(WhatIfContext)
  if (!ctx) {
    throw new Error('useWhatIf must be used within a WhatIfProvider')
  }
  return ctx
}
