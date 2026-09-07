import type { RepresentationType } from "./representationTypes"

export const ROUTER_CONFIG = {
  structuredThreshold: 0.42,
  scorePrecision: 2,
  plainText: { baseConfidence: 0.76, competingSignalPenalty: 0.3, structuredContextScore: 0.12, minimumConfidence: 0.5 },
  process: {
    transitionWeight: 0.16, transitionCap: 0.64, temporalWeight: 0.08, temporalCap: 0.24,
    repeatedTransitionBonus: 0.18, explicitPhraseWeight: 0.44, orderedListWeight: 0.5,
    singleOrderedItemWeight: 0.2, arrowWeight: 0.44
  },
  comparison: { explicitTermWeight: 0.44, parallelLanguageWeight: 0.2, comparativeFormWeight: 0.44 },
  causal: { directionalWeight: 0.46, connectiveWeight: 0.34, twoClauseBonus: 0.14, repeatedSignalBonus: 0.12 },
  conceptMap: { relationWeight: 0.34, hubWeight: 0.24, entityNetworkWeight: 0.2, networkCombinationBonus: 0.16 },
  hierarchy: {
    strongContainmentWeight: 0.46, weakContainmentWeight: 0.28, groupedEnumerationWeight: 0.22,
    flatListWeight: 0.44, nestedListBonus: 0.2
  },
  quantitative: {
    symbolicEquationWeight: 0.44, verbalRelationshipWeight: 0.46, percentageWeight: 0.28,
    unitWeight: 0.26, multipleQuantityWeight: 0.18
  }
} as const

export const ROUTER_MARKERS = {
  process: {
    transitions: /\b(first|next|then|finally|afterward|subsequently)\b/gi,
    temporal: /\b(before|after|once|when)\b/gi,
    explicit: /\b(the process begins|the process ends|followed by|in sequence)\b/i,
    orderedItem: /^\s*(?:\d+[.)]|step\s+\d+[:.)]?)[ \t]+/gim,
    arrow: /(?:→|->|=>)/
  },
  comparison: {
    explicit: /\b(vs\.?|versus|whereas|unlike|compared (?:with|to)|similarities|differences|different)\b/gi,
    parallel: /\b(?:both|either)\b[^.!?]*\b(?:and|or)\b/i,
    comparative: /\b(?:more|less|fewer|higher|lower|faster|slower|better|worse)\s+than\b/i,
    metaLanguage: /\b(?:word|phrase|term|symbol|heading)\s+["']?(?:vs\.?|versus|whereas|unlike)["']?/i
  },
  causal: {
    directional: /\b(causes?|leads? to|results? in|gives? rise to|produces?|triggers?)\b/gi,
    connective: /\b(because|therefore|due to|consequently|as a result|thus|hence)\b/gi,
    metaLanguage: /\b(?:word|phrase|term)\s+["']?(?:because|therefore|consequently|thus|hence)["']?/i
  },
  conceptMap: {
    relation: /\b(related to|related through|associated with|connected to|linked to|depends on|interacts with|relationship between)\b/gi,
    hub: /\b(involves?|integrates?|connects?)\b/gi
  },
  hierarchy: {
    strongContainment: /\b(consists of|composed of|made up of|divided into|types of|categories of|kinds of|parts of|components of)\b/gi,
    weakContainment: /\b(contains?|includes?)\b/gi,
    listItem: /^\s*(?:[-*]|\d+[.)])[ \t]+/gim,
    nestedListItem: /^\s{2,}(?:[-*]|\d+[.)])[ \t]+/m
  },
  quantitative: {
    symbolicEquation: /(?:=|\s[+×*÷]\s|\s[-−]\s|\s\/\s|≤|≥)/,
    verbalRelationship: /\b(divided by|multiplied by|sum of|difference between|ratio of|proportional to|per unit|equals? .+ (?:plus|minus|times))\b/i,
    percentage: /\b\d+(?:\.\d+)?\s*%/g,
    unit: /\b\d+(?:\.\d+)?\s*(?:ms|milliseconds?|s|seconds?|hz|khz|mhz|ghz|kb|mb|gb|bytes?|m|meters?|km|kilometers?|g|kg|°c|°f|volts?|watts?)\b/gi,
    quantity: /\b\d+(?:\.\d+)?\b/g
  }
} as const

// Explicit ordering makes equal-score routing stable and easy to revisit.
export const STRUCTURED_TYPE_PRIORITY: Exclude<RepresentationType, "plain_text">[] = [
  "process", "comparison", "causal", "hierarchy", "quantitative", "concept_map"
]
