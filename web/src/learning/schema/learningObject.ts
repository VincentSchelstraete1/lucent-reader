import type { RepresentationType } from "../routing/representationTypes"

export type SourceReference = { id: string; label: string; url?: string }
export type LearningInteraction = { type: "step_focus" | "item_compare"; targetIds: string[] }

export interface LearningObjectBase<T extends RepresentationType> {
  id: string
  type: T
  title: string
  learningGoal: string
  sourceText: string
  sourceReferences: SourceReference[]
  interactions: LearningInteraction[]
}

export interface ProcessStep {
  id: string
  label: string
  explanation: string
}

export interface ProcessConnection {
  from: string
  to: string
}

export interface ProcessLearningObject extends LearningObjectBase<"process"> {
  steps: ProcessStep[]
  connections: ProcessConnection[]
}

export interface ComparisonAttribute {
  label: string
  value: string
}

export interface ComparisonItem {
  id: string
  name: string
  attributes: ComparisonAttribute[]
}

export interface ComparisonLearningObject extends LearningObjectBase<"comparison"> {
  items: ComparisonItem[]
  similarities?: string[]
  differences?: string[]
}

// This union deliberately contains only implemented semantic objects. The
// routing taxonomy is broader, and future concrete objects extend this union.
export type LearningObject = ProcessLearningObject | ComparisonLearningObject
