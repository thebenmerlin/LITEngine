import { useState, useRef, useEffect } from 'react'
import {
  Download,
  Loader2,
  Sparkles,
  Gavel,
  Tag,
  ListChecks,
  Scale,
  FileText,
  ArrowUpRight,
} from 'lucide-react'
import { useApi } from '../hooks/useApi'
import { extractFacts, ApiError } from '../lib/api'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import ErrorBanner from '../components/ui/ErrorBanner'
import Spinner from '../components/ui/Spinner'

/* ------------------------------------------------------------------ */
/*  Section label — small uppercase gray                              */
/* ------------------------------------------------------------------ */

function SectionLabel({ icon: Icon, children }) {
  return (
    <div className="mb-3 flex items-center gap-2">
      <span className="flex h-6 w-6 items-center justify-center rounded bg-gray-100 dark:bg-gray-800">
        <Icon className="h-3.5 w-3.5 text-gray-500 dark:text-gray-400" />
      </span>
      <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
        {children}
      </span>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Thin horizontal rule between sections                             */
/* ------------------------------------------------------------------ */

function SectionDivider() {
  return <div className="my-5 h-px bg-gray-200 dark:bg-gray-800" />
}

/* ------------------------------------------------------------------ */
/*  Output panel — renders StructuredCaseProfile                      */
/* ------------------------------------------------------------------ */

function OutputPanel({ profile, onExport }) {
  const {
    parties,
    case_type,
    court_level,
    legal_issues,
    ipc_sections,
    acts_referenced,
    key_facts,
    relief_sought,
    metadata,
  } = profile

  const hasContent =
    (parties && (parties.petitioner || parties.respondent)) ||
    legal_issues?.length ||
    ipc_sections?.length ||
    acts_referenced?.length ||
    key_facts?.length ||
    relief_sought

  if (!hasContent) {
    return (
      <div className="py-10 text-center text-sm text-gray-400 dark:text-gray-500">
        No structured elements could be extracted from this text.
      </div>
    )
  }

  return (
    <div className="text-sm leading-relaxed text-gray-800 dark:text-gray-300">
      {/* ── Parties ─────────────────────────────── */}
      {(parties?.petitioner || parties?.respondent) && (
        <>
          <SectionLabel icon={Gavel}>Parties</SectionLabel>
          <div className="flex flex-col gap-2 sm:flex-row sm:gap-8">
            {parties.petitioner && (
              <div>
                <span className="text-xs text-gray-400 dark:text-gray-500">
                  Petitioner
                </span>
                <p className="font-medium text-gray-900 dark:text-gray-100">
                  {parties.petitioner}
                </p>
              </div>
            )}
            {parties.respondent && (
              <div>
                <span className="text-xs text-gray-400 dark:text-gray-500">
                  Respondent
                </span>
                <p className="font-medium text-gray-900 dark:text-gray-100">
                  {parties.respondent}
                </p>
              </div>
            )}
          </div>
          <SectionDivider />
        </>
      )}

      {/* ── Case Classification ─────────────────── */}
      {(case_type || court_level) && (
        <>
          <SectionLabel icon={Tag}>Case Classification</SectionLabel>
          <div className="flex flex-wrap gap-2">
            {case_type && (
              <Badge variant="navy">{case_type}</Badge>
            )}
            {court_level && (
              <Badge variant="default">
                <Scale className="mr-1 h-3 w-3" />
                {court_level}
              </Badge>
            )}
          </div>
          <SectionDivider />
        </>
      )}

      {/* ── Legal Issues ────────────────────────── */}
      {legal_issues?.length > 0 && (
        <>
          <SectionLabel icon={ListChecks}>Legal Issues</SectionLabel>
          <ul className="list-none space-y-2">
            {legal_issues.map((issue, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-gray-400 dark:bg-gray-500" />
                <span className="text-gray-700 dark:text-gray-300">{issue}</span>
              </li>
            ))}
          </ul>
          <SectionDivider />
        </>
      )}

      {/* ── IPC / Statute References ────────────── */}
      {ipc_sections?.length > 0 && (
        <>
          <SectionLabel icon={FileText}>IPC / Statute References</SectionLabel>
          <div className="flex flex-wrap gap-1.5">
            {ipc_sections.map((sec) => (
              <a
                key={sec}
                href={`https://indiankanoon.org/search/?formInput=${encodeURIComponent(sec)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 rounded-md bg-navy-700/10 px-2.5 py-1 text-[12px] font-medium text-navy-700 transition-colors hover:bg-navy-700/20 dark:bg-navy-700/25 dark:text-navy-200 dark:hover:bg-navy-700/40"
              >
                {sec}
                <ArrowUpRight className="h-3 w-3" />
              </a>
            ))}
          </div>
          <SectionDivider />
        </>
      )}

      {/* ── Acts Referenced ─────────────────────── */}
      {acts_referenced?.length > 0 && (
        <>
          <SectionLabel icon={FileText}>Acts Referenced</SectionLabel>
          <ul className="list-none space-y-1">
            {acts_referenced.map((act) => (
              <li
                key={act}
                className="flex items-start gap-2 text-gray-700 dark:text-gray-300"
              >
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-gray-400 dark:bg-gray-500" />
                {act}
              </li>
            ))}
          </ul>
          <SectionDivider />
        </>
      )}

      {/* ── Key Facts ───────────────────────────── */}
      {key_facts?.length > 0 && (
        <>
          <SectionLabel icon={ListChecks}>Key Facts</SectionLabel>
          <ol className="list-none space-y-2">
            {key_facts.map((fact, i) => (
              <li key={i} className="flex gap-2">
                <span className="shrink-0 font-mono text-xs text-gray-400 dark:text-gray-500">
                  {i + 1}.
                </span>
                <span className="text-gray-700 dark:text-gray-300">{fact}</span>
              </li>
            ))}
          </ol>
          <SectionDivider />
        </>
      )}

      {/* ── Relief Sought ───────────────────────── */}
      {relief_sought && (
        <>
          <SectionLabel icon={Scale}>Relief Sought</SectionLabel>
          <p className="text-gray-700 dark:text-gray-300">{relief_sought}</p>
          <SectionDivider />
        </>
      )}

      {/* ── Extraction Metadata ─────────────────── */}
      {metadata && (
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 pt-1 text-xs text-gray-400 dark:text-gray-500">
          <span>
            Method:{' '}
            <span className="font-medium text-gray-600 dark:text-gray-300">
              {metadata.extraction_method}
            </span>
          </span>
          <span>
            Confidence:{' '}
            <span className="font-medium text-gray-600 dark:text-gray-300">
              {Math.round(metadata.confidence * 100)}%
            </span>
          </span>
          <span>
            Time:{' '}
            <span className="font-medium text-gray-600 dark:text-gray-300">
              {(metadata.processing_time_ms / 1000).toFixed(1)}s
            </span>
          </span>
        </div>
      )}

      {/* ── Export ──────────────────────────────── */}
      <div className="mt-6 flex justify-end">
        <Button
          variant="outline"
          size="sm"
          className="gap-2"
          onClick={onExport}
        >
          <Download className="h-4 w-4" />
          Export as JSON
        </Button>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  FactExtraction page                                               */
/* ------------------------------------------------------------------ */

export default function FactExtraction() {
  const [caseText, setCaseText] = useState('')
  const [useModel, setUseModel] = useState(true)

  const {
    data: profile,
    loading,
    error,
    execute,
  } = useApi(extractFacts)

  // ---- warming-up timer ---------------------------------------
  // useApi handles the 202 polling internally. We show an elapsed
  // seconds counter while loading is true — if the model was cold
  // the user sees the warming state; if it was warm it flashes away.
  const [elapsed, setElapsed] = useState(0)
  const timerRef = useRef(null)

  useEffect(() => {
    if (loading) {
      setElapsed(0)
      timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000)
    } else {
      clearInterval(timerRef.current)
    }
    return () => clearInterval(timerRef.current)
  }, [loading])

  const handleExtract = () => {
    if (!caseText.trim()) return
    execute({ caseText: caseText.trim(), useModel })
  }

  const handleExport = () => {
    if (!profile) return
    const blob = new Blob([JSON.stringify(profile, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `case-profile-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const hasExtracted = profile !== null || error !== null

  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-100">
          Fact Extraction
        </h2>
        <p className="mt-1.5 text-sm text-gray-500 dark:text-gray-400">
          Paste a case description to extract structured legal elements
        </p>
      </div>

      {/* Two-panel layout */}
      <div className="flex flex-col gap-8 lg:flex-row lg:gap-10">
        {/* ── LEFT: Input panel (40%) ──────────────────────── */}
        <div className="w-full lg:w-[40%]">
          <textarea
            value={caseText}
            onChange={(e) => setCaseText(e.target.value)}
            placeholder="Paste the case description, FIR text, or complaint here..."
            className="block w-full resize-y rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm leading-relaxed text-gray-900 placeholder:text-gray-400 focus:border-navy-700 focus:outline-none focus:ring-1 focus:ring-navy-700 dark:border-gray-700 dark:bg-surface-dark dark:text-gray-100 dark:placeholder:text-gray-500 dark:focus:border-navy-500 dark:focus:ring-navy-500"
            style={{ minHeight: 300 }}
          />

          {/* Toggle */}
          <label className="mt-4 flex cursor-pointer items-center gap-3 text-sm text-gray-600 dark:text-gray-400">
            <span className="relative inline-flex h-5 w-9 shrink-0">
              <input
                type="checkbox"
                checked={useModel}
                onChange={(e) => setUseModel(e.target.checked)}
                className="peer sr-only"
              />
              <span className="absolute inset-0 rounded-full bg-gray-300 transition-colors duration-200 peer-checked:bg-navy-700 dark:bg-gray-700" />
              <span className="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200 peer-checked:translate-x-4" />
            </span>
            <span className="flex items-center gap-1.5">
              <Sparkles className="h-3.5 w-3.5 text-navy-700 dark:text-navy-300" />
              Extract using InLegalBERT
            </span>
          </label>

          {/* Extract button */}
          <Button
            onClick={handleExtract}
            variant="primary"
            className="mt-5 w-full gap-2"
            disabled={loading || !caseText.trim()}
          >
            {loading ? (
              <>
                <Spinner size="sm" />
                Extracting…
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Extract
              </>
            )}
          </Button>
        </div>

        {/* ── RIGHT: Output panel (60%) ────────────────────── */}
        <div className="w-full lg:w-[60%]">
          {/* Loading */}
          {loading && (
            <div className="flex flex-col items-center justify-center rounded-lg border border-gray-200 bg-white px-6 py-16 dark:border-gray-800 dark:bg-surface-dark">
              <Loader2 className="mb-3 h-6 w-6 animate-spin text-navy-700 dark:text-navy-300" />
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                {elapsed > 5
                  ? 'Model is warming up, please wait…'
                  : 'Extracting…'}
              </p>
              <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                Elapsed: {elapsed}s
              </p>
            </div>
          )}

          {/* Error */}
          {!loading && error && (
            <ErrorBanner
              message={
                error instanceof ApiError
                  ? error.detail || error.message
                  : error.message
              }
            />
          )}

          {/* Empty — nothing extracted yet */}
          {!loading && !hasExtracted && (
            <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-gray-300 text-sm text-gray-400 dark:border-gray-700 dark:text-gray-500">
              Extracted case profile will appear here
            </div>
          )}

          {/* Profile */}
          {!loading && profile && (
            <OutputPanel profile={profile} onExport={handleExport} />
          )}
        </div>
      </div>
    </div>
  )
}
