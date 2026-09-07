import type { ComparisonAttribute, ComparisonLearningObject } from "../schema/learningObject"
import { stableTextId } from "./builderUtils"

const COMPARISON_PATTERN = /^(.+?)\s+(is|are|has|have|uses?|allows?)\s+(.+?),?\s+whereas\s+(.+?)\s+(is|are|has|have|uses?|allows?)\s+(.+?)[.!?]*$/i
const NUMBER_WORDS: Record<string, string> = { one: "1", two: "2", three: "3", four: "4", five: "5", six: "6", seven: "7", eight: "8" }

function itemName(value: string): string {
  const withoutArticle = value.trim().replace(/^(?:a|an|the)\s+/i, "")
  const normalized = withoutArticle.replace(/\b(one|two|three|four|five|six|seven|eight)-way\b/gi, (match, number: string) => match.replace(number, NUMBER_WORDS[number.toLowerCase()]))
  return normalized.charAt(0).toUpperCase() + normalized.slice(1)
}

function normalizedValue(value: string): string {
  return value.trim().replace(/^(one|two|three|four|five|six|seven|eight)\b/i, (number) => NUMBER_WORDS[number.toLowerCase()])
}

function attributes(verb: string, leftValue: string, rightValue: string): [ComparisonAttribute, ComparisonAttribute] {
  const locationPattern = /^(?:one|two|three|four|five|six|seven|eight|\d+)\s+possible\s+locations?$/i
  if (locationPattern.test(leftValue.trim()) && locationPattern.test(rightValue.trim())) {
    const value = (text: string) => normalizedValue(text).split(/\s+/)[0]
    return [{ label: "Possible locations", value: value(leftValue) }, { label: "Possible locations", value: value(rightValue) }]
  }
  const labels: Record<string, string> = { is: "Characteristic", are: "Characteristic", has: "Feature", have: "Feature", use: "Approach", uses: "Approach", allow: "Capability", allows: "Capability" }
  const label = labels[verb.toLowerCase()] ?? "Difference"
  return [{ label, value: normalizedValue(leftValue) }, { label, value: normalizedValue(rightValue) }]
}

function verbFamily(verb: string): string {
  const families: Record<string, string> = { is: "be", are: "be", has: "have", have: "have", use: "use", uses: "use", allow: "allow", allows: "allow" }
  return families[verb.toLowerCase()] ?? verb.toLowerCase()
}

export function buildComparisonLearningObject(sourceText: string): ComparisonLearningObject {
  const normalized = sourceText.trim()
  const match = normalized.match(COMPARISON_PATTERN)
  if (!match) throw new Error("This comparison builder needs an explicit ‘whereas’ comparison")
  const [, leftRaw, leftVerb, leftValue, rightRaw, rightVerb, rightValue] = match
  if (verbFamily(leftVerb) !== verbFamily(rightVerb)) {
    throw new Error("This comparison builder needs parallel comparison language")
  }
  const leftName = itemName(leftRaw)
  const rightName = itemName(rightRaw)
  const [leftAttribute, rightAttribute] = attributes(leftVerb, leftValue, rightValue)
  const items = [
    { id: "item-1", name: leftName, attributes: [leftAttribute] },
    { id: "item-2", name: rightName, attributes: [rightAttribute] }
  ]
  return {
    id: `comparison-${stableTextId(normalized)}`,
    type: "comparison",
    title: `${leftName} compared with ${rightName}`,
    learningGoal: `Distinguish ${leftName} from ${rightName} using the same attribute.`,
    sourceText: normalized,
    sourceReferences: [],
    interactions: [{ type: "item_compare", targetIds: items.map((item) => item.id) }],
    items,
    differences: [`${leftName}: ${leftAttribute.value}; ${rightName}: ${rightAttribute.value}.`]
  }
}
