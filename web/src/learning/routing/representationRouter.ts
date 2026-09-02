import { ROUTER_CONFIG, STRUCTURED_TYPE_PRIORITY } from "./scoringConfig"
import { REPRESENTATION_TYPES, type RepresentationRoute, type RepresentationScores, type RepresentationType } from "./representationTypes"

type ScoredSignal = { score: number; reasons: string[] }
const clamp = (value: number) => Math.max(0, Math.min(1, value))
const rounded = (value: number) => Math.round(clamp(value) * 100) / 100
const matches = (text: string, pattern: RegExp) => text.match(pattern)?.length ?? 0

function processScore(text: string): ScoredSignal {
  const transitions = matches(text, /\b(first|next|then|finally|afterward|subsequently)\b/gi)
  const temporal = matches(text, /\b(before|after|once|when)\b/gi)
  const explicit = /\b(the process begins|followed by|the process ends|in sequence)\b/i.test(text)
  const orderedItems = matches(text, /^\s*(?:\d+[.)]|step\s+\d+[:.)]?)[ \t]+/gim)
  const arrows = /(?:→|->|=>)/.test(text)
  let score = Math.min(0.64, transitions * ROUTER_CONFIG.process.transitionWeight)
  score += Math.min(0.24, temporal * ROUTER_CONFIG.process.temporalWeight)
  if (transitions >= 2) score += ROUTER_CONFIG.process.repeatedTransitionBonus
  if (explicit) score += ROUTER_CONFIG.process.explicitPhraseWeight
  if (orderedItems >= 2) score += ROUTER_CONFIG.process.orderedListWeight
  else if (orderedItems === 1) score += 0.2
  if (arrows) score += ROUTER_CONFIG.process.arrowWeight
  const reasons: string[] = []
  if (transitions) reasons.push("contains sequential transition words")
  if (temporal || explicit) reasons.push("contains ordered procedural language")
  if (orderedItems) reasons.push("contains numbered or ordered steps")
  if (arrows) reasons.push("contains explicit progression arrows")
  return { score: rounded(score), reasons }
}

function comparisonScore(text: string): ScoredSignal {
  const terms = matches(text, /\b(vs\.?|versus|whereas|unlike|compared (?:with|to)|similarities|differences)\b/gi)
  const parallel = /\b(?:both|either)\b.*\b(?:and|or)\b/i.test(text) || /\b\w+\b.*\bwhereas\b.*\b\w+\b/i.test(text)
  const score = terms * ROUTER_CONFIG.comparison.termWeight + (parallel ? ROUTER_CONFIG.comparison.parallelLanguageWeight : 0)
  return { score: rounded(score), reasons: [...(terms ? ["contains explicit comparison language"] : []), ...(parallel ? ["contrasts parallel alternatives"] : [])] }
}

function causalScore(text: string): ScoredSignal {
  const terms = matches(text, /\b(because|therefore|causes?|leads? to|results? in|due to|consequently|effects?)\b/gi)
  return { score: rounded(terms * ROUTER_CONFIG.causal.termWeight), reasons: terms ? ["contains cause-and-effect language"] : [] }
}

function conceptMapScore(text: string): ScoredSignal {
  const relations = matches(text, /\b(related to|associated with|connected to|depends on|interacts with)\b/gi)
  const definitionNetwork = /\b(?:is|are|refers to)\b/i.test(text) && matches(text, /,/g) >= 2
  return {
    score: rounded(relations * ROUTER_CONFIG.conceptMap.relationWeight + (definitionNetwork ? ROUTER_CONFIG.conceptMap.definitionNetworkWeight : 0)),
    reasons: [...(relations ? ["links multiple related concepts"] : []), ...(definitionNetwork ? ["defines a concept through neighboring concepts"] : [])]
  }
}

function hierarchyScore(text: string): ScoredSignal {
  const containment = matches(text, /\b(consists of|contains|includes|types of|categories of|parts of|components of)\b/gi)
  const enumeration = containment > 0 && matches(text, /,/g) >= 2
  const listItems = matches(text, /^\s*(?:[-*]|\d+[.)])[ \t]+/gim)
  const nestedList = /^\s{2,}(?:[-*]|\d+[.)])[ \t]+/m.test(text)
  let score = containment * ROUTER_CONFIG.hierarchy.containmentWeight
  if (enumeration) score += ROUTER_CONFIG.hierarchy.enumerationWeight
  if (listItems >= 3) score += ROUTER_CONFIG.hierarchy.listWeight
  if (nestedList) score += 0.2
  return {
    score: rounded(score),
    reasons: [...(containment ? ["contains explicit part-to-whole language"] : []), ...(enumeration || listItems >= 3 ? ["contains grouped or nested items"] : [])]
  }
}

function quantitativeScore(text: string): ScoredSignal {
  const equation = /(?:=|\+|−|-|×|\*|÷|\/|≤|≥)/.test(text)
  const percentage = /\b\d+(?:\.\d+)?\s*%/.test(text)
  const units = /\b\d+(?:\.\d+)?\s*(?:ms|s|hz|khz|mhz|ghz|kb|mb|gb|bytes?|meters?|kg|°c)\b/i.test(text)
  const relationship = /\b(average|rate|ratio|proportional|equals?|sum|difference|probability)\b/i.test(text)
  let score = equation ? ROUTER_CONFIG.quantitative.equationWeight : 0
  if (percentage) score += ROUTER_CONFIG.quantitative.percentageWeight
  if (units) score += ROUTER_CONFIG.quantitative.unitWeight
  if (relationship) score += ROUTER_CONFIG.quantitative.numericRelationWeight
  return {
    score: rounded(score),
    reasons: [...(equation ? ["contains a mathematical relationship"] : []), ...(percentage || units ? ["contains quantities or units"] : []), ...(relationship ? ["describes a numeric relationship"] : [])]
  }
}

export function routeRepresentation(sourceText: string): RepresentationRoute {
  const text = sourceText.trim()
  const signals: Record<Exclude<RepresentationType, "plain_text">, ScoredSignal> = {
    process: processScore(text), comparison: comparisonScore(text), causal: causalScore(text),
    concept_map: conceptMapScore(text), hierarchy: hierarchyScore(text), quantitative: quantitativeScore(text)
  }
  let strongest = STRUCTURED_TYPE_PRIORITY[0]
  for (const type of STRUCTURED_TYPE_PRIORITY.slice(1)) {
    if (signals[type].score > signals[strongest].score) strongest = type
  }
  const strongestScore = signals[strongest].score
  const plainScore = rounded(strongestScore < ROUTER_CONFIG.structuredThreshold ? 0.75 - strongestScore * 0.25 : 0.12)
  const scores = Object.fromEntries(REPRESENTATION_TYPES.map((type) => [type, type === "plain_text" ? plainScore : signals[type].score])) as RepresentationScores
  if (!text || strongestScore < ROUTER_CONFIG.structuredThreshold) {
    return { type: "plain_text", confidence: plainScore, scores, reasons: ["no strong structural signals detected"] }
  }
  return { type: strongest, confidence: strongestScore, scores, reasons: signals[strongest].reasons }
}
