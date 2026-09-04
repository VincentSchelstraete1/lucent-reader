import { useState } from "react"

export type MechanismEntity = { id: string; label: string; color?: string }
export type EntityStatus = "default" | "active" | "selected" | "compared" | "changed" | "completed" | "inactive"
export type MechanismStage = {
  title: string
  explanation: string
  equation?: string
  activeEntityIds?: string[]
  notice?: string
  insight?: string
  vectors?: { id: string; x: number; y: number; color?: string; dashed?: boolean; label?: string }[]
  visual?: StageVisual
}
export type SequenceExchangeScene = { type: "sequence_exchange_scene"; actors: { id: string; label: string }[]; messages: { id: string; sender: string; receiver: string; label: string; reason?: string | null; result?: string | null }[]; visibleMessageIds: string[]; emphasizedMessageId?: string | null }
export type VectorScene = { type: "vector_scene"; activeEntityIds: string[]; operations?: Array<{ type: "project" | "subtract" | "highlight" | "reveal"; entityIds: string[]; reason?: string | null; result?: string | null }>; relationships?: Array<{ source: string; target: string; relation: "perpendicular_to" | "projects_onto" | "parallel_to"; explanation?: string | null }> }
export type SemanticRegion = { id: string; label: string; entityIds: string[]; status: "active" | "selected" | "completed" | "input" | "output"; explanation?: string | null }
export type OrderedCollectionState = { items: Array<{ entityId: string; status: EntityStatus }>; regions: SemanticRegion[] }
export type OrderedOperation = { type: "compare" | "swap" | "move" | "highlight" | "mark_complete"; entityIds: string[]; reason?: string | null; result?: string | null }
export type OrderedItemsScene = { type: "ordered_items_scene"; before: OrderedCollectionState; operation: OrderedOperation; after?: OrderedCollectionState | null; notice?: string | null }
export type MechanismPrimitive = { id: string; kind: "region" | "boundary" | "object" | "particle" | "flow" | "quantity_bar" | "annotation"; label?: string; x: number; y: number; width?: number; height?: number; x2?: number; y2?: number; value?: number; color?: string; visibleFromStage?: number; detail?: string }
export type MechanismScene = { type: "mechanism_scene"; primitives: MechanismPrimitive[]; operations?: Array<{ type: "photon_arrives" | "electron_moves" | "particle_accumulates" | "gradient_increases" | "object_transforms" | "value_changes" | "flow"; primitiveIds: string[]; explanation?: string }> }
export type StageVisual = SequenceExchangeScene | VectorScene | OrderedItemsScene | MechanismScene
export type MechanismPrediction = { prompt: string; options: string[]; answer: number; reveal: string }
export type StepThroughMechanismData = {
  sceneType: string
  learningGoal: string
  entities: MechanismEntity[]
  stages: MechanismStage[]
  prediction?: MechanismPrediction
  conclusion: string
}

export type GeneratedStepThroughMechanism = {
  type: "step_through_mechanism"
  sceneType: string
  title: string
  learningGoal: string
  entities: Array<{ id: string; kind: "item" | "actor" | "vector" | "node" | "quantity"; label: string; description?: string | null }>
  stages: Array<{ title: string; explanation: string; stateChanges: Array<{ entityId: string; change: string; why?: string | null }>; equation?: string | null; activeEntityIds: string[]; notice?: string | null; insight?: string | null; visual?: unknown }>
  prediction?: MechanismPrediction | null
  conclusion: string
}

export function generatedMechanismToRendererData(mechanism: GeneratedStepThroughMechanism): StepThroughMechanismData {
  return {
    sceneType: mechanism.sceneType,
    learningGoal: mechanism.learningGoal,
    entities: mechanism.entities.map((entity) => ({ id: entity.id, label: entity.label })),
    stages: mechanism.stages.map((stage) => ({
      title: stage.title,
      explanation: stage.explanation,
      equation: stage.equation ?? undefined,
      activeEntityIds: stage.activeEntityIds,
      notice: stage.notice ?? undefined,
      insight: stage.insight ?? undefined,
      visual: stage.visual as StageVisual | undefined,
    })),
    prediction: mechanism.prediction ?? undefined,
    conclusion: mechanism.conclusion,
  }
}

const OPERATION_LABELS: Record<OrderedOperation["type"], string> = {
  compare: "Compare",
  swap: "Swap",
  move: "Move",
  highlight: "Focus on",
  mark_complete: "Mark complete",
}

function entityLabel(id: string, entities: MechanismEntity[]) {
  return entities.find((entity) => entity.id === id)?.label ?? "Unknown item"
}

function OrderedStateRow({ state, entities, label }: { state: OrderedCollectionState; entities: MechanismEntity[]; label?: string }) {
  return <div className="ordered-state">
    {label && <p className="ordered-state-label">{label}</p>}
    <div className="ordered-items-row" role="list" aria-label={label ?? "Ordered items"}>
      {state.items.map((item) => <div key={item.entityId} className={`ordered-item status-${item.status}`} role="listitem">
        <span className="ordered-item-value">{entityLabel(item.entityId, entities)}</span>
        {item.status === "completed" && <span className="ordered-item-status" aria-label="completed">✓</span>}
      </div>)}
    </div>
    {state.regions.length > 0 && <div className="ordered-regions">{state.regions.map((region) => <div key={region.id} className={`ordered-region region-${region.status}`}>
      <strong>{region.label}</strong>
      <span>{region.entityIds.map((id) => entityLabel(id, entities)).join(", ")}</span>
      {region.explanation && <small>{region.explanation}</small>}
    </div>)}</div>}
  </div>
}

function OrderedItemsVisual({ scene, entities }: { scene: OrderedItemsScene; entities: MechanismEntity[] }) {
  const labels = scene.operation.entityIds.map((id) => entityLabel(id, entities))
  const operationText = `${OPERATION_LABELS[scene.operation.type]} ${labels.join(scene.operation.type === "move" ? "" : " and ")}`.trim()
  return <div className="ordered-transition" role="img" aria-label={`${operationText}. ${scene.operation.reason ?? ""}`}>
    <OrderedStateRow state={scene.before} entities={entities} label={scene.after ? "Before" : undefined} />
    <div className="ordered-operation" aria-label="State transition">
      <span className="ordered-operation-arrow" aria-hidden="true">↓</span>
      <strong>{operationText}</strong>
      {scene.operation.reason && <p>{scene.operation.reason}</p>}
    </div>
    {scene.after && <OrderedStateRow state={scene.after} entities={entities} label="After" />}
    {scene.operation.result && <p className="ordered-result"><strong>Result:</strong> {scene.operation.result}</p>}
    {scene.notice && <p className="scene-notice"><strong>Notice:</strong> {scene.notice}</p>}
  </div>
}

function SequenceExchangeVisual({ scene }: { scene: SequenceExchangeScene }) {
  const actorX = (index: number) => scene.actors.length === 1 ? 210 : 60 + index * (300 / (scene.actors.length - 1))
  const actorIndex = new Map(scene.actors.map((actor, index) => [actor.id, index]))
  const visibleMessages = scene.messages.filter((message) => scene.visibleMessageIds.includes(message.id))
  const height = Math.max(145, 88 + visibleMessages.length * 48)
  const emphasized = scene.messages.find((message) => message.id === scene.emphasizedMessageId)
  return <div className="sequence-exchange"><svg viewBox={`0 0 420 ${height}`} role="img" aria-label="Sequence exchange diagram">
    {scene.actors.map((actor, index) => <g key={actor.id}><rect x={actorX(index) - 44} y="12" width="88" height="30" rx="8" fill="#fbfaf6" stroke="#58735d" strokeWidth="2" /><text x={actorX(index)} y="32" textAnchor="middle" className="vector-label">{actor.label}</text><line x1={actorX(index)} y1="48" x2={actorX(index)} y2={height - 16} className="sequence-lifeline" /></g>)}
    {scene.messages.map((message, index) => {
      if (!scene.visibleMessageIds.includes(message.id)) return null
      const from = actorIndex.get(message.sender), to = actorIndex.get(message.receiver)
      if (from === undefined || to === undefined) return null
      const visibleIndex = visibleMessages.findIndex((item) => item.id === message.id)
      const y = 78 + visibleIndex * 48
      const x1 = actorX(from), x2 = actorX(to), direction = x2 >= x1 ? 1 : -1
      const tip = x2 - direction * 2
      const head = `${tip},${y} ${tip - direction * 10},${y - 5} ${tip - direction * 10},${y + 5}`
      const emphasized = scene.emphasizedMessageId === message.id
      return <g key={message.id} className={emphasized ? "sequence-message sequence-message-emphasized" : "sequence-message"}><line x1={x1} y1={y} x2={tip} y2={y} stroke="#58735d" strokeWidth={emphasized ? 3 : 2} /><polygon points={head} fill="#58735d" /><text x={(x1 + x2) / 2} y={y - 9} textAnchor="middle" className="sequence-message-label">{message.label}</text></g>
    })}
    <text x="12" y={height - 10} className="axis-label">time ↓</text>
  </svg>{emphasized && (emphasized.reason || emphasized.result) && <div className="sequence-teaching-detail"><strong>{emphasized.label}</strong>{emphasized.reason && <span>{emphasized.reason}</span>}{emphasized.result && <span className="sequence-result">Result: {emphasized.result}</span>}</div>}</div>
}

function MechanismSceneVisual({ scene, stage }: { scene: MechanismScene; stage: number }) {
  const visible = scene.primitives.filter((primitive) => (primitive.visibleFromStage ?? 0) <= stage)
  const activeIds = new Set(scene.operations?.flatMap((operation) => operation.primitiveIds) ?? [])
  return <div className="mechanism-scene" role="img" aria-label="Mechanism visual"><svg viewBox="0 0 720 360">
    {visible.map((p) => p.kind === "region" ? <g key={p.id}><rect className="mechanism-region" x={p.x} y={p.y} width={p.width ?? 100} height={p.height ?? 80} rx="12" fill={p.color ?? "#e7efe7"} /><text x={p.x + 12} y={p.y + 22}>{p.label}</text></g> : p.kind === "boundary" ? <line key={p.id} className="mechanism-boundary" x1={p.x} y1={p.y} x2={p.x2 ?? p.x} y2={p.y2 ?? p.y} /> : p.kind === "particle" ? <g key={p.id} className={activeIds.has(p.id) ? "mechanism-active" : ""}><circle cx={p.x} cy={p.y} r="7" fill={p.color ?? "#4d8764"} /><text x={p.x + 11} y={p.y + 4}>{p.label}</text></g> : p.kind === "flow" ? <g key={p.id}><line className="mechanism-flow" x1={p.x} y1={p.y} x2={p.x2 ?? p.x + 40} y2={p.y2 ?? p.y} markerEnd="url(#mechanism-arrow)" /><text x={(p.x + (p.x2 ?? p.x + 40)) / 2} y={(p.y + (p.y2 ?? p.y)) / 2 - 6}>{p.label}</text></g> : p.kind === "quantity_bar" ? <g key={p.id}><text x={p.x} y={p.y - 6}>{p.label}: {p.value}</text><rect x={p.x} y={p.y} width={p.width ?? 100} height="12" rx="6" fill="#d9e5da" /><rect x={p.x} y={p.y} width={(p.width ?? 100) * Math.min(1, Math.max(0, p.value ?? 0))} height="12" rx="6" fill={p.color ?? "#4d8764"} /></g> : <text key={p.id} className="mechanism-annotation" x={p.x} y={p.y}>{p.label}</text>)}
    <defs><marker id="mechanism-arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#477456" /></marker></defs>
  </svg></div>
}

const toScreen = ({ x, y }: { x: number; y: number }) => ({ x: 70 + x, y: 215 - y })

function VectorArrow({ vector }: { vector: NonNullable<MechanismStage["vectors"]>[number] }) {
  const color = vector.color ?? "#1d9e75"
  const strokeWidth = vector.dashed ? 3 : 4
  const start = { x: 70, y: 215 }
  const endpoint = toScreen(vector)
  const dx = endpoint.x - start.x
  const dy = endpoint.y - start.y
  const length = Math.sqrt(dx * dx + dy * dy)
  const ux = dx / Math.max(length, 0.001)
  const uy = dy / Math.max(length, 0.001)
  const px = -uy
  const py = ux
  const headLength = Math.min(strokeWidth * 3, length * 0.35)
  const headWidth = strokeWidth * 2.2
  const baseCenter = { x: endpoint.x - ux * headLength, y: endpoint.y - uy * headLength }
  const left = { x: baseCenter.x + px * headWidth / 2, y: baseCenter.y + py * headWidth / 2 }
  const right = { x: baseCenter.x - px * headWidth / 2, y: baseCenter.y - py * headWidth / 2 }
  return <g>
    <line x1={start.x} y1={start.y} x2={baseCenter.x} y2={baseCenter.y} className={`vector vector-${vector.id} ${vector.dashed ? "vector-dashed" : ""}`} stroke={color} style={{ strokeWidth }} strokeLinecap="round" />
    <polygon points={`${endpoint.x},${endpoint.y} ${left.x},${left.y} ${right.x},${right.y}`} fill={color} />
    <text x={endpoint.x + 7} y={endpoint.y - 7} className={`vector-label vector-label-${vector.id}`}>{vector.label ?? vector.id}</text>
  </g>
}

const SUPPORTED_SCENES = new Set(["vector_scene", "sequence_exchange_scene", "ordered_items_scene", "mechanism_scene"])

export function visualUnavailableReason(data: StepThroughMechanismData, stage: MechanismStage): string | null {
  if (!SUPPORTED_SCENES.has(data.sceneType)) return `Unsupported scene type: ${data.sceneType || "missing"}`
  if (data.sceneType === "vector_scene") return stage.vectors?.length ? null : "Vector semantics do not include deterministic geometry for this stage."
  if (!stage.visual) return "This stage has no visual semantic program."
  if (stage.visual.type !== data.sceneType) return `Stage visual ${stage.visual.type} does not match ${data.sceneType}.`
  return null
}

export function summarizeVisualProgram(data: StepThroughMechanismData) {
  const sequenceMessageIds = new Set<string>()
  let operations = 0
  data.stages.forEach((stage) => {
    if (stage.visual?.type === "ordered_items_scene") operations += 1
    if (stage.visual?.type === "sequence_exchange_scene") stage.visual.messages.forEach((message) => sequenceMessageIds.add(message.id))
    if (stage.visual?.type === "vector_scene") operations += stage.visual.operations?.length ?? 0
  })
  operations += sequenceMessageIds.size
  const stateChangingOperations = data.stages.filter((stage) => stage.visual?.type === "ordered_items_scene" && ["swap", "move", "mark_complete"].includes(stage.visual.operation.type)).length
  const availableStages = data.stages.filter((stage) => visualUnavailableReason(data, stage) === null).length
  return { scene: data.sceneType, entities: data.entities.length, stages: data.stages.length, operations, stateChangingOperations, availableStages }
}

function VisualUnavailable({ reason }: { reason: string }) {
  return <div className="visual-unavailable" role="status"><strong>Visual unavailable</strong><span>{reason}</span><small>The teaching explanation remains available below.</small></div>
}

export function StepThroughMechanism({ data }: { data: StepThroughMechanismData }) {
  const [stage, setStage] = useState(0)
  const [choice, setChoice] = useState<number | null>(null)
  const [expanded, setExpanded] = useState(false)
  const current = data.stages[stage]
  const vectors = current.vectors ?? []
  const unavailable = visualUnavailableReason(data, current)
  return <section className="step-mechanism" aria-label={data.learningGoal}>
    <p className="step-goal">Learning goal: {data.learningGoal}</p>
    <div className={`step-visual${expanded ? " step-visual-expanded" : ""}`} aria-live="polite">
      <button type="button" className="structured-visual-expand" onClick={() => setExpanded((value) => !value)} aria-label={`${expanded ? "Close" : "Expand"} visual`}>{expanded ? "Close" : "Expand visual"}</button>
      {unavailable ? <VisualUnavailable reason={unavailable} /> : data.sceneType === "mechanism_scene" && current.visual?.type === "mechanism_scene" ? <MechanismSceneVisual scene={current.visual} stage={stage} /> : data.sceneType === "sequence_exchange_scene" && current.visual?.type === "sequence_exchange_scene" ? <SequenceExchangeVisual scene={current.visual} /> : data.sceneType === "ordered_items_scene" && current.visual?.type === "ordered_items_scene" ? <OrderedItemsVisual scene={current.visual} entities={data.entities} /> : data.sceneType === "vector_scene" ? <svg viewBox="0 0 420 250" role="img" aria-label={`${current.title}: ${current.explanation}`}>
        <line x1="35" y1="215" x2="390" y2="215" className="axis" /><line x1="70" y1="235" x2="70" y2="25" className="axis" />
        {vectors.map((vector) => <VectorArrow key={vector.id} vector={vector} />)}
        <text x="78" y="32" className="axis-label">y</text><text x="385" y="232" className="axis-label">x</text>
      </svg> : <VisualUnavailable reason="The selected scene cannot be rendered." />}
      {data.sceneType === "vector_scene" && !unavailable && <div className="step-legend">{data.entities.filter((entity) => !current.activeEntityIds || current.activeEntityIds.includes(entity.id)).map((entity) => <span key={entity.id}><i style={{ background: entity.color ?? "#1d9e75" }} />{entity.label}</span>)}</div>}
    </div>
    <div className="step-copy"><p className="step-count">Step {stage + 1} of {data.stages.length}</p><h3>{current.title}</h3><p>{current.explanation}</p>{current.equation && <code className="step-equation">{current.equation}</code>}{current.notice && <p className="step-notice"><strong>Notice:</strong> {current.notice}</p>}{current.insight && <p className="step-insight"><strong>Insight:</strong> {current.insight}</p>}</div>
    <div className="step-controls"><button type="button" onClick={() => setStage(Math.max(0, stage - 1))} disabled={stage === 0}>Previous</button><button type="button" onClick={() => setStage(Math.min(data.stages.length - 1, stage + 1))} disabled={stage === data.stages.length - 1}>Next</button></div>
    {data.prediction && stage === data.stages.length - 1 && <div className="step-prediction"><h3>Pause and predict</h3><p>{data.prediction.prompt}</p><div className="prediction-options">{data.prediction.options.map((option, index) => <button key={option} type="button" className={choice === index ? "selected" : ""} onClick={() => setChoice(index)}>{option}</button>)}</div>{choice !== null && <p className={`prediction-result ${choice === data.prediction!.answer ? "correct" : ""}`} aria-live="polite">{choice === data.prediction.answer ? "Correct. " : "Not quite. "}{data.prediction.reveal}</p>}</div>}
    {stage === data.stages.length - 1 && <p className="step-conclusion"><strong>General idea:</strong> {data.conclusion}</p>}
  </section>
}
