import type { LearningObject } from "../schema/learningObject"
import type { RepresentationType } from "../routing/representationTypes"
import { buildComparisonLearningObject } from "./comparisonBuilder"
import { buildProcessLearningObject } from "./processBuilder"

export function buildLearningObject(type: RepresentationType, sourceText: string): LearningObject | null {
  switch (type) {
    case "process": return buildProcessLearningObject(sourceText)
    case "comparison": return buildComparisonLearningObject(sourceText)
    default: return null
  }
}
