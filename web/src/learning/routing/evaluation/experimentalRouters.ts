import { ROUTER_CONFIG, STRUCTURED_TYPE_PRIORITY } from "../scoringConfig"
import { routeRepresentationBaseline } from "../representationRouter"
import { REPRESENTATION_TYPES, type RepresentationRoute, type RepresentationScores, type RepresentationType } from "../representationTypes"

export type ExperimentProfile = {
  lexicalExpansion?: boolean
  structuralPatterns?: boolean
  classThresholds?: boolean
  ambiguitySafeguards?: boolean
}

type StructuredType = Exclude<RepresentationType, "plain_text">
type AddedEvidence = { score: number; reasons: string[] }

const rounded = (value: number) => Math.round(Math.max(0, Math.min(1, value)) * 100) / 100
const count = (text: string, pattern: RegExp) => text.match(pattern)?.length ?? 0

const emptyEvidence = (): Record<StructuredType, AddedEvidence> => ({
  process: { score: 0, reasons: [] },
  comparison: { score: 0, reasons: [] },
  causal: { score: 0, reasons: [] },
  concept_map: { score: 0, reasons: [] },
  hierarchy: { score: 0, reasons: [] },
  quantitative: { score: 0, reasons: [] }
})

function lexicalEvidence(text: string, safeguards = false): Record<StructuredType, AddedEvidence> {
  const evidence = emptyEvidence()

  const processNoun = /\b(?:workflow|sequence|life cycle|pipeline|path of|stages? of)\b/i.test(text)
  if (processNoun) evidence.process = { score: 0.3, reasons: ["names an ordered process structure"] }

  const contrast = count(text, /\b(?:while|in contrast to|by contrast|instead|but only)\b/gi)
  const explicitContrast = safeguards && /\b(?:in contrast to|by contrast)\b/i.test(text)
  if (contrast) evidence.comparison = {
    score: contrast * 0.44 + (explicitContrast ? 0.5 : 0),
    reasons: ["uses an additional explicit contrast marker"]
  }

  const causalPattern = safeguards
    ? /\b(?:causing|leading to|resulting in|making|enabling|raises?|reduces?|increases?|reverses?|strengthens?|impairs?)\b/gi
    : /\b(?:causing|leading to|resulting in|making|enabling|raises?|lowers?|reduces?|increases?|reverses?|strengthens?|impairs?)\b/gi
  const causalDirection = count(text, causalPattern)
  const causalConnector = count(text, /\b(?:so|since)\b/gi)
  evidence.causal = {
    score: causalDirection * 0.46 + causalConnector * 0.34 + (causalConnector && /[,;]/.test(text) ? 0.14 : 0),
    reasons: [
      ...(causalDirection ? ["uses an additional directional effect verb"] : []),
      ...(causalConnector ? ["uses an additional causal connector"] : [])
    ]
  }

  const networkTerms = count(text, /\b(?:links?|linked|connects?|connected|coordinates?|coordinated|interconnected|working together|brings? together|emerges? from)\b/gi)
  const networkList = networkTerms > 0 && count(text, /,/g) >= 2
  evidence.concept_map = {
    score: (safeguards ? Math.min(1, networkTerms) : networkTerms) * 0.34 + (networkList ? 0.2 : 0),
    reasons: [
      ...(networkTerms ? ["uses an additional concept-relationship marker"] : []),
      ...(networkList ? ["relates a multi-entity concept network"] : [])
    ]
  }

  const taxonomyTerms = count(text, /\b(?:classified as|main divisions?|market structures?|occup(?:y|ies) layers?|fall into|comprises?|branching into|major components?|grouped as)\b/gi)
  evidence.hierarchy = {
    score: taxonomyTerms * 0.46,
    reasons: taxonomyTerms ? ["uses an additional taxonomy or containment marker"] : []
  }

  const expandedUnit = /\b\d[\d,]*(?:\.\d+)?\s*(?:beats?|requests?|words?|soldiers?|people|participants?)\s+per\s+(?:minute|second|hour|day)\b/i.test(text)
  const numericChange = /\b(?:from|between)\s+\d[\d,]*(?:\.\d+)?[^.!?]{0,45}\b(?:to|and)\s+\d[\d,]*(?:\.\d+)?\b/i.test(text)
  const interpretedEquation = safeguards && /(?:=|\s[+×*÷]\s)/.test(text) && /\b(?:so|therefore|thus|hence)\b/i.test(text)
  evidence.quantitative = {
    score: (expandedUnit ? 0.26 : 0) + (numericChange ? 0.3 : 0) + (interpretedEquation ? 0.14 : 0),
    reasons: [
      ...(expandedUnit ? ["contains an expanded rate unit"] : []),
      ...(numericChange ? ["states a numeric range or change"] : []),
      ...(interpretedEquation ? ["interprets an explicit equation"] : [])
    ]
  }

  return evidence
}

function structuralEvidence(text: string, safeguards = false): Record<StructuredType, AddedEvidence> {
  const evidence = emptyEvidence()
  const proceduralList = /\b(?:to|how to)\s+\w+[^:]{0,100}:/i.test(text) && count(text, /;/g) >= 2
  if (proceduralList) evidence.process = { score: 0.5, reasons: ["uses a procedural lead-in followed by ordered clauses"] }

  const pairedLabels = /(?:^|[.!?]\s+)[A-Z][^.:]{1,30}:[^.!?]+[.!?]\s+[A-Z][^.:]{1,30}:/m.test(text)
  if (pairedLabels) evidence.comparison = { score: 0.44, reasons: ["presents parallel labeled alternatives"] }

  const participialEffect = /[,;]\s*(?:causing|making|enabling|producing|leaving)\b/i.test(text)
  if (participialEffect) evidence.causal = { score: 0.46, reasons: ["uses a result clause attached to an initiating event"] }

  const networkEnumeration = !safeguards && /\b(?:system|model|framework|foundation|network)\b[^.!?]{0,80}(?:,\s*[^,]+){3,}/i.test(text)
    && /\b(?:together|relationship|interconnected|coordinate|link)\w*\b/i.test(text)
  if (networkEnumeration) evidence.concept_map = { score: 0.44, reasons: ["describes several entities as an interacting network"] }

  const categoryColon = /\b(?:types?|categories|divisions?|layers?|components?|structures?|forms?|groups?|levels?|sources?)\b[^.!?]{0,45}:\s*[^.!?]+(?:,|;|\n-)/i.test(text)
  if (categoryColon) evidence.hierarchy = { score: 0.46, reasons: ["uses a category heading followed by grouped members"] }

  const formulaNarration = /\b(?:is|equals?)\s+(?:one half\s+)?(?:the\s+)?\w+(?:\s+\w+){0,4}\s+(?:divided by|times|minus|plus)\b/i.test(text)
  if (formulaNarration) evidence.quantitative = { score: 0.46, reasons: ["narrates a formula relationship"] }

  return evidence
}

const thresholds: Record<StructuredType, number> = {
  process: 0.32,
  comparison: 0.34,
  causal: 0.34,
  concept_map: 0.34,
  hierarchy: 0.4,
  quantitative: 0.42
}

export function createExperimentalRouter(profile: ExperimentProfile) {
  return (sourceText: string): RepresentationRoute => {
    const text = sourceText.trim()
    const baseline = routeRepresentationBaseline(text)
    const scores = { ...baseline.scores }
    const reasons: Partial<Record<StructuredType, string[]>> = {}
    const additions = [
      ...(profile.lexicalExpansion ? [lexicalEvidence(text, profile.ambiguitySafeguards)] : []),
      ...(profile.structuralPatterns ? [structuralEvidence(text, profile.ambiguitySafeguards)] : [])
    ]

    for (const type of STRUCTURED_TYPE_PRIORITY) {
      const addedScore = additions.reduce((sum, evidence) => sum + evidence[type].score, 0)
      scores[type] = rounded(scores[type] + addedScore)
      reasons[type] = additions.flatMap((evidence) => evidence[type].reasons)
    }

    let strongest = STRUCTURED_TYPE_PRIORITY[0]
    for (const type of STRUCTURED_TYPE_PRIORITY.slice(1)) {
      if (scores[type] > scores[strongest]) strongest = type
    }
    const threshold = profile.classThresholds ? thresholds[strongest] : ROUTER_CONFIG.structuredThreshold
    const strongestScore = scores[strongest]
    const plainConfig = ROUTER_CONFIG.plainText
    const plainScore = strongestScore < threshold
      ? rounded(Math.max(plainConfig.minimumConfidence, plainConfig.baseConfidence - strongestScore * plainConfig.competingSignalPenalty))
      : plainConfig.structuredContextScore
    scores.plain_text = plainScore

    if (!text || strongestScore < threshold) {
      return { type: "plain_text", confidence: plainScore, scores: scores as RepresentationScores, reasons: ["no strong structural signals detected"] }
    }
    return {
      type: strongest,
      confidence: strongestScore,
      scores: Object.fromEntries(REPRESENTATION_TYPES.map((type) => [type, scores[type]])) as RepresentationScores,
      reasons: reasons[strongest]?.length ? reasons[strongest]! : baseline.reasons
    }
  }
}

export const DEVELOPMENT_CANDIDATES = {
  "Candidate A — lexical coverage": createExperimentalRouter({ lexicalExpansion: true }),
  "Candidate B — class thresholds": createExperimentalRouter({ classThresholds: true }),
  "Candidate C — structural patterns": createExperimentalRouter({ structuralPatterns: true }),
  "Candidate A+C": createExperimentalRouter({ lexicalExpansion: true, structuralPatterns: true }),
  "Candidate A+B+C": createExperimentalRouter({ lexicalExpansion: true, structuralPatterns: true, classThresholds: true }),
  "Candidate D — guarded A+C": createExperimentalRouter({ lexicalExpansion: true, structuralPatterns: true, ambiguitySafeguards: true })
} as const
