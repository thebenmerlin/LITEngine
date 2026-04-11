import { useState, useCallback, useMemo } from 'react'
import { FlaskConical, Loader2, CheckCircle2, Beaker } from 'lucide-react'
import { extractFacts, searchPrecedents, runSimulation, ApiError } from '../lib/api'
import { recalculate, riskLevel, DEFAULT_TWEAKS } from '../utils/whatIfCalculator'
import SimulationGauge from '../components/SimulationGauge'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import ErrorBanner from '../components/ui/ErrorBanner'

/* ------------------------------------------------------------------ */
/*  Stepped progress (reused from Simulation)                          */
/* ------------------------------------------------------------------ */

const STEPS = [
  { label: 'Extracting facts…' },
  { label: 'Searching precedents…' },
  { label: 'Running simulation…' },
]

function SteppedProgress({ currentStep }) {
  return (
    <div className="flex items-center gap-3 py-5">
      {STEPS.map((step, i) => {
        const done = i < currentStep
        const active = i === currentStep
        return (
          <div key={i} className="flex items-center gap-3">
            <div
              className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                done
                  ? 'bg-navy-700 text-white'
                  : active
                    ? 'bg-navy-700/20 text-navy-700 dark:bg-navy-700/30 dark:text-navy-300'
                    : 'bg-gray-200 text-gray-400 dark:bg-gray-700 dark:text-gray-500'
              }`}
            >
              {done ? <CheckCircle2 className="h-3.5 w-3.5" /> : i + 1}
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
              <div className={`h-px w-5 ${i < currentStep ? 'bg-navy-700' : 'bg-gray-200 dark:bg-gray-700'}`} />
            )}
          </div>
        )
      })}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Section separator                                                  */
/* ------------------------------------------------------------------ */

function SectionHeader({ children }) {
  return (
    <div className="mt-5 pt-4">
      <div className="mb-2 h-px bg-gray-200 dark:bg-gray-800" />
      <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
        {children}
      </span>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Slider control                                                     */
/* ------------------------------------------------------------------ */

function SliderControl({ label, value, min = 0, max = 5, unit = '' }) {
  return (
    <div className="py-2">
      <div className="mb-1.5 flex items-center justify-between text-sm">
        <span className="text-gray-700 dark:text-gray-300">{label}</span>
        <span className="font-mono text-xs text-gray-400 dark:text-gray-500">
          {value}{unit && ` ${unit}`}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={1}
        value={value}
        readOnly
        className="w-full accent-navy-700"
      />
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Radio group                                                        */
/* ------------------------------------------------------------------ */

function RadioGroup({ label, options, value, onChange }) {
  return (
    <div className="py-2">
      <span className="mb-2 block text-sm text-gray-700 dark:text-gray-300">
        {label}
      </span>
      <div className="flex gap-3">
        {options.map(({ label: optLabel, value: optVal }) => (
          <label
            key={optVal}
            className={`flex cursor-pointer items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
              value === optVal
                ? 'bg-navy-700/10 text-navy-700 dark:bg-navy-700/30 dark:text-navy-200'
                : 'text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800'
            }`}
          >
            <input
              type="radio"
              name={label}
              value={optVal}
              checked={value === optVal}
              onChange={() => onChange(optVal)}
              className="sr-only"
            />
            {optLabel}
          </label>
        ))}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Dropdown                                                           */
/* ------------------------------------------------------------------ */

function DropdownControl({ label, options, value, onChange }) {
  return (
    <div className="py-2">
      <span className="mb-1.5 block text-sm text-gray-700 dark:text-gray-300">
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:border-navy-700 focus:outline-none focus:ring-1 focus:ring-navy-700 dark:border-gray-700 dark:bg-surface-dark dark:text-gray-100"
      >
        {options.map(({ label: optLabel, value: optVal }) => (
          <option key={optVal} value={optVal}>
            {optLabel}
          </option>
        ))}
      </select>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Checkbox list for weak args                                        */
/* ------------------------------------------------------------------ */

function WeakArgCheckboxes({ weakNodes, checked, onToggle }) {
  if (!weakNodes || weakNodes.length === 0) {
    return (
      <p className="py-2 text-sm text-gray-400 dark:text-gray-500">
        No weak arguments in base case.
      </p>
    )
  }
  return (
    <div className="py-2 space-y-1.5">
      {weakNodes.map((n) => {
        const id = n.id
        const label = n.label || id
        const isChecked = checked.includes(id)
        return (
          <label
            key={id}
            className={`flex cursor-pointer items-start gap-2 rounded-md px-2 py-1.5 text-sm transition-colors ${
              isChecked
                ? 'bg-green-50 text-green-700 dark:bg-green-900/10 dark:text-green-300'
                : 'text-gray-600 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-800'
            }`}
          >
            <input
              type="checkbox"
              checked={isChecked}
              onChange={() => onToggle(id)}
              className="mt-0.5 h-3.5 w-3.5 rounded accent-navy-700"
            />
            <span>Resolve: {label}</span>
          </label>
        )
      })}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  What-If page                                                       */
/* ------------------------------------------------------------------ */

export default function WhatIf() {
  // Base case
  const [caseText, setCaseText] = useState('')
  const [baseResult, setBaseResult] = useState(null)
  const [baseWeakNodes, setBaseWeakNodes] = useState([])
  const [loading, setLoading] = useState(false)
  const [progressStep, setProgressStep] = useState(0)
  const [loadError, setLoadError] = useState(null)

  // Tweaks state
  const [tweaks, setTweaks] = useState({ ...DEFAULT_TWEAKS })

  // Update a single tweak field
  const setTweak = useCallback((key, value) => {
    setTweaks((prev) => ({ ...prev, [key]: value }))
  }, [])

  // Toggle a weak argument resolution
  const toggleWeakArg = useCallback((id) => {
    setTweaks((prev) => ({
      ...prev,
      resolvedWeakArgs: prev.resolvedWeakArgs.includes(id)
        ? prev.resolvedWeakArgs.filter((x) => x !== id)
        : [...prev.resolvedWeakArgs, id],
    }))
  }, [])

  // Load base case (3-step API chain)
  const handleLoad = useCallback(async () => {
    if (!caseText.trim()) return
    setLoading(true)
    setLoadError(null)
    setBaseResult(null)
    setBaseWeakNodes([])
    setTweaks({ ...DEFAULT_TWEAKS })
    setProgressStep(0)

    try {
      // Step 1
      setProgressStep(0)
      const profile = await extractFacts({ caseText: caseText.trim(), useModel: true })

      // Step 2
      setProgressStep(1)
      const query = profile.legal_issues
        ? profile.legal_issues.join(' ')
        : caseText.trim()
      let precedents = []
      try {
        const sr = await searchPrecedents({ query, topK: 5, useKanoon: true })
        precedents = sr.results || []
      } catch {
        precedents = []
      }

      // Step 3
      setProgressStep(2)
      const simRes = await runSimulation({
        caseProfile: profile,
        precedents: precedents.slice(0, 5),
        graphStats: null,
      })

      setBaseResult(simRes.result)
      setBaseWeakNodes(simRes.result?.weak_nodes || [])
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.detail || err.message : err.message)
    } finally {
      setLoading(false)
    }
  }, [caseText])

  // Live recalculation — pure JS, instant
  const liveResult = useMemo(() => {
    if (!baseResult) return null
    const baseProb = baseResult.win_probability
    return recalculate(baseProb, tweaks)
  }, [baseResult, tweaks])

  const hasBase = baseResult !== null

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h2 className="text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-100">
          What-If Analyzer
        </h2>
        <p className="mt-1.5 text-sm text-gray-500 dark:text-gray-400">
          Modify case parameters and instantly see how outcome shifts
        </p>
      </div>

      {/* Three-column layout */}
      <div className="flex flex-col gap-6 xl:flex-row xl:gap-8">
        {/* ═══ LEFT COLUMN: Base Case (30%) ═══════════════════ */}
        <div className="w-full xl:w-[30%]">
          <textarea
            value={caseText}
            onChange={(e) => setCaseText(e.target.value)}
            placeholder="Paste your case description here to load a base simulation…"
            className="block w-full resize-y rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm leading-relaxed text-gray-900 placeholder:text-gray-400 focus:border-navy-700 focus:outline-none focus:ring-1 focus:ring-navy-700 dark:border-gray-700 dark:bg-surface-dark dark:text-gray-100 dark:placeholder:text-gray-500 dark:focus:border-navy-500 dark:focus:ring-navy-500"
            style={{ minHeight: 160 }}
          />
          <Button
            onClick={handleLoad}
            variant="primary"
            className="mt-3 w-full gap-2"
            disabled={loading || !caseText.trim()}
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading…
              </>
            ) : (
              <>
                <FlaskConical className="h-4 w-4" />
                Load Base Case
              </>
            )}
          </Button>

          {/* Stepped progress during load */}
          {loading && (
            <div className="mt-3">
              <SteppedProgress currentStep={progressStep} />
            </div>
          )}

          {/* Error */}
          {loadError && (
            <ErrorBanner className="mt-3" message={loadError} onDismiss={() => setLoadError(null)} />
          )}

          {/* Base probability summary card */}
          {hasBase && !loading && (
            <div className="mt-4 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-800 dark:bg-gray-900/50">
              <div className="flex items-center gap-2 text-sm">
                <Beaker className="h-4 w-4 text-navy-700 dark:text-navy-300" />
                <span className="text-gray-500 dark:text-gray-400">Base Probability:</span>
                <span className="font-semibold text-gray-900 dark:text-gray-100">
                  {Math.round(baseResult.win_probability * 100)}%
                </span>
                <Badge variant={riskLevel(baseResult.win_probability).color}>
                  {riskLevel(baseResult.win_probability).level}
                </Badge>
              </div>
              <p className="mt-1 text-[11px] text-gray-400 dark:text-gray-500">
                This value stays fixed as you tweak parameters.
              </p>
            </div>
          )}
        </div>

        {/* ═══ MIDDLE COLUMN: Parameter Tweaks (40%) ══════════ */}
        <div className="w-full xl:w-[40%]">
          {!hasBase && !loading && (
            <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-gray-300 dark:border-gray-700">
              <p className="text-sm text-gray-400 dark:text-gray-500">
                Load a base case to enable parameter tweaks
              </p>
            </div>
          )}

          {loading && (
            <div className="space-y-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-12 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-700" />
              ))}
            </div>
          )}

          {hasBase && !loading && (
            <div className="rounded-lg border border-gray-200 bg-white px-5 py-4 dark:border-gray-800 dark:bg-surface-dark">
              {/* Evidence Controls */}
              <SectionHeader>Evidence Controls</SectionHeader>

              <div className="py-2">
                <div className="mb-1.5 flex items-center justify-between text-sm">
                  <span className="text-gray-700 dark:text-gray-300">
                    Additional Evidence Pieces
                  </span>
                  <span className="font-mono text-xs text-gray-400 dark:text-gray-500">
                    {tweaks.additionalEvidence}{' '}
                    {tweaks.additionalEvidence === 1 ? 'piece' : 'pieces'}
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={5}
                  step={1}
                  value={tweaks.additionalEvidence}
                  onChange={(e) => setTweak('additionalEvidence', Number(e.target.value))}
                  className="w-full accent-navy-700"
                />
              </div>

              <RadioGroup
                label="Evidence Quality"
                value={tweaks.evidenceQuality}
                onChange={(v) => setTweak('evidenceQuality', v)}
                options={[
                  { label: 'Weak', value: 'weak' },
                  { label: 'Moderate', value: 'moderate' },
                  { label: 'Strong', value: 'strong' },
                ]}
              />

              {/* Statute Controls */}
              <SectionHeader>Statute Controls</SectionHeader>

              <div className="py-2">
                <div className="mb-1.5 flex items-center justify-between text-sm">
                  <span className="text-gray-700 dark:text-gray-300">
                    Additional IPC Sections
                  </span>
                  <span className="font-mono text-xs text-gray-400 dark:text-gray-500">
                    {tweaks.additionalIpcSections}
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={4}
                  step={1}
                  value={tweaks.additionalIpcSections}
                  onChange={(e) => setTweak('additionalIpcSections', Number(e.target.value))}
                  className="w-full accent-navy-700"
                />
              </div>

              <DropdownControl
                label="Jurisdiction Change"
                value={tweaks.jurisdiction}
                onChange={(v) => setTweak('jurisdiction', v)}
                options={[
                  { label: 'Same Court', value: 'same' },
                  { label: 'High Court', value: 'high' },
                  { label: 'Supreme Court', value: 'supreme' },
                  { label: 'District Court', value: 'district' },
                ]}
              />

              {/* Argument Controls */}
              <SectionHeader>Argument Controls</SectionHeader>

              <div className="mb-1 text-sm text-gray-700 dark:text-gray-300">
                Weak Arguments Resolved
              </div>
              <WeakArgCheckboxes
                weakNodes={baseWeakNodes}
                checked={tweaks.resolvedWeakArgs}
                onToggle={toggleWeakArg}
              />

              {/* Precedent Controls */}
              <SectionHeader>Precedent Controls</SectionHeader>

              <div className="py-2">
                <div className="mb-1.5 flex items-center justify-between text-sm">
                  <span className="text-gray-700 dark:text-gray-300">
                    Additional Supporting Precedents
                  </span>
                  <span className="font-mono text-xs text-gray-400 dark:text-gray-500">
                    {tweaks.additionalPrecedents}
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={5}
                  step={1}
                  value={tweaks.additionalPrecedents}
                  onChange={(e) => setTweak('additionalPrecedents', Number(e.target.value))}
                  className="w-full accent-navy-700"
                />
              </div>

              <RadioGroup
                label="Precedent Similarity"
                value={tweaks.precedentSimilarity}
                onChange={(v) => setTweak('precedentSimilarity', v)}
                options={[
                  { label: 'Low (0.5)', value: 'low' },
                  { label: 'Medium (0.7)', value: 'medium' },
                  { label: 'High (0.9)', value: 'high' },
                ]}
              />
            </div>
          )}
        </div>

        {/* ═══ RIGHT COLUMN: Live Result (30%) ════════════════ */}
        <div className="w-full xl:w-[30%]">
          {!hasBase && !loading && (
            <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-gray-300 dark:border-gray-700">
              <p className="text-sm text-gray-400 dark:text-gray-500">
                Results will appear here as you tweak parameters
              </p>
            </div>
          )}

          {loading && (
            <div className="space-y-4">
              <div className="h-40 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-700" />
              <div className="h-6 animate-pulse rounded bg-gray-200 dark:bg-gray-700" />
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-4 animate-pulse rounded bg-gray-200 dark:bg-gray-700" />
              ))}
            </div>
          )}

          {hasBase && !loading && liveResult && (
            <div className="space-y-4">
              {/* Gauge + risk */}
              <div className="rounded-lg border border-gray-200 bg-white px-4 py-6 text-center dark:border-gray-800 dark:bg-surface-dark">
                <SimulationGauge value={liveResult.adjusted} size={160} />

                {/* Delta */}
                {liveResult.delta !== 0 && (
                  <div className="mt-2">
                    <span
                      className={`text-sm font-semibold ${
                        liveResult.delta > 0
                          ? 'text-green-600 dark:text-green-400'
                          : 'text-red-600 dark:text-red-400'
                      }`}
                    >
                      {liveResult.delta > 0 ? '+' : ''}
                      {Math.round(liveResult.delta * 100)}%
                    </span>
                    <span className="ml-1.5 text-xs text-gray-400 dark:text-gray-500">
                      from base
                    </span>
                  </div>
                )}

                {/* Risk badge */}
                <div className="mt-3">
                  <Badge variant={riskLevel(liveResult.adjusted).color} className="text-sm px-3 py-1">
                    {riskLevel(liveResult.adjusted).level}
                  </Badge>
                </div>
              </div>

              {/* Change log */}
              {liveResult.changelog.length > 0 && (
                <div className="rounded-lg border border-gray-200 bg-white px-4 py-3 dark:border-gray-800 dark:bg-surface-dark">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                    Changes
                  </span>
                  <ul className="mt-2 space-y-1.5">
                    {liveResult.changelog.map((entry, i) => {
                      const positive = entry.startsWith('✓')
                      return (
                        <li
                          key={i}
                          className={`flex items-start gap-2 text-xs ${
                            positive
                              ? 'text-green-700 dark:text-green-400'
                              : 'text-red-600 dark:text-red-400'
                          }`}
                        >
                          <span className="mt-0.5 shrink-0">
                            {positive ? '✓' : '✗'}
                          </span>
                          {entry.replace(/^[✓✗] /, '')}
                        </li>
                      )
                    })}
                  </ul>
                </div>
              )}

              {/* Reset button */}
              <button
                onClick={() => setTweaks({ ...DEFAULT_TWEAKS })}
                className="w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-600 transition-colors hover:bg-gray-50 dark:border-gray-800 dark:bg-surface-dark dark:text-gray-400 dark:hover:bg-gray-800"
              >
                Reset to defaults
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
