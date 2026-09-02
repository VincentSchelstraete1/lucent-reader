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

export interface CausalNode { id: string; label: string; explanation?: string }
export interface CausalEdge { from: string; to: string; label?: string }
export interface CausalLearningObject extends LearningObjectBase<"causal"> { nodes: CausalNode[]; edges: CausalEdge[] }

export interface ConceptMapNode { id: string; label: string; definition?: string }
export interface ConceptMapRelationship { from: string; to: string; label: string }
export interface ConceptMapLearningObject extends LearningObjectBase<"concept_map"> { nodes: ConceptMapNode[]; relationships: ConceptMapRelationship[] }

export interface HierarchyNode { id: string; label: string; children?: HierarchyNode[] }
export interface HierarchyLearningObject extends LearningObjectBase<"hierarchy"> { root: HierarchyNode }

export interface QuantitativeVariable { id: string; name: string; value?: string; unit?: string; explanation?: string }
export interface QuantitativeRelationship { expression: string; explanation?: string }
export interface QuantitativeLearningObject extends LearningObjectBase<"quantitative"> { variables: QuantitativeVariable[]; relationships: QuantitativeRelationship[] }

export interface PlainTextLearningObject extends LearningObjectBase<"plain_text"> { paragraphs: string[]; keyPoints?: string[]; definitions?: Array<{ term: string; meaning: string }> }

export type LearningObject = ProcessLearningObject | ComparisonLearningObject | CausalLearningObject | ConceptMapLearningObject | HierarchyLearningObject | QuantitativeLearningObject | PlainTextLearningObject
