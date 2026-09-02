import type { RepresentationType } from "./representationTypes"

export const ROUTER_CONFIG = {
  structuredThreshold: 0.42,
  process: {
    transitionWeight: 0.16,
    temporalWeight: 0.08,
    repeatedTransitionBonus: 0.18,
    explicitPhraseWeight: 0.3,
    orderedListWeight: 0.5,
    arrowWeight: 0.3
  },
  comparison: { termWeight: 0.44, parallelLanguageWeight: 0.2 },
  causal: { termWeight: 0.44 },
  conceptMap: { relationWeight: 0.35, definitionNetworkWeight: 0.2 },
  hierarchy: { containmentWeight: 0.5, enumerationWeight: 0.22, listWeight: 0.35 },
  quantitative: { equationWeight: 0.38, percentageWeight: 0.35, unitWeight: 0.28, numericRelationWeight: 0.3 }
} as const

// Explicit ordering makes equal-score routing stable and easy to revisit.
export const STRUCTURED_TYPE_PRIORITY: Exclude<RepresentationType, "plain_text">[] = [
  "process", "comparison", "causal", "hierarchy", "quantitative", "concept_map"
]
