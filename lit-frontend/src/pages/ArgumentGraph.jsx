import { useState, useCallback, useRef } from 'react'
import CytoscapeComponent from 'react-cytoscapejs'
import {
  GitBranch,
  Maximize2,
  ZoomIn,
  ZoomOut,
  AlertTriangle,
  X,
  Loader2,
} from 'lucide-react'
import { useApi } from '../hooks/useApi'
import { extractFacts, buildGraph, ApiError } from '../lib/api'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import ErrorBanner from '../components/ui/ErrorBanner'
import Spinner from '../components/ui/Spinner'

/* ------------------------------------------------------------------ */
/*  Node type metadata for the legend                                  */
/* ------------------------------------------------------------------ */

const NODE_LEGEND = [
  { type: 'CLAIM', label: 'Claim', color: '#1B2A4A' },
  { type: 'EVIDENCE', label: 'Evidence', color: '#374151' },
  { type: 'STATUTE', label: 'Statute', color: '#065F46' },
  { type: 'PRECEDENT', label: 'Precedent', color: '#92400E' },
  { type: 'ISSUE', label: 'Issue', color: '#1E3A5F' },
]

/* ------------------------------------------------------------------ */
/*  Edge style map                                                     */
/* ------------------------------------------------------------------ */

const EDGE_STYLE = {
  supports: { color: '#9CA3AF', 'line-style': 'solid', 'target-arrow-color': '#9CA3AF' },
  contradicts: { color: '#DC2626', 'line-style': 'dashed', 'target-arrow-color': '#DC2626' },
  cites: { color: '#D97706', 'line-style': 'solid', 'target-arrow-color': '#D97706' },
  raises: { color: '#1B2A4A', 'line-style': 'solid', 'target-arrow-color': '#1B2A4A' },
}

/* ------------------------------------------------------------------ */
/*  Convert backend response → cytoscape elements                      */
/* ------------------------------------------------------------------ */

function toElements(graphData, weakNodes) {
  const weakSet = new Set(weakNodes || [])

  const nodes = (graphData.nodes || []).map((n) => ({
    data: {
      id: n.id,
      label: n.label,
      type: n.type,
      color: n.color,
      shape: n.shape,
      weight: n.weight ?? 0.5,
      description: n.description ?? '',
      weak: weakSet.has(n.id),
    },
  }))

  const edges = (graphData.edges || []).map((e, i) => {
    const style = EDGE_STYLE[e.type] || EDGE_STYLE.supports
    return {
      data: {
        id: `e${i}`,
        source: e.source,
        target: e.target,
        label: e.label,
        type: e.type,
        ...style,
      },
    }
  })

  return [...nodes, ...edges]
}

/* ------------------------------------------------------------------ */
/*  Graph skeleton (loading placeholder)                               */
/* ------------------------------------------------------------------ */

function GraphSkeleton() {
  return (
    <div className="flex h-full items-center justify-center rounded-lg border border-gray-200 bg-white dark:border-gray-800 dark:bg-surface-dark">
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-navy-700 dark:text-navy-300" />
        <p className="text-sm text-gray-400 dark:text-gray-500">Building graph…</p>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Empty state (no graph yet)                                         */
/* ------------------------------------------------------------------ */

function GraphEmpty() {
  return (
    <div className="flex h-full flex-col items-center justify-center rounded-lg border border-dashed border-gray-300 dark:border-gray-700">
      <GitBranch className="mb-3 h-10 w-10 text-gray-300 dark:text-gray-600" />
      <p className="text-sm text-gray-400 dark:text-gray-500">
        Build a graph to visualize argument structure
      </p>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Weight bar                                                         */
/* ------------------------------------------------------------------ */

function WeightBar({ value }) {
  const pct = Math.round((value ?? 0.5) * 100)
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
        <div
          className="h-full rounded-full bg-navy-700 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="shrink-0 text-xs tabular-nums text-gray-500 dark:text-gray-400">
        {pct}%
      </span>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  ArgumentGraph page                                                 */
/* ------------------------------------------------------------------ */

export default function ArgumentGraph() {
  const [caseText, setCaseText] = useState('')
  const [graphData, setGraphData] = useState(null)
  const [selectedNode, setSelectedNode] = useState(null)

  const cyRef = useRef(null)

  // Graph build (manual — not using useApi since we chain two calls)
  const [building, setBuilding] = useState(false)
  const [buildError, setBuildError] = useState(null)

  const handleBuild = useCallback(async () => {
    if (!caseText.trim()) return
    setBuilding(true)
    setBuildError(null)
    setSelectedNode(null)
    setGraphData(null)

    try {
      // Step 1: extract facts
      const profile = await extractFacts({ caseText: caseText.trim(), useModel: true })
      // Step 2: build graph
      const graph = await buildGraph({ caseProfile: profile, precedents: [] })
      setGraphData(graph)
    } catch (err) {
      setBuildError(
        err instanceof ApiError ? err.detail || err.message : err.message,
      )
    } finally {
      setBuilding(false)
    }
  }, [caseText])

  // Cytoscape node click handler
  const onNodeClick = useCallback((event) => {
    const { data } = event.target
    if (!data || !data.label) return
    setSelectedNode({
      label: data('label'),
      type: data('type'),
      description: data('description'),
      weight: data('weight'),
      color: data('color'),
    })
  }, [])

  // Graph controls
  const fitGraph = useCallback(() => {
    if (cyRef.current) cyRef.current.fit(undefined, 40)
  }, [])

  const zoomIn = useCallback(() => {
    if (cyRef.current) cyRef.current.zoom({ level: cyRef.current.zoom() * 1.3 })
  }, [])

  const zoomOut = useCallback(() => {
    if (cyRef.current) cyRef.current.zoom({ level: cyRef.current.zoom() / 1.3 })
  }, [])

  const weakNodeIds = new Set(graphData?.weak_nodes ?? [])

  // Cytoscape stylesheet — shape mapping
  const stylesheet = [
    // Default node style
    {
      selector: 'node',
      style: {
        'background-color': (el) => el.data('color') || '#666',
        label: (el) => {
          const t = el.data('label') || ''
          return t.length > 25 ? t.slice(0, 24) + '…' : t
        },
        'text-valign': 'bottom',
        'text-halign': 'center',
        'text-margin-y': 12,
        'font-size': 11,
        'font-family': 'Inter, system-ui, sans-serif',
        'text-wrap': 'wrap',
        'text-max-width': 90,
        width: 60,
        height: 60,
        'border-width': 0,
      },
    },
    // Weak nodes — red border, slightly larger
    {
      selector: 'node[weak = true]',
      style: {
        'border-width': 3,
        'border-color': '#DC2626',
        width: 68,
        height: 68,
      },
    },
    // Shape overrides
    {
      selector: 'node[type = "CLAIM"]',
      style: { shape: 'rectangle', width: 70, height: 50 },
    },
    {
      selector: 'node[type = "EVIDENCE"]',
      style: { shape: 'ellipse', width: 55, height: 55 },
    },
    {
      selector: 'node[type = "STATUTE"]',
      style: { shape: 'diamond', width: 55, height: 55 },
    },
    {
      selector: 'node[type = "PRECEDENT"]',
      style: { shape: 'hexagon', width: 55, height: 55 },
    },
    {
      selector: 'node[type = "ISSUE"]',
      style: { shape: 'round-rectangle', width: 65, height: 50 },
    },
    // Default edge
    {
      selector: 'edge',
      style: {
        'curve-style': 'bezier',
        'target-arrow-shape': 'triangle',
        'target-arrow-size': 10,
        width: 1.5,
        'font-size': 9,
        'text-margin-y': -8,
        label: (el) => el.data('label') || '',
        'text-opacity': 0.6,
        'text-background-color': '#ffffff',
        'text-background-opacity': 0.8,
        'text-background-padding': 2,
      },
    },
    // Edge color/type overrides via data attributes set in toElements
    {
      selector: 'edge[type = "supports"]',
      style: { 'line-color': '#9CA3AF', 'target-arrow-color': '#9CA3AF' },
    },
    {
      selector: 'edge[type = "contradicts"]',
      style: { 'line-color': '#DC2626', 'target-arrow-color': '#DC2626', 'line-style': 'dashed' },
    },
    {
      selector: 'edge[type = "cites"]',
      style: { 'line-color': '#D97706', 'target-arrow-color': '#D97706' },
    },
    {
      selector: 'edge[type = "raises"]',
      style: { 'line-color': '#1B2A4A', 'target-arrow-color': '#1B2A4A' },
    },
  ]

  const elements = graphData ? toElements(graphData, graphData.weak_nodes) : []
  const weakList = graphData
    ? (graphData.nodes ?? []).filter((n) => weakNodeIds.has(n.id))
    : []

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h2 className="text-2xl font-semibold tracking-tight text-gray-900 dark:text-gray-100">
          Argument Graph
        </h2>
        <p className="mt-1.5 text-sm text-gray-500 dark:text-gray-400">
          Visualize the legal argument structure of your case
        </p>
      </div>

      {/* Two-panel layout */}
      <div className="flex flex-col gap-8 lg:flex-row lg:gap-10">
        {/* ── LEFT: Input panel (35%) ──────────────────────────── */}
        <div className="w-full lg:w-[35%]">
          <textarea
            value={caseText}
            onChange={(e) => setCaseText(e.target.value)}
            placeholder="Paste your case description to generate the argument graph"
            className="block w-full resize-y rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm leading-relaxed text-gray-900 placeholder:text-gray-400 focus:border-navy-700 focus:outline-none focus:ring-1 focus:ring-navy-700 dark:border-gray-700 dark:bg-surface-dark dark:text-gray-100 dark:placeholder:text-gray-500 dark:focus:border-navy-500 dark:focus:ring-navy-500"
            style={{ minHeight: 200 }}
          />

          {/* Build button */}
          <Button
            onClick={handleBuild}
            variant="primary"
            className="mt-4 w-full gap-2"
            disabled={building || !caseText.trim()}
          >
            {building ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Building…
              </>
            ) : (
              <>
                <GitBranch className="h-4 w-4" />
                Build Graph
              </>
            )}
          </Button>

          {/* Error */}
          {buildError && (
            <ErrorBanner className="mt-4" message={buildError} onDismiss={() => setBuildError(null)} />
          )}

          {/* Stats bar */}
          {graphData && !building && (
            <div className="mt-4 text-xs text-gray-400 dark:text-gray-500">
              <span className="font-medium text-gray-600 dark:text-gray-300">
                {graphData.node_count}
              </span>{' '}
              nodes ·{' '}
              <span className="font-medium text-gray-600 dark:text-gray-300">
                {graphData.edge_count}
              </span>{' '}
              edges ·{' '}
              <span className="font-medium text-gray-600 dark:text-gray-300">
                {graphData.weak_nodes?.length ?? 0}
              </span>{' '}
              weak arguments
            </div>
          )}

          {/* Legend */}
          <div className="mt-6">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
              Legend
            </h3>
            <div className="space-y-2">
              {NODE_LEGEND.map(({ type, label, color }) => (
                <div key={type} className="flex items-center gap-2.5 text-sm text-gray-600 dark:text-gray-400">
                  <span
                    className="h-3 w-3 shrink-0 rounded-sm"
                    style={{ backgroundColor: color }}
                  />
                  {label}
                </div>
              ))}
            </div>
          </div>

          {/* Weak arguments */}
          {weakList.length > 0 && (
            <div className="mt-6">
              <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-red-500">
                <AlertTriangle className="h-3.5 w-3.5" />
                Arguments needing support
              </h3>
              <ul className="space-y-1.5">
                {weakList.map((n) => (
                  <li
                    key={n.id}
                    className="flex items-start gap-2 text-sm text-red-600 dark:text-red-400"
                  >
                    <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-red-400" />
                    {n.label}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* ── RIGHT: Graph panel (65%) ─────────────────────────── */}
        <div className="w-full lg:w-[65%]">
          {/* Loading */}
          {building && <GraphSkeleton />}

          {/* Empty */}
          {!building && !graphData && <GraphEmpty />}

          {/* Graph */}
          {!building && graphData && elements.length > 0 && (
            <div>
              {/* Controls row */}
              <div className="mb-2 flex justify-end gap-1">
                {[
                  { fn: fitGraph, icon: Maximize2, title: 'Fit to screen' },
                  { fn: zoomIn, icon: ZoomIn, title: 'Zoom in' },
                  { fn: zoomOut, icon: ZoomOut, title: 'Zoom out' },
                ].map(({ fn, icon: Icon, title }) => (
                  <button
                    key={title}
                    onClick={fn}
                    title={title}
                    className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-300"
                  >
                    <Icon className="h-4 w-4" />
                  </button>
                ))}
              </div>

              {/* Cytoscape container */}
              <div className="overflow-hidden rounded-lg border border-gray-200 bg-white transition-colors duration-200 dark:border-gray-800 dark:bg-surface-dark">
                <CytoscapeComponent
                  elements={elements}
                  stylesheet={stylesheet}
                  cy={(cy) => { cyRef.current = cy }}
                  style={{ width: '100%', height: 520 }}
                  layout={{ name: 'cose', animate: true, animationDuration: 600, padding: 30 }}
                  className="select-none"
                  wheelSensitivity={0.3}
                  zoom={1}
                  minZoom={0.2}
                  maxZoom={3}
                  tap={onNodeClick}
                />
              </div>

              {/* Selected node info */}
              {selectedNode && (
                <div className="mt-4 rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-surface-dark">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span
                          className="h-3 w-3 rounded-sm"
                          style={{ backgroundColor: selectedNode.color }}
                        />
                        <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                          {selectedNode.label}
                        </span>
                      </div>
                      <Badge variant="navy" className="mt-1 text-[10px]">
                        {selectedNode.type}
                      </Badge>
                    </div>
                    <button
                      onClick={() => setSelectedNode(null)}
                      className="rounded p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                  {selectedNode.description && (
                    <p className="mt-2 text-sm leading-relaxed text-gray-600 dark:text-gray-400">
                      {selectedNode.description}
                    </p>
                  )}
                  <div className="mt-3">
                    <div className="mb-1 flex items-center justify-between text-xs text-gray-400 dark:text-gray-500">
                      <span>Weight</span>
                    </div>
                    <WeightBar value={selectedNode.weight} />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
