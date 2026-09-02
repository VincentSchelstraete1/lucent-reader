import type { CausalLearningObject, ConceptMapLearningObject, HierarchyLearningObject, PlainTextLearningObject, QuantitativeLearningObject } from "../schema/learningObject"
import { stableTextId } from "./builderUtils"

function base(type: any, text: string, title: string) { return { id: stableTextId(`${type}:${text}`), type, title, learningGoal: "Understand the source passage", sourceText: text, sourceReferences: [], interactions: [] } }

export function buildCausalLearningObject(text: string): CausalLearningObject {
  const parts = text.split(/(?:,?\s+(?:which\s+)?(?:causes?|leads?\s+to|results?\s+in|therefore)\s+)/i).map(s => s.trim()).filter(Boolean)
  const nodes = parts.length > 1 ? parts : [text]
  return { ...base("causal", text, "Cause and effect"), nodes: nodes.map((label, i) => ({ id: `cause-${i}`, label })), edges: nodes.slice(1).map((_, i) => ({ from: `cause-${i}`, to: `cause-${i + 1}`, label: "causes" })) }
}

export function buildConceptMapLearningObject(text: string): ConceptMapLearningObject {
  const concepts = (text.match(/[A-Z][A-Za-z-]{2,}(?:\s+[A-Za-z-]{2,})?/g) ?? []).slice(0, 8)
  const labels = concepts.length >= 2 ? [...new Set(concepts)] : text.split(/[,;]|\band\b/i).map(s => s.trim()).filter(Boolean).slice(0, 8)
  const nodes = labels.map((label, i) => ({ id: `concept-${i}`, label }))
  return { ...base("concept_map", text, "Concept relationships"), nodes, relationships: nodes.slice(1).map((node) => ({ source: nodes[0].id, target: node.id, relation: "related to" })) }
}

export function buildHierarchyLearningObject(text: string): HierarchyLearningObject {
  const match = text.match(/(.+?)\s+(?:consists of|includes|contains|has)\s+(.+)/i)
  const rootLabel = match?.[1]?.trim() || "Main topic"
  const children = (match?.[2] || text).split(/,|;|\band\b/i).map(s => s.replace(/[.。]$/, "").trim()).filter(Boolean).map((label, i) => ({ id: `child-${i}`, label }))
  return { ...base("hierarchy", text, "Hierarchy"), root: { id: "root", label: rootLabel, children } }
}

export function buildQuantitativeLearningObject(text: string): QuantitativeLearningObject {
  const expressions = text.match(/[^.?!]*(?:=|×|\+|÷|\bdivided by\b|\bpercent\b|%)[^.?!]*/gi)?.map(s => s.trim()).filter(Boolean) ?? [text]
  const variables = [...new Set((text.match(/[A-Za-z][A-Za-z ]{1,20}/g) ?? []).map(s => s.trim()).filter(s => s.length > 2).slice(0, 8))].map((name, i) => ({ id: `var-${i}`, name }))
  return { ...base("quantitative", text, "Quantitative relationship"), variables, relationships: expressions.map(expression => ({ expression })) }
}

export function buildPlainTextLearningObject(text: string): PlainTextLearningObject {
  const paragraphs = text.split(/\n\s*\n/).map(s => s.trim()).filter(Boolean)
  return { ...base("plain_text", text, "Learning note"), paragraphs: paragraphs.length ? paragraphs : [text.trim()] }
}
