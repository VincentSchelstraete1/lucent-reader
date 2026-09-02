import type { LearningObject } from "../schema/learningObject"
import { ComparisonRenderer } from "./ComparisonRenderer"
import { ProcessRenderer } from "./ProcessRenderer"

export function rendererKindFor(object: LearningObject): LearningObject["type"] {
  return object.type
}

export function LearningObjectRenderer({ object }: { object: LearningObject }) {
  switch (object.type) {
    case "process": return <ProcessRenderer object={object} />
    case "comparison": return <ComparisonRenderer object={object} />
  }
}
