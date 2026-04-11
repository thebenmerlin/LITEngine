import { ExternalLink, ChevronDown, ChevronUp, Scale } from 'lucide-react'
import { useState } from 'react'
import Badge from './ui/Badge'
import Button from './ui/Button'

/**
 * Extract a rough IPC section list from a snippet or metadata.
 * The backend returns `ipc_sections` inside each result's metadata
 * when indexed; when results come from Kanoon fallback the field
 * may be missing. We do a lightweight heuristic parse.
 */
function extractSectionsFromSnippet(snippet) {
  if (!snippet) return []
  const re = /Section\s+(\d+[A-Z]?(?:\s*(?:IPC|CrPC|CPC))?)?/gi
  const found = new Set()
  let m
  while ((m = re.exec(snippet)) !== null) {
    const val = m[0].trim()
    if (val.length > 6) found.add(val)
  }
  return Array.from(found)
}

/**
 * Map a similarity score (0–1) to a Badge variant.
 *
 *   > 0.80  → green
 *   0.60–0.80 → yellow (amber)
 *   < 0.60  → gray (default)
 */
function scoreVariant(score) {
  if (score == null) return 'default'
  if (score > 0.8) return 'green'
  if (score > 0.6) return 'yellow'
  return 'default'
}

function scoreLabel(score) {
  if (score == null) return '—'
  return `${Math.round(score * 100)}%`
}

export default function PrecedentCard({ result }) {
  const [expanded, setExpanded] = useState(false)

  const {
    title,
    url,
    doc_id,
    court,
    date,
    snippet,
    similarity_score,
    source,
    ipc_sections,
  } = result

  const sections =
    ipc_sections && ipc_sections.length > 0
      ? ipc_sections
      : extractSectionsFromSnippet(snippet)

  const displaySnippet = snippet || 'No excerpt available for this result.'
  const needsExpand = displaySnippet.length > 200
  const visibleText =
    needsExpand && !expanded
      ? displaySnippet.slice(0, 200).replace(/\s\S*$/, '') + '…'
      : displaySnippet

  return (
    <article className="group rounded-lg border border-gray-200 bg-white p-5 transition-colors duration-150 hover:bg-gray-50/60 dark:border-gray-800 dark:bg-surface-dark dark:hover:bg-gray-900/50">
      {/* Title row */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <a
            href={url || `https://indiankanoon.org/doc/${doc_id}/`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-base font-semibold text-gray-900 transition-colors hover:text-navy-700 dark:text-gray-100 dark:hover:text-navy-300"
          >
            {title}
          </a>

          {/* Court + date */}
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-gray-500 dark:text-gray-400">
            {court && (
              <span className="flex items-center gap-1">
                <Scale className="h-3.5 w-3.5" />
                {court}
              </span>
            )}
            {date && <span>{date}</span>}
            {source && (
              <Badge
                variant={source === 'faiss' ? 'navy' : 'default'}
                className="text-[10px]"
              >
                {source}
              </Badge>
            )}
          </div>
        </div>

        {/* Similarity badge */}
        {similarity_score != null && (
          <Badge variant={scoreVariant(similarity_score)}>
            {scoreLabel(similarity_score)}
          </Badge>
        )}
      </div>

      {/* Snippet */}
      <p className="mt-3 text-sm leading-relaxed text-gray-600 dark:text-gray-400">
        {visibleText}
      </p>
      {needsExpand && (
        <button
          onClick={() => setExpanded((p) => !p)}
          className="mt-1 flex items-center gap-1 text-xs font-medium text-navy-700 hover:underline dark:text-navy-300"
        >
          {expanded ? (
            <>
              Show less
              <ChevronUp className="h-3.5 w-3.5" />
            </>
          ) : (
            <>
              Show more
              <ChevronDown className="h-3.5 w-3.5" />
            </>
          )}
        </button>
      )}

      {/* IPC section badges */}
      {sections.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {sections.map((s) => (
            <span
              key={s}
              className="rounded-md bg-gray-100 px-2 py-0.5 text-[11px] text-gray-500 dark:bg-gray-800 dark:text-gray-400"
            >
              {s}
            </span>
          ))}
        </div>
      )}

      {/* Action row */}
      <div className="mt-4 flex items-center justify-end">
        <a
          href={url || '#'}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200"
        >
          View Judgment
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      </div>
    </article>
  )
}
