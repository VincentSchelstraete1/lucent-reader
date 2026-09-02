"""Direct port of web/src/learning/routing/scoringConfig.ts. Keep the two in
sync by hand - this is the "one shared source of truth, two implementations"
tradeoff documented in the Checkpoint B architecture proposal; parity tests
in test_router_parity.py catch drift.
"""

import re


ROUTER_CONFIG = {
    "structuredThreshold": 0.42,
    "scorePrecision": 2,
    "plainText": {"baseConfidence": 0.76, "competingSignalPenalty": 0.3, "structuredContextScore": 0.12, "minimumConfidence": 0.5},
    "process": {
        "transitionWeight": 0.16, "transitionCap": 0.64, "temporalWeight": 0.08, "temporalCap": 0.24,
        "repeatedTransitionBonus": 0.18, "explicitPhraseWeight": 0.44, "orderedListWeight": 0.5,
        "singleOrderedItemWeight": 0.2, "arrowWeight": 0.44,
    },
    "comparison": {"explicitTermWeight": 0.44, "parallelLanguageWeight": 0.2, "comparativeFormWeight": 0.44},
    "causal": {"directionalWeight": 0.46, "connectiveWeight": 0.34, "twoClauseBonus": 0.14, "repeatedSignalBonus": 0.12},
    "conceptMap": {"relationWeight": 0.34, "hubWeight": 0.24, "entityNetworkWeight": 0.2, "networkCombinationBonus": 0.16},
    "hierarchy": {
        "strongContainmentWeight": 0.46, "weakContainmentWeight": 0.28, "groupedEnumerationWeight": 0.22,
        "flatListWeight": 0.44, "nestedListBonus": 0.2,
    },
    "quantitative": {
        "symbolicEquationWeight": 0.44, "verbalRelationshipWeight": 0.46, "percentageWeight": 0.28,
        "unitWeight": 0.26, "multipleQuantityWeight": 0.18,
    },
}

ROUTER_MARKERS = {
    "process": {
        "transitions": re.compile(r"\b(first|next|then|finally|afterward|subsequently)\b", re.IGNORECASE),
        "temporal": re.compile(r"\b(before|after|once|when)\b", re.IGNORECASE),
        "explicit": re.compile(r"\b(the process begins|the process ends|followed by|in sequence)\b", re.IGNORECASE),
        "orderedItem": re.compile(r"^\s*(?:\d+[.)]|step\s+\d+[:.)]?)[ \t]+", re.IGNORECASE | re.MULTILINE),
        "arrow": re.compile(r"(?:→|->|=>)"),
    },
    "comparison": {
        "explicit": re.compile(r"\b(vs\.?|versus|whereas|unlike|compared (?:with|to)|similarities|differences|different)\b", re.IGNORECASE),
        "parallel": re.compile(r"\b(?:both|either)\b[^.!?]*\b(?:and|or)\b", re.IGNORECASE),
        "comparative": re.compile(r"\b(?:more|less|fewer|higher|lower|faster|slower|better|worse)\s+than\b", re.IGNORECASE),
        "metaLanguage": re.compile(r"""\b(?:word|phrase|term|symbol|heading)\s+["']?(?:vs\.?|versus|whereas|unlike)["']?""", re.IGNORECASE),
    },
    "causal": {
        "directional": re.compile(r"\b(causes?|leads? to|results? in|gives? rise to|produces?|triggers?)\b", re.IGNORECASE),
        "connective": re.compile(r"\b(because|therefore|due to|consequently|as a result|thus|hence)\b", re.IGNORECASE),
        "metaLanguage": re.compile(r"""\b(?:word|phrase|term)\s+["']?(?:because|therefore|consequently|thus|hence)["']?""", re.IGNORECASE),
    },
    "conceptMap": {
        "relation": re.compile(r"\b(related to|related through|associated with|connected to|linked to|depends on|interacts with|relationship between)\b", re.IGNORECASE),
        "hub": re.compile(r"\b(involves?|integrates?|connects?)\b", re.IGNORECASE),
    },
    "hierarchy": {
        "strongContainment": re.compile(r"\b(consists of|composed of|made up of|divided into|types of|categories of|kinds of|parts of|components of)\b", re.IGNORECASE),
        "weakContainment": re.compile(r"\b(contains?|includes?)\b", re.IGNORECASE),
        "listItem": re.compile(r"^\s*(?:[-*]|\d+[.)])[ \t]+", re.IGNORECASE | re.MULTILINE),
        "nestedListItem": re.compile(r"^\s{2,}(?:[-*]|\d+[.)])[ \t]+", re.MULTILINE),
    },
    "quantitative": {
        "symbolicEquation": re.compile(r"(?:=|\s[+×*÷]\s|\s[-−]\s|\s/\s|≤|≥)"),
        "verbalRelationship": re.compile(r"\b(divided by|multiplied by|sum of|difference between|ratio of|proportional to|per unit|equals? .+ (?:plus|minus|times))\b", re.IGNORECASE),
        "percentage": re.compile(r"\b\d+(?:\.\d+)?\s*%"),
        "unit": re.compile(r"\b\d+(?:\.\d+)?\s*(?:ms|milliseconds?|s|seconds?|hz|khz|mhz|ghz|kb|mb|gb|bytes?|m|meters?|km|kilometers?|g|kg|°c|°f|volts?|watts?)\b", re.IGNORECASE),
        "quantity": re.compile(r"\b\d+(?:\.\d+)?\b"),
    },
}

# Explicit ordering makes equal-score routing stable and easy to revisit.
STRUCTURED_TYPE_PRIORITY = ["process", "comparison", "causal", "hierarchy", "quantitative", "concept_map"]
