import { ROUTER_CONFIG, ROUTER_MARKERS, STRUCTURED_TYPE_PRIORITY } from "./scoringConfig"
import { REPRESENTATION_TYPES, type RepresentationRoute, type RepresentationScores, type RepresentationType } from "./representationTypes"

type ScoredSignal = { score: number; reasons: string[] }

const clamp = (value: number) => Math.max(0, Math.min(1, value))
const rounded = (value: number) => {
  const scale = 10 ** ROUTER_CONFIG.scorePrecision
  return Math.round(clamp(value) * scale) / scale
}
const matches = (text: string, pattern: RegExp) => text.match(pattern)?.length ?? 0
const commaSeparatedItems = (text: string) => matches(text, /,/g) >= 2

function processScore(text: string): ScoredSignal {
  const markers = ROUTER_MARKERS.process
  const config = ROUTER_CONFIG.process
  const transitions = matches(text, markers.transitions)
  const temporal = matches(text, markers.temporal)
  const explicit = markers.explicit.test(text)
  const orderedItems = matches(text, markers.orderedItem)
  const arrows = markers.arrow.test(text)
  let score = Math.min(config.transitionCap, transitions * config.transitionWeight)
  score += Math.min(config.temporalCap, temporal * config.temporalWeight)
  if (transitions >= 2) score += config.repeatedTransitionBonus
  if (explicit) score += config.explicitPhraseWeight
  if (orderedItems >= 2) score += config.orderedListWeight
  else if (orderedItems === 1) score += config.singleOrderedItemWeight
  if (arrows) score += config.arrowWeight
  return {
    score: rounded(score),
    reasons: [
      ...(transitions ? ["contains sequential transition words"] : []),
      ...(temporal || explicit ? ["contains ordered procedural language"] : []),
      ...(orderedItems ? ["contains numbered or ordered steps"] : []),
      ...(arrows ? ["contains explicit progression arrows"] : [])
    ]
  }
}

function comparisonScore(text: string): ScoredSignal {
  const markers = ROUTER_MARKERS.comparison
  const config = ROUTER_CONFIG.comparison
  const explicitTerms = markers.metaLanguage.test(text) ? 0 : matches(text, markers.explicit)
  const parallel = markers.parallel.test(text)
  const comparative = markers.comparative.test(text)
  return {
    score: rounded(explicitTerms * config.explicitTermWeight
      + (parallel ? config.parallelLanguageWeight : 0)
      + (comparative ? config.comparativeFormWeight : 0)),
    reasons: [
      ...(explicitTerms ? ["contains explicit comparison language"] : []),
      ...(parallel ? ["contrasts parallel alternatives"] : []),
      ...(comparative ? ["uses a comparative relationship"] : [])
    ]
  }
}

function causalScore(text: string): ScoredSignal {
  const markers = ROUTER_MARKERS.causal
  const config = ROUTER_CONFIG.causal
  const directional = matches(text, markers.directional)
  const connectives = markers.metaLanguage.test(text) ? 0 : matches(text, markers.connective)
  const signalCount = directional + connectives
  const hasTwoClauseConnection = connectives > 0 && /[,;]|\b(?:which|so)\b/i.test(text)
  let score = directional * config.directionalWeight + connectives * config.connectiveWeight
  if (hasTwoClauseConnection) score += config.twoClauseBonus
  if (signalCount >= 2) score += config.repeatedSignalBonus
  return {
    score: rounded(score),
    reasons: [
      ...(directional ? ["states a directional cause-and-effect relationship"] : []),
      ...(connectives ? ["connects a cause with its consequence"] : []),
      ...(signalCount >= 2 ? ["contains multiple reinforcing causal signals"] : [])
    ]
  }
}

function conceptMapScore(text: string): ScoredSignal {
  const markers = ROUTER_MARKERS.conceptMap
  const config = ROUTER_CONFIG.conceptMap
  const relations = matches(text, markers.relation)
  const hubs = matches(text, markers.hub)
  const entityNetwork = (relations > 0 || hubs > 0) && commaSeparatedItems(text)
  const combinedNetwork = relations + hubs >= 2 || (relations > 0 && entityNetwork)
  let score = relations * config.relationWeight + hubs * config.hubWeight
  if (entityNetwork) score += config.entityNetworkWeight
  if (combinedNetwork) score += config.networkCombinationBonus
  return {
    score: rounded(score),
    reasons: [
      ...(relations ? ["links concepts with explicit relationships"] : []),
      ...(hubs ? ["describes a concept involving neighboring concepts"] : []),
      ...(entityNetwork ? ["connects a network of multiple named concepts"] : [])
    ]
  }
}

function hierarchyScore(text: string): ScoredSignal {
  const markers = ROUTER_MARKERS.hierarchy
  const config = ROUTER_CONFIG.hierarchy
  const strongContainment = matches(text, markers.strongContainment)
  const weakContainment = matches(text, markers.weakContainment)
  const listItems = matches(text, markers.listItem)
  const nestedList = markers.nestedListItem.test(text)
  const enumeration = (strongContainment + weakContainment > 0)
    && (commaSeparatedItems(text) || /:\s*[^.!?]+(?:,|;)/.test(text))
  let score = strongContainment * config.strongContainmentWeight + weakContainment * config.weakContainmentWeight
  if (enumeration) score += config.groupedEnumerationWeight
  if (listItems >= 3) score += config.flatListWeight
  if (nestedList) score += config.nestedListBonus
  return {
    score: rounded(score),
    reasons: [
      ...(strongContainment || weakContainment ? ["contains explicit part-to-whole language"] : []),
      ...(enumeration ? ["groups several members under a parent concept"] : []),
      ...(listItems >= 3 ? ["contains a structured list of members"] : []),
      ...(nestedList ? ["contains nested hierarchy levels"] : [])
    ]
  }
}

function quantitativeScore(text: string): ScoredSignal {
  const markers = ROUTER_MARKERS.quantitative
  const config = ROUTER_CONFIG.quantitative
  const equation = markers.symbolicEquation.test(text)
  const verbalRelationship = markers.verbalRelationship.test(text)
  const percentages = matches(text, markers.percentage)
  const units = matches(text, markers.unit)
  const quantities = matches(text, markers.quantity)
  let score = equation ? config.symbolicEquationWeight : 0
  if (verbalRelationship) score += config.verbalRelationshipWeight
  if (percentages) score += config.percentageWeight
  if (units) score += config.unitWeight
  if (quantities >= 2) score += config.multipleQuantityWeight
  return {
    score: rounded(score),
    reasons: [
      ...(equation ? ["contains a symbolic mathematical relationship"] : []),
      ...(verbalRelationship ? ["describes a quantitative relationship in words"] : []),
      ...(percentages || units ? ["contains explicit quantities or units"] : []),
      ...(quantities >= 2 ? ["relates multiple numeric values"] : [])
    ]
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
  const plainConfig = ROUTER_CONFIG.plainText
  const plainScore = strongestScore < ROUTER_CONFIG.structuredThreshold
    ? rounded(Math.max(plainConfig.minimumConfidence, plainConfig.baseConfidence - strongestScore * plainConfig.competingSignalPenalty))
    : plainConfig.structuredContextScore
  const scores = Object.fromEntries(
    REPRESENTATION_TYPES.map((type) => [type, type === "plain_text" ? plainScore : signals[type].score])
  ) as RepresentationScores
  if (!text || strongestScore < ROUTER_CONFIG.structuredThreshold) {
    return { type: "plain_text", confidence: plainScore, scores, reasons: ["no strong structural signals detected"] }
  }
  return { type: strongest, confidence: strongestScore, scores, reasons: signals[strongest].reasons }
}

// Alias used by the reproducible experiment harness to name the frozen baseline.
export const routeRepresentationBaseline = routeRepresentation
