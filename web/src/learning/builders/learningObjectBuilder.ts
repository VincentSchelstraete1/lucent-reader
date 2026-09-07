import type { LearningObject } from "../schema/learningObject"
import type { RepresentationType } from "../routing/representationTypes"
import { buildComparisonLearningObject } from "./comparisonBuilder"
import { buildProcessLearningObject } from "./processBuilder"
import { buildCausalLearningObject, buildConceptMapLearningObject, buildHierarchyLearningObject, buildPlainTextLearningObject, buildQuantitativeLearningObject } from "./extendedBuilders"

export function buildLearningObject(type: RepresentationType, sourceText: string): LearningObject | null {
  switch (type) {
    case "process": return buildProcessLearningObject(sourceText)
    case "comparison": return buildComparisonLearningObject(sourceText)
    case "causal": return buildCausalLearningObject(sourceText)
    case "concept_map": return buildConceptMapLearningObject(sourceText)
    case "hierarchy": return buildHierarchyLearningObject(sourceText)
    case "quantitative": return buildQuantitativeLearningObject(sourceText)
    case "plain_text": return buildPlainTextLearningObject(sourceText)
  }
}
