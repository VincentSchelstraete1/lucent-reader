import { useMemo, useState } from "react"

export type StructuredVisualSpec = {
  type: "diagram" | "process" | "labeling" | "ordering" | "prediction" | "step_through"
  title: string
  purpose: string
  nodes: Array<{ id: string; label: string; detail?: string | null; group?: string | null }>
  edges: Array<{ source: string; target: string; label?: string | null }>
  stages: Array<{ title?: string; explanation?: string; activeNodeIds?: string[] }>
  answerId?: string | null
}

/** Deterministic, intentionally small SVG grammar for model-supplied visuals. */
export function StructuredVisual({ spec }: { spec: StructuredVisualSpec }) {
  const [selected, setSelected] = useState<string | null>(null)
  const [stage, setStage] = useState(0)
  const nodes = spec.nodes.slice(0, 16)
  const currentStage = spec.stages[stage]
  const active = useMemo(() => new Set(currentStage?.activeNodeIds ?? []), [currentStage])
  const positions = nodes.map((node, index) => ({ node, x: 80 + (index % 4) * 170, y: 70 + Math.floor(index / 4) * 74 }))
  const byId = new Map(positions.map((entry) => [entry.node.id, entry]))
  const selectedNode = nodes.find((node) => node.id === selected)
  return <section className="structured-visual" aria-label={spec.title}>
    <div className="structured-visual-heading"><strong>{spec.title}</strong><span>{spec.purpose}</span></div>
    <svg viewBox="0 0 760 360" role="img" aria-label={spec.purpose}>
      <defs><marker id="lucent-arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="currentColor" /></marker></defs>
      {spec.edges.slice(0, 24).map((edge) => { const from = byId.get(edge.source); const to = byId.get(edge.target); if (!from || !to) return null; return <g key={`${edge.source}-${edge.target}`} className="structured-visual-edge"><line x1={from.x + 65} y1={from.y + 20} x2={to.x} y2={to.y + 20} markerEnd="url(#lucent-arrow)" /><text x={(from.x + to.x) / 2} y={(from.y + to.y) / 2 + 12}>{edge.label}</text></g> })}
      {positions.map(({ node, x, y }) => <g key={node.id} className={`structured-visual-node ${active.has(node.id) ? "active" : ""} ${selected === node.id ? "selected" : ""}`} tabIndex={0} role="button" aria-label={`Learn about ${node.label}`} onClick={() => setSelected(node.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelected(node.id) } }}><rect x={x} y={y} width="132" height="42" rx="7" /><text x={x + 66} y={y + 25} textAnchor="middle">{node.label.slice(0, 22)}</text></g>)}
    </svg>
    {selectedNode && <p className="structured-visual-detail" role="status"><strong>{selectedNode.label}:</strong> {selectedNode.detail || "This element is part of the relationship shown above."}</p>}
    {spec.stages.length > 0 && <div className="structured-visual-controls"><span>Stage {stage + 1} of {spec.stages.length}</span><button type="button" onClick={() => setStage((value) => Math.max(0, value - 1))} disabled={stage === 0}>Previous</button><button type="button" onClick={() => setStage((value) => Math.min(spec.stages.length - 1, value + 1))} disabled={stage === spec.stages.length - 1}>Next</button>{currentStage?.explanation && <span>{currentStage.explanation}</span>}</div>}
  </section>
}
