import EmptyState from '../components/ui/EmptyState'
import { Brain } from 'lucide-react'

export default function Simulation() {
  return (
    <EmptyState
      title="Judicial Simulation"
      message="AI-powered case outcome simulation — coming soon"
      icon={Brain}
    />
  )
}
