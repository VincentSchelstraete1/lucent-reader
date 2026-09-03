import { useState } from "react"

export type MechanismEntity = { id: string; label: string; color?: string }
export type MechanismStage = {
  title: string
  explanation: string
  equation?: string
  activeEntityIds?: string[]
  vectors?: { id: string; x: number; y: number; color?: string; dashed?: boolean; label?: string }[]
  visual?: StageVisual
}
export type SequenceExchangeScene = { type: "sequence_exchange_scene"; actors: { id: string; label: string }[]; messages: { id: string; sender: string; receiver: string; label: string; explanation?: string | null }[]; visibleMessageIds: string[]; emphasizedMessageId?: string | null }
export type VectorScene = { type: "vector_scene"; activeEntityIds: string[] }
export type StageVisual = SequenceExchangeScene | VectorScene
export type MechanismPrediction = { prompt: string; options: string[]; answer: number; reveal: string }
export type StepThroughMechanismData = {
  learningGoal: string
  entities: MechanismEntity[]
  stages: MechanismStage[]
  prediction?: MechanismPrediction
  conclusion: string
}

export type GeneratedStepThroughMechanism = {
  type: "step_through_mechanism"
  title: string
  learningGoal: string
  entities: Array<{ id: string; label: string; color?: string | null }>
  stages: Array<{ title: string; explanation: string; stateChanges: Array<{ entityId: string; change: string; why?: string | null }>; equation?: string | null; activeEntityIds: string[]; visual?: StageVisual | null }>
  prediction?: MechanismPrediction | null
  conclusion: string
}

export function generatedMechanismToRendererData(mechanism: GeneratedStepThroughMechanism): StepThroughMechanismData {
  return {
    learningGoal: mechanism.learningGoal,
    entities: mechanism.entities.map((entity) => ({ ...entity, color: entity.color ?? undefined })),
    stages: mechanism.stages.map((stage) => ({
      title: stage.title,
      explanation: stage.explanation,
      equation: stage.equation ?? undefined,
      activeEntityIds: stage.activeEntityIds,
      visual: stage.visual ?? undefined,
    })),
    prediction: mechanism.prediction ?? undefined,
    conclusion: mechanism.conclusion,
  }
}

function SequenceExchangeVisual({ scene }: { scene: SequenceExchangeScene }) {
  const actorX = (index: number) => 120 + index * 180
  const actorIndex = new Map(scene.actors.map((actor, index) => [actor.id, index]))
  return <svg viewBox="0 0 420 250" role="img" aria-label="Sequence exchange diagram">
    {scene.actors.slice(0, 2).map((actor, index) => <g key={actor.id}><rect x={actorX(index) - 48} y="12" width="96" height="30" rx="8" fill="#fbfaf6" stroke="#58735d" strokeWidth="2" /><text x={actorX(index)} y="32" textAnchor="middle" className="vector-label">{actor.label}</text><line x1={actorX(index)} y1="48" x2={actorX(index)} y2="228" className="axis" /></g>)}
    {scene.messages.map((message, index) => {
      if (!scene.visibleMessageIds.includes(message.id)) return null
      const from = actorIndex.get(message.sender), to = actorIndex.get(message.receiver)
      if (from === undefined || to === undefined) return null
      const y = 78 + index * 48
      const x1 = actorX(from), x2 = actorX(to), direction = x2 >= x1 ? 1 : -1
      const tip = x2 - direction * 2
      const head = `${tip},${y} ${tip - direction * 10},${y - 5} ${tip - direction * 10},${y + 5}`
      const emphasized = scene.emphasizedMessageId === message.id
      return <g key={message.id} className={emphasized ? "sequence-message sequence-message-emphasized" : "sequence-message"}><line x1={x1} y1={y} x2={tip} y2={y} stroke="#58735d" strokeWidth={emphasized ? 3 : 2} /><polygon points={head} fill="#58735d" /><text x={(x1 + x2) / 2} y={y - 9} textAnchor="middle" className="sequence-message-label">{message.label}</text></g>
    })}
    <text x="24" y="224" className="axis-label">time ↓</text>
  </svg>
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

export function StepThroughMechanism({ data }: { data: StepThroughMechanismData }) {
  const [stage, setStage] = useState(0)
  const [choice, setChoice] = useState<number | null>(null)
  const current = data.stages[stage]
  const vectors = current.vectors ?? []
  return <section className="step-mechanism" aria-label={data.learningGoal}>
    <p className="step-goal">Learning goal: {data.learningGoal}</p>
    <div className="step-visual" aria-live="polite">
      {current.visual?.type === "sequence_exchange_scene" ? <SequenceExchangeVisual scene={current.visual} /> : <svg viewBox="0 0 420 250" role="img" aria-label={`${current.title}: ${current.explanation}`}>
        <line x1="35" y1="215" x2="390" y2="215" className="axis" /><line x1="70" y1="235" x2="70" y2="25" className="axis" />
        {vectors.map((vector) => <VectorArrow key={vector.id} vector={vector} />)}
        {!vectors.length && (current.activeEntityIds ?? data.entities.map((entity) => entity.id)).slice(0, 4).map((entityId, index, activeIds) => {
          const entity = data.entities.find((item) => item.id === entityId)
          if (!entity) return null
          const x = 105 + index * 92
          return <g key={entity.id}><rect x={x - 38} y="105" width="76" height="40" rx="10" fill="#fbfaf6" stroke={entity.color ?? "#58735d"} strokeWidth="2" /><text x={x} y="129" textAnchor="middle" className="vector-label">{entity.label}</text>{index < activeIds.length - 1 && <path d={`M${x + 39} 125 L${x + 53} 125`} stroke="#58735d" strokeWidth="2" markerEnd="none" />}</g>
        })}
        <text x="78" y="32" className="axis-label">y</text><text x="385" y="232" className="axis-label">x</text>
      </svg>}
      <div className="step-legend">{data.entities.filter((entity) => !current.activeEntityIds || current.activeEntityIds.includes(entity.id)).map((entity) => <span key={entity.id}><i style={{ background: entity.color ?? "#1d9e75" }} />{entity.label}</span>)}</div>
    </div>
    <div className="step-copy"><p className="step-count">Step {stage + 1} of {data.stages.length}</p><h3>{current.title}</h3><p>{current.explanation}</p>{current.equation && <code className="step-equation">{current.equation}</code>}</div>
    <div className="step-controls"><button type="button" onClick={() => setStage(Math.max(0, stage - 1))} disabled={stage === 0}>Previous</button><button type="button" onClick={() => setStage(Math.min(data.stages.length - 1, stage + 1))} disabled={stage === data.stages.length - 1}>Next</button></div>
    {data.prediction && stage === data.stages.length - 1 && <div className="step-prediction"><h3>Pause and predict</h3><p>{data.prediction.prompt}</p><div className="prediction-options">{data.prediction.options.map((option, index) => <button key={option} type="button" className={choice === index ? "selected" : ""} onClick={() => setChoice(index)}>{option}</button>)}</div>{choice !== null && <p className={`prediction-result ${choice === data.prediction!.answer ? "correct" : ""}`} aria-live="polite">{choice === data.prediction.answer ? "Correct. " : "Not quite. "}{data.prediction.reveal}</p>}</div>}
    {stage === data.stages.length - 1 && <p className="step-conclusion"><strong>General idea:</strong> {data.conclusion}</p>}
  </section>
}
