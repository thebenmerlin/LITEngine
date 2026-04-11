import EmptyState from '../components/ui/EmptyState'
import { GitBranch } from 'lucide-react'

export default function ArgumentGraph() {
  return (
    <EmptyState
      title="Argument Graph"
      message="Interactive visualization of legal relationships — coming soon"
      icon={GitBranch}
    />
  )
}
