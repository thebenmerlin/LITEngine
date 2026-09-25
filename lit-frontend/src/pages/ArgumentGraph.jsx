import { useEffect, useMemo, useState } from 'react'
import CytoscapeComponent from 'react-cytoscapejs'
import { ArrowUpRight, Download, Focus, GitBranch, Maximize, Search, ZoomIn, ZoomOut } from 'lucide-react'
import { EmptyPanel, ErrorNotice, PageHeading, RebuildButton, SampleCaseMenu } from '../components/workspace/Primitives'
import { useWorkspace } from '../workspace/WorkspaceContext'
import { useTheme } from '../hooks/useTheme'

const types = [
  { key: 'ISSUE', label: 'Issue', color: '#668db8' },
  { key: 'CLAIM', label: 'Claim', color: '#b45f4b' },
  { key: 'EVIDENCE', label: 'Evidence', color: '#678774' },
  { key: 'STATUTE', label: 'Statute', color: '#a57f42' },
  { key: 'PRECEDENT', label: 'Precedent', color: '#826f9e' },
]

const shape = { ISSUE: 'round-rectangle', CLAIM: 'round-rectangle', EVIDENCE: 'ellipse', STATUTE: 'diamond', PRECEDENT: 'hexagon' }

function stylesheet(dark) {
  const ink = dark ? '#e9e8df' : '#26302e'
  const surface = dark ? '#191d1c' : '#f8f7f1'
  return [
    { selector: 'node', style: {
      'background-color': 'data(color)', shape: 'data(shape)', width: 42, height: 42,
      label: 'data(shortLabel)', color: ink, 'font-family': 'IBM Plex Sans, sans-serif',
      'font-size': 10, 'font-weight': 500, 'text-valign': 'bottom', 'text-halign': 'center',
      'text-margin-y': 10, 'text-wrap': 'wrap', 'text-max-width': 115,
      'text-outline-width': 3, 'text-outline-color': surface,
      'border-color': surface, 'border-width': 2,
    } },
    { selector: 'node[type = "CLAIM"]', style: { width: 51, height: 38 } },
    { selector: 'node[type = "ISSUE"]', style: { width: 54, height: 38 } },
    { selector: 'node[?weak]', style: { 'border-color': '#d9634c', 'border-width': 4 } },
    { selector: 'node[?selected]', style: { 'border-color': dark ? '#faf6e9' : '#26302e', 'border-width': 4, width: 58, height: 48, 'font-weight': 700 } },
    { selector: 'edge', style: {
      width: 'data(width)', 'line-color': dark ? '#5c6761' : '#b9c0b9',
      'target-arrow-color': dark ? '#5c6761' : '#b9c0b9', 'target-arrow-shape': 'triangle',
      'arrow-scale': 0.7, 'curve-style': 'bezier', opacity: 0.7,
    } },
    { selector: 'edge[type = "contradicts"]', style: { 'line-color': '#d9634c', 'target-arrow-color': '#d9634c', 'line-style': 'dashed' } },
    { selector: 'edge[?connected]', style: { opacity: 1, width: 2.5, 'line-color': dark ? '#d9c79c' : '#b45f4b', 'target-arrow-color': dark ? '#d9c79c' : '#b45f4b' } },
    { selector: 'node[?dimmed], edge[?dimmed]', style: { opacity: 0.14 } },
    { selector: 'node[?hidden], edge[?hidden]', style: { display: 'none' } },
  ]
}

function nodeColor(type) {
  return types.find((item) => item.key === type)?.color || '#778580'
}

export default function ArgumentGraph() {
  const { graph, profile, precedents, status, errors, refreshGraph, stale, busy } = useWorkspace()
  const { dark } = useTheme()
  const [cy, setCy] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [activeTypes, setActiveTypes] = useState(() => new Set(types.map((item) => item.key)))
  const [focused, setFocused] = useState(false)
  const [nodeQuery, setNodeQuery] = useState('')

  const selected = graph?.nodes?.find((node) => node.id === selectedId)
    || graph?.nodes?.find((node) => node.type === 'CLAIM')
    || graph?.nodes?.[0]
  const relatedEdges = useMemo(() => graph?.edges?.filter((edge) => edge.source === selected?.id || edge.target === selected?.id) || [], [graph, selected])
  const relatedIds = useMemo(() => new Set([selected?.id, ...relatedEdges.flatMap((edge) => [edge.source, edge.target])]), [selected, relatedEdges])
  const queryMatchIds = useMemo(() => new Set(graph?.nodes?.filter((node) => node.label.toLowerCase().includes(nodeQuery.toLowerCase())).map((node) => node.id) || []), [graph, nodeQuery])

  const elements = useMemo(() => {
    if (!graph) return []
    const visible = new Set(graph.nodes.filter((node) => activeTypes.has(node.type)).map((node) => node.id))
    return [
      ...graph.nodes.map((node) => ({ data: {
        id: node.id, type: node.type, color: nodeColor(node.type), shape: shape[node.type] || 'ellipse',
        shortLabel: node.label.length > 31 ? `${node.label.slice(0, 30)}…` : node.label,
        weak: Boolean(node.weak || graph.weak_nodes?.includes(node.id)), selected: node.id === selected?.id,
        hidden: !visible.has(node.id), dimmed: (focused && !relatedIds.has(node.id)) || (nodeQuery && !queryMatchIds.has(node.id)),
      } })),
      ...graph.edges.map((edge, index) => ({ data: {
        id: edge.id || `edge-${index}`, source: edge.source, target: edge.target, type: edge.type,
        width: 1 + (edge.strength || 0.5), connected: edge.source === selected?.id || edge.target === selected?.id,
        hidden: !visible.has(edge.source) || !visible.has(edge.target),
        dimmed: focused && edge.source !== selected?.id && edge.target !== selected?.id,
      } })),
    ]
  }, [graph, activeTypes, selected, focused, relatedIds, nodeQuery, queryMatchIds])

  useEffect(() => {
    if (!cy) return undefined
    const onTap = (event) => setSelectedId(event.target.id())
    cy.on('tap', 'node', onTap)
    return () => cy.off('tap', 'node', onTap)
  }, [cy])

  useEffect(() => { setSelectedId(null); setFocused(false) }, [graph])

  const toggleType = (type) => setActiveTypes((current) => {
    const next = new Set(current)
    if (next.has(type)) next.delete(type)
    else next.add(type)
    return next
  })

  const exportPng = () => {
    if (!cy) return
    const link = document.createElement('a')
    link.href = cy.png({ full: true, scale: 2, bg: dark ? '#191d1c' : '#f8f7f1' })
    link.download = 'lit-argument-map.png'
    link.click()
  }

  const precedentSource = selected?.type === 'PRECEDENT'
    ? precedents?.find((item) => selected.id.endsWith(item.doc_id?.toLowerCase()))
    : null

  return <div className="page-stack graph-page">
    <PageHeading eyebrow="03 / ARGUMENT STRUCTURE" title="Argument map" description="Explore how issues, claims, facts, statutes and precedents connect. Generated links are prompts for review."
      action={graph && <RebuildButton onClick={refreshGraph} disabled={busy || stale}>Refresh map</RebuildButton>} />
    {stale && <div className="notice notice-info">The case text changed. Reanalyze the case before refreshing the map.</div>}
    <ErrorNotice message={errors.graph} title="Could not build the argument map" />
    <SampleCaseMenu />
    {!graph && status.graph !== 'running' && <EmptyPanel icon={GitBranch} title="See the structure behind the case" body={profile ? 'Use the case profile to generate a map of claims and supporting material.' : 'Analyze a case to build its argument map.'} action={profile && <RebuildButton onClick={refreshGraph} disabled={busy || stale}>Build map</RebuildButton>} />}
    {status.graph === 'running' && <div className="loading-line"><span className="spin-dot" /> Building argument relationships…</div>}
    {graph && <>
      <div className="graph-summary">
        <span><strong>{graph.node_count}</strong> elements</span><span><strong>{graph.edge_count}</strong> relationships</span><span className={graph.weak_nodes?.length ? 'weak-count' : ''}><strong>{graph.weak_nodes?.length || 0}</strong> claims to review</span>
        <span className="graph-summary-note">Generated structure · review against source text</span>
      </div>
      <div className="graph-toolbar">
        <div className="graph-filter-group">{types.map((type) => <button key={type.key} className={`graph-filter ${activeTypes.has(type.key) ? 'active' : ''}`} onClick={() => toggleType(type.key)} aria-pressed={activeTypes.has(type.key)}><i style={{ background: type.color }} />{type.label}</button>)}</div>
        <div className="graph-tools"><label className="graph-search"><Search size={15} /><input value={nodeQuery} onChange={(event) => setNodeQuery(event.target.value)} placeholder="Find a node" aria-label="Find a node" /></label><button className={`tool-button ${focused ? 'active' : ''}`} onClick={() => setFocused((value) => !value)} title="Focus selected node" aria-label="Focus selected node"><Focus size={17} /></button><button className="tool-button" onClick={() => cy?.fit(undefined, 48)} title="Fit map" aria-label="Fit map"><Maximize size={17} /></button><button className="tool-button" onClick={() => cy?.zoom({ level: Math.min(3, cy.zoom() * 1.25), renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } })} title="Zoom in" aria-label="Zoom in"><ZoomIn size={17} /></button><button className="tool-button" onClick={() => cy?.zoom({ level: Math.max(0.2, cy.zoom() / 1.25), renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } })} title="Zoom out" aria-label="Zoom out"><ZoomOut size={17} /></button><button className="tool-button" onClick={exportPng} title="Export PNG" aria-label="Export PNG"><Download size={17} /></button></div>
      </div>
      <div className="graph-workbench">
        <aside className="graph-rail">
          <div className="rail-header"><span className="eyebrow">REVIEW QUEUE</span><span>{graph.weak_nodes?.length || 0}</span></div>
          {graph.weak_nodes?.length ? graph.nodes.filter((node) => graph.weak_nodes.includes(node.id)).map((node) => <button key={node.id} className={`weak-item ${selected?.id === node.id ? 'selected' : ''}`} onClick={() => { setSelectedId(node.id); setFocused(true) }}><span className="weak-indicator" /><span><strong>{node.label}</strong><small>No incoming evidence support</small></span></button>) : <p className="rail-empty">No claims lack incoming evidence links in this generated map.</p>}
          <div className="rail-note">A weak flag means the graph builder found no evidence edge for that claim. It does not assess legal merit.</div>
        </aside>
        <div className="graph-canvas" role="img" aria-label="Interactive argument map">
          <CytoscapeComponent elements={elements} stylesheet={stylesheet(dark)} cy={setCy}
            layout={{ name: 'cose', animate: false, padding: 62, nodeRepulsion: 180000, idealEdgeLength: 120, edgeElasticity: 80 }}
            style={{ width: '100%', height: '100%' }} minZoom={0.2} maxZoom={3} />
          <div className="canvas-caption">DRAG TO MOVE · SCROLL TO ZOOM · SELECT A NODE TO INSPECT</div>
        </div>
        <aside className="graph-inspector">
          {selected && <>
            <div className="inspector-top"><span className="eyebrow">ELEMENT DETAIL</span><span className="node-type" style={{ color: nodeColor(selected.type) }}>{selected.type}</span></div>
            <h2>{selected.label}</h2>
            <p className="inspector-description">{selected.description || 'No further description available.'}</p>
            <div className="weight-field"><div><span>Importance weight</span><strong>{Math.round((selected.weight || 0) * 100)} / 100</strong></div><span className="weight-track"><i style={{ width: `${Math.round((selected.weight || 0) * 100)}%` }} /></span></div>
            {(selected.weak || graph.weak_nodes?.includes(selected.id)) && <div className="weak-insight"><strong>Needs support</strong><span>No evidence node points to this claim in the generated map.</span></div>}
            <div className="inspector-connections"><span className="eyebrow">CONNECTED MATERIAL / {relatedEdges.length}</span>{relatedEdges.length ? relatedEdges.map((edge, index) => {
              const other = graph.nodes.find((node) => node.id === (edge.source === selected.id ? edge.target : edge.source))
              return <button key={edge.id || index} onClick={() => { setSelectedId(other?.id); setFocused(true) }}><span className="relation-type">{edge.label || edge.type}</span><strong>{other?.label || 'Unknown element'}</strong><small>{other?.type || ''} · strength {Math.round((edge.strength || 0) * 100)}%</small></button>
            }) : <p className="muted">No connected elements.</p>}</div>
            {precedentSource && <a className="source-link" href={precedentSource.url} target="_blank" rel="noreferrer">Open source judgment <ArrowUpRight size={15} /></a>}
          </>}
        </aside>
      </div>
    </>}
  </div>
}
