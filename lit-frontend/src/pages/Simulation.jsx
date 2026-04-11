import { useState, useCallback } from 'react'
import { Brain, Download, Printer, Loader2, CheckCircle2, AlertTriangle } from 'lucide-react'
import { extractFacts, searchPrecedents, runSimulation, ApiError } from '../lib/api'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import ErrorBanner from '../components/ui/ErrorBanner'
import SimulationGauge from '../components/SimulationGauge'

/* ------------------------------------------------------------------ */
/*  Stepped progress indicator                                         */
/* ------------------------------------------------------------------ */

const STEPS = [
  { label: 'Extracting facts…' },
  { label: 'Searching precedents…' },
  { label: 'Running simulation…' },
]

function SteppedProgress({ currentStep }) {
  return (
    <div className="flex items-center gap-3 py-6">
      {STEPS.map((step, i) => {
        const done = i < currentStep
        const active = i === currentStep
        return (
          <div key={i} className="flex items-center gap-3">
            <div
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-colors ${
                done
                  ? 'bg-navy-700 text-white'
                  : active
                    ? 'bg-navy-700/20 text-navy-700 dark:bg-navy-700/30 dark:text-navy-300'
                    : 'bg-gray-200 text-gray-400 dark:bg-gray-700 dark:text-gray-500'
              }`}
            >
              {done ? (
                <CheckCircle2 className="h-4 w-4" />
              ) : (
                i + 1
              )}
            </div>
            <span
              className={`whitespace-nowrap text-sm ${
                active
                  ? 'font-medium text-gray-900 dark:text-gray-100'
                  : done
                    ? 'text-gray-600 dark:text-gray-400'
                    : 'text-gray-400 dark:text-gray-500'
              }`}
            >
              {step.label}
            </span>
            {i < STEPS.length - 1 && (
              <div
                className={`h-px w-6 ${
                  i < currentStep ? 'bg-navy-700' : 'bg-gray-200 dark:bg-gray-700'
                }`}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Score bar                                                          */
/* ------------------------------------------------------------------ */

function ScoreBar({ component, weight, weightedScore, explanation }) {
  const pct = Math.round((weightedScore ?? 0) * 100)
  return (
    <div className="py-3">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-gray-900 dark:text-gray-100">
          {component}
        </span>
        <span className="text-xs text-gray-400 dark:text-gray-500">
          w={weight * 100}%
        </span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
        <div
          className="h-full rounded-full bg-navy-700 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
        {explanation}
      </p>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Section separator                                                  */
/* ------------------------------------------------------------------ */

function SectionSeparator({ children }) {
  return (
    <div className="mt-6 pt-5">
      <div className="mb-3 h-px bg-gray-200 dark:bg-gray-800" />
      <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
        {children}
      </span>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Skeleton                                                           */
/* ------------------------------------------------------------------ */

function ResultsSkeleton() {
  const bar = (w) => (
    <div className={`h-4 ${w} animate-pulse rounded bg-gray-200 dark:bg-gray-700`} />
  )
  return (
    <div className="space-y-6">
      <div className="flex justify-center">{bar('w-36')}</div>
      {bar('w-1/4')}
      {bar('w-3/4')}
      <div className="space-y-4">
        {bar('w-1/3')}
        {bar('w-full')}
        {bar('w-2/3')}
      </div>
      <div className="space-y-4">
        {bar('w-1/4')}
        {bar('w-5/6')}
        {bar('w-4/6')}
      </div>
      <div className="space-y-2">
        {bar('w-3/4')}
        {bar('w-5/6')}
        {bar('w-4/6')}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Empty state                                                        */
/* ------------------------------------------------------------------ */

function SimulationEmpty() {
  return (
    <div className="flex h-80 flex-col items-center justify-center rounded-lg border border-dashed border-gray-300 dark:border-gray-700">
      <Brain className="mb-3 h-10 w-10 text-gray-300 dark:text-gray-600" />
      <p className="text-sm text-gray-400 dark:text-gray-500">
        Run a simulation to see outcome prediction
      </p>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Simulation page                                                    */
/* ------------------------------------------------------------------ */

export default function Simulation() {
  const [caseText, setCaseText] = useState('')
  const [simResult, setSimResult] = useState(null)
  const [error, setError] = useState(null)
  const [running, setRunning] = useState(false)
  const [progressStep, setProgressStep] = useState(0)

  const handleRun = useCallback(async () => {
    if (!caseText.trim()) return
    setRunning(true)
    setError(null)
    setSimResult(null)
    setProgressStep(0)

    try {
      // Step 1: Extract facts
      setProgressStep(0)
      const profile = await extractFacts({ caseText: caseText.trim(), useModel: true })

      // Step 2: Search precedents
      setProgressStep(1)
      const query = profile.legal_issues
        ? profile.legal_issues.join(' ')
        : caseText.trim()
      let precedents = []
      try {
        const searchRes = await searchPrecedents({ query, topK: 5, useKanoon: true })
        precedents = searchRes.results || []
      } catch {
        // Non-fatal — simulation can run without precedents
        precedents = []
      }

      // Step 3: Run simulation
      setProgressStep(2)
      const simRes = await runSimulation({
        caseProfile: profile,
        precedents: precedents.slice(0, 5),
        graphStats: null,
      })

      setSimResult(simRes.result)
    } catch (err) {
      setError(
        err instanceof ApiError ? err.detail || err.message : err.message,
      )
    } finally {
      setRunning(false)
    }
  }, [caseText])

  const handleExportJSON = useCallback(() => {
    if (!simResult) return
    const blob = new Blob([JSON.stringify(simResult, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `simulation-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }, [simResult])

  const handleExportPDF = useCallback(() => {
    window.print()
  }, [])

  if (!simResult && !running) {
    return (
      <div>
        <div className="mb-8">
          <h2 className="text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-100">
            Judicial Simulation
          </h2>
          <p className="mt-1.5 text-sm text-gray-500 dark:text-gray-400">
            Estimate the probable outcome of your case based on precedents
            and argument strength
          </p>
        </div>

        <div className="flex flex-col gap-8 lg:flex-row lg:gap-10">
          {/* Left panel */}
          <div className="w-full lg:w-[40%]">
            <textarea
              value={caseText}
              onChange={(e) => setCaseText(e.target.value)}
              placeholder="Describe your case in detail for the most accurate simulation"
              className="block w-full resize-y rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm leading-relaxed text-gray-900 placeholder:text-gray-400 focus:border-navy-700 focus:outline-none focus:ring-1 focus:ring-navy-700 dark:border-gray-700 dark:bg-surface-dark dark:text-gray-100 dark:placeholder:text-gray-500 dark:focus:border-navy-500 dark:focus:ring-navy-500"
              style={{ minHeight: 220 }}
            />
            <Button
              onClick={handleRun}
              variant="primary"
              className="mt-4 w-full gap-2"
              disabled={!caseText.trim()}
            >
              <Brain className="h-4 w-4" />
              Run Simulation
            </Button>
          </div>

          {/* Right panel */}
          <div className="w-full lg:w-[60%]">
            <SimulationEmpty />
          </div>
        </div>
      </div>
    )
  }

  // Loading state
  if (running) {
    return (
      <div>
        <div className="mb-8">
          <h2 className="text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-100">
            Judicial Simulation
          </h2>
          <p className="mt-1.5 text-sm text-gray-500 dark:text-gray-400">
            Estimate the probable outcome of your case based on precedents
            and argument strength
          </p>
        </div>

        <div className="flex flex-col gap-8 lg:flex-row lg:gap-10">
          <div className="w-full lg:w-[40%]">
            <textarea
              value={caseText}
              onChange={(e) => setCaseText(e.target.value)}
              placeholder="Describe your case in detail for the most accurate simulation"
              className="block w-full resize-y rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm leading-relaxed text-gray-900 placeholder:text-gray-400 focus:border-navy-700 focus:outline-none focus:ring-1 focus:ring-navy-700 dark:border-gray-700 dark:bg-surface-dark dark:text-gray-100 dark:placeholder:text-gray-500 dark:focus:border-navy-500 dark:focus:ring-navy-500"
              style={{ minHeight: 220 }}
            />
            <Button
              onClick={handleRun}
              variant="primary"
              className="mt-4 w-full gap-2"
              disabled
            >
              <Loader2 className="h-4 w-4 animate-spin" />
              Running…
            </Button>

            {/* Stepped progress */}
            <div className="mt-6">
              <SteppedProgress currentStep={progressStep} />
            </div>
          </div>

          <div className="w-full lg:w-[60%]">
            <ResultsSkeleton />
          </div>
        </div>
      </div>
    )
  }

  // Error state (keep input visible)
  if (error && !simResult) {
    return (
      <div>
        <div className="mb-8">
          <h2 className="text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-100">
            Judicial Simulation
          </h2>
          <p className="mt-1.5 text-sm text-gray-500 dark:text-gray-400">
            Estimate the probable outcome of your case based on precedents
            and argument strength
          </p>
        </div>

        <div className="flex flex-col gap-8 lg:flex-row lg:gap-10">
          <div className="w-full lg:w-[40%]">
            <textarea
              value={caseText}
              onChange={(e) => setCaseText(e.target.value)}
              placeholder="Describe your case in detail for the most accurate simulation"
              className="block w-full resize-y rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm leading-relaxed text-gray-900 placeholder:text-gray-400 focus:border-navy-700 focus:outline-none focus:ring-1 focus:ring-navy-700 dark:border-gray-700 dark:bg-surface-dark dark:text-gray-100 dark:placeholder:text-gray-500 dark:focus:border-navy-500 dark:focus:ring-navy-500"
              style={{ minHeight: 220 }}
            />
            <Button
              onClick={handleRun}
              variant="primary"
              className="mt-4 w-full gap-2"
            >
              <Brain className="h-4 w-4" />
              Retry Simulation
            </Button>
            <ErrorBanner className="mt-4" message={error} />
          </div>
          <div className="w-full lg:w-[60%]">
            <SimulationEmpty />
          </div>
        </div>
      </div>
    )
  }

  // Success — render results
  const r = simResult
  const probPct = Math.round((r.win_probability ?? 0) * 100)
  const riskColor =
    r.risk_assessment?.color === 'green'
      ? 'green'
      : r.risk_assessment?.color === 'amber'
        ? 'yellow'
        : 'red'

  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-100">
          Judicial Simulation
        </h2>
        <p className="mt-1.5 text-sm text-gray-500 dark:text-gray-400">
          Estimate the probable outcome of your case based on precedents
          and argument strength
        </p>
      </div>

      <div className="flex flex-col gap-8 lg:flex-row lg:gap-10">
        {/* ── LEFT: Input (40%) ──────────────────────────────────── */}
        <div className="w-full lg:w-[40%]">
          <textarea
            value={caseText}
            onChange={(e) => setCaseText(e.target.value)}
            placeholder="Describe your case in detail for the most accurate simulation"
            className="block w-full resize-y rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm leading-relaxed text-gray-900 placeholder:text-gray-400 focus:border-navy-700 focus:outline-none focus:ring-1 focus:ring-navy-700 dark:border-gray-700 dark:bg-surface-dark dark:text-gray-100 dark:placeholder:text-gray-500 dark:focus:border-navy-500 dark:focus:ring-navy-500"
            style={{ minHeight: 220 }}
          />
          <Button
            onClick={handleRun}
            variant="primary"
            className="mt-4 w-full gap-2"
          >
            <Brain className="h-4 w-4" />
            Run Simulation
          </Button>

          {error && <ErrorBanner className="mt-4" message={error} />}
        </div>

        {/* ── RIGHT: Results (60%) ───────────────────────────────── */}
        <div className="w-full lg:w-[60%]">
          {/* ── Outcome Prediction ──────────────────────────────── */}
          <div className="flex flex-col items-center rounded-lg border border-gray-200 bg-white px-6 py-8 text-center dark:border-gray-800 dark:bg-surface-dark">
            <SimulationGauge value={r.win_probability} />

            {/* Risk badge */}
            <div className="mt-4">
              <Badge variant={riskColor} className="text-sm px-4 py-1">
                {r.risk_assessment?.level ?? '—'}
              </Badge>
            </div>

            {/* Recommendation */}
            {r.recommendation && (
              <p className="mt-3 max-w-md text-sm italic leading-relaxed text-gray-400 dark:text-gray-500">
                "{r.recommendation}"
              </p>
            )}
          </div>

          {/* ── Score Breakdown ─────────────────────────────────── */}
          <SectionSeparator>Score Breakdown</SectionSeparator>
          <div className="rounded-lg border border-gray-200 bg-white px-5 py-2 dark:border-gray-800 dark:bg-surface-dark">
            {(r.score_breakdown || []).map((sc, i) => (
              <div key={sc.component}>
                <ScoreBar
                  component={sc.component}
                  weight={sc.weight}
                  weightedScore={sc.weighted_score}
                  explanation={sc.explanation}
                />
                {i < r.score_breakdown.length - 1 && (
                  <div className="h-px bg-gray-100 dark:bg-gray-800" />
                )}
              </div>
            ))}
          </div>

          {/* ── Key Strengths ───────────────────────────────────── */}
          {r.key_strengths?.length > 0 && (
            <>
              <SectionSeparator>Key Strengths</SectionSeparator>
              <div className="rounded-lg border-l-[3px] border-green-400 bg-green-50/50 px-4 py-3 dark:border-green-700 dark:bg-green-900/10">
                <ul className="space-y-1.5">
                  {r.key_strengths.map((s, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 text-sm text-green-800 dark:text-green-300"
                    >
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-green-500" />
                      {s}
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}

          {/* ── Key Weaknesses ──────────────────────────────────── */}
          {r.key_weaknesses?.length > 0 && (
            <>
              <SectionSeparator>Key Weaknesses</SectionSeparator>
              <div className="rounded-lg border-l-[3px] border-red-400 bg-red-50/50 px-4 py-3 dark:border-red-700 dark:bg-red-900/10">
                <ul className="space-y-1.5">
                  {r.key_weaknesses.map((w, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 text-sm text-red-700 dark:text-red-300"
                    >
                      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-400" />
                      {w}
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}

          {/* ── Export ──────────────────────────────────────────── */}
          <div className="mt-6 flex justify-end gap-3">
            <Button
              variant="ghost"
              size="sm"
              className="gap-2"
              onClick={handleExportJSON}
            >
              <Download className="h-4 w-4" />
              Export as JSON
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="gap-2"
              onClick={handleExportPDF}
            >
              <Printer className="h-4 w-4" />
              Export as PDF
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
