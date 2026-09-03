import { useState } from "react"

export type MechanismEntity = { id: string; label: string; color?: string }
export type MechanismStage = {
  title: string
  explanation: string
  equation?: string
  activeEntityIds?: string[]
  vectors?: { id: string; x: number; y: number; color?: string; dashed?: boolean }[]
}
export type MechanismPrediction = { prompt: string; options: string[]; answer: number; reveal: string }
export type StepThroughMechanismData = {
  learningGoal: string
  entities: MechanismEntity[]
  stages: MechanismStage[]
  prediction?: MechanismPrediction
  conclusion: string
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
        {vectors.map((vector) => <line key={vector.id} x1="70" y1="215" x2={70 + vector.x} y2={215 - vector.y} className={`vector ${vector.dashed ? "vector-dashed" : ""}`} stroke={vector.color ?? "#1d9e75"} markerEnd="url(#arrow)" />)}
        <defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="currentColor" /></marker></defs>
        {stage >= 2 && <path d="M70 215 L150 215 L150 165" className="right-angle" />}
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

