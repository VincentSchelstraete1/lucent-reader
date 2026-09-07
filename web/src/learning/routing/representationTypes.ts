export const REPRESENTATION_TYPES = [
  "plain_text",
  "process",
  "comparison",
  "causal",
  "concept_map",
  "hierarchy",
  "quantitative"
] as const

export type RepresentationType = (typeof REPRESENTATION_TYPES)[number]
export type RepresentationScores = Record<RepresentationType, number>

export type RepresentationRoute = {
  type: RepresentationType
  confidence: number
  scores: RepresentationScores
  reasons: string[]
}
