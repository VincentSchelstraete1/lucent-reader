import type { LearningObject } from "../schema/learningObject"
import { ComparisonRenderer } from "./ComparisonRenderer"
import { ProcessRenderer } from "./ProcessRenderer"
import { CausalRenderer, ConceptMapRenderer, HierarchyRenderer, PlainTextRenderer, QuantitativeRenderer } from "./ExtendedRenderers"

export function rendererKindFor(object: LearningObject): LearningObject["type"] {
  return object.type
}

export function LearningObjectRenderer({ object }: { object: LearningObject }) {
  switch (object.type) {
    case "process": return <ProcessRenderer object={object} />
    case "comparison": return <ComparisonRenderer object={object} />
    case "causal": return <CausalRenderer object={object} />
    case "concept_map": return <ConceptMapRenderer object={object} />
    case "hierarchy": return <HierarchyRenderer object={object} />
    case "quantitative": return <QuantitativeRenderer object={object} />
    case "plain_text": return <PlainTextRenderer object={object} />
  }
}
