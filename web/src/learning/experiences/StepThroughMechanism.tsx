import { useState } from "react"

export type MechanismEntity = { id: string; label: string; color?: string }
export type MechanismStage = {
  title: string
  explanation: string
  equation?: string
  activeEntityIds?: string[]
  vectors?: { id: string; x: number; y: number; color?: string; dashed?: boolean; label?: string }[]
}
export type MechanismPrediction = { prompt: string; options: string[]; answer: number; reveal: string }
export type StepThroughMechanismData = {
  learningGoal: string
  entities: MechanismEntity[]
  stages: MechanismStage[]
  prediction?: MechanismPrediction
  conclusion: string
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
      <svg viewBox="0 0 420 250" role="img" aria-label={`${current.title}: ${current.explanation}`}>
        <line x1="35" y1="215" x2="390" y2="215" className="axis" /><line x1="70" y1="235" x2="70" y2="25" className="axis" />
        {vectors.map((vector) => <VectorArrow key={vector.id} vector={vector} />)}
        <text x="78" y="32" className="axis-label">y</text><text x="385" y="232" className="axis-label">x</text>
      </svg>
      <div className="step-legend">{data.entities.filter((entity) => !current.activeEntityIds || current.activeEntityIds.includes(entity.id)).map((entity) => <span key={entity.id}><i style={{ background: entity.color ?? "#1d9e75" }} />{entity.label}</span>)}</div>
    </div>
    <div className="step-copy"><p className="step-count">Step {stage + 1} of {data.stages.length}</p><h3>{current.title}</h3><p>{current.explanation}</p>{current.equation && <code className="step-equation">{current.equation}</code>}</div>
    <div className="step-controls"><button type="button" onClick={() => setStage(Math.max(0, stage - 1))} disabled={stage === 0}>Previous</button><button type="button" onClick={() => setStage(Math.min(data.stages.length - 1, stage + 1))} disabled={stage === data.stages.length - 1}>Next</button></div>
    {data.prediction && stage === data.stages.length - 1 && <div className="step-prediction"><h3>Pause and predict</h3><p>{data.prediction.prompt}</p><div className="prediction-options">{data.prediction.options.map((option, index) => <button key={option} type="button" className={choice === index ? "selected" : ""} onClick={() => setChoice(index)}>{option}</button>)}</div>{choice !== null && <p className={`prediction-result ${choice === data.prediction!.answer ? "correct" : ""}`} aria-live="polite">{choice === data.prediction.answer ? "Correct. " : "Not quite. "}{data.prediction.reveal}</p>}</div>}
    {stage === data.stages.length - 1 && <p className="step-conclusion"><strong>General idea:</strong> {data.conclusion}</p>}
  </section>
}
