import type { ProcessLearningObject, ProcessStep } from "../schema/learningObject"
import { stableTextId } from "./builderUtils"

const TRANSITION_PREFIX = /^(?:\d+[.)]\s*|step\s+\d+[:.)]?\s*|first,?\s+|next,?\s+|then,?\s+|finally,?\s+|afterward,?\s+)/i

function extractSteps(sourceText: string): ProcessStep[] {
  return sourceText
    .trim()
    .split(/(?<=[.!?])\s+|\s*(?:→|->|=>)\s*|\n+/)
    .map((part) => part.trim().replace(TRANSITION_PREFIX, "").replace(/[.!?]+$/, "").trim())
    .filter(Boolean)
    .map((explanation, index) => ({
      id: `step-${index + 1}`,
      label: explanation.length > 72 ? `${explanation.slice(0, 69)}…` : explanation,
      explanation
    }))
}

export function buildProcessLearningObject(sourceText: string): ProcessLearningObject {
  const normalized = sourceText.trim()
  const steps = extractSteps(normalized)
  if (steps.length < 2) throw new Error("A process needs at least two identifiable steps")
  return {
    id: `process-${stableTextId(normalized)}`,
    type: "process",
    title: "Sequential process",
    learningGoal: "Understand the order and relationship between each step.",
    sourceText: normalized,
    sourceReferences: [],
    interactions: [{ type: "step_focus", targetIds: steps.map((step) => step.id) }],
    steps,
    connections: steps.slice(1).map((step, index) => ({ from: steps[index].id, to: step.id }))
  }
}
