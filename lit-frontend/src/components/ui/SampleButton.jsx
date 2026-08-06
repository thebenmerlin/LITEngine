import { Wand2 } from 'lucide-react'

/**
 * "Load sample" affordance placed beside a primary action button so a demo
 * can populate realistic case input in one click.
 */
export default function SampleButton({ onClick, label = 'Try sample', className = '' }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex h-10 shrink-0 items-center justify-center gap-1.5 rounded-md border border-dashed border-navy-700/40 bg-navy-700/5 px-3 text-sm font-medium text-navy-700 transition-colors duration-150 hover:border-navy-700 hover:bg-navy-700/10 dark:border-navy-400/40 dark:bg-navy-700/10 dark:text-navy-200 dark:hover:border-navy-400 dark:hover:bg-navy-700/25 ${className}`}
    >
      <Wand2 className="h-4 w-4" />
      {label}
    </button>
  )
}
