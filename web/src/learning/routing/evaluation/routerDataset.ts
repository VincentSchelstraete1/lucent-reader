import type { RepresentationType } from "../representationTypes"
import rawDataset from "./routerDataset.json"

export type EducationalSubject = "computer_science" | "biology" | "physics" | "mathematics" | "economics" | "history" | "psychology"
export type PassageStyle = "textbook" | "lecture_note" | "highlight" | "paragraph" | "list" | "equation" | "definition"

export type RouterExample = {
  id: string
  expected: RepresentationType
  text: string
  subject: EducationalSubject
  style: PassageStyle
  ambiguous?: boolean
  acceptableTypes?: RepresentationType[]
  ambiguityNote?: string
}

// The dataset itself lives in routerDataset.json - a single machine-readable
// fixture shared with the Python port (backend/app/routing/dataset.py reads
// this exact file) instead of two independently hand-authored copies. See
// backend/tests/test_router_parity.py for the cross-language check this
// makes possible. If you need to add or edit examples, edit the JSON file
// directly (id format: "<expected>-NN", or "ambiguous-<expected>-N").
export const ROUTER_DATASET: RouterExample[] = rawDataset as RouterExample[]

export type DatasetPartition = "development" | "holdout"
export const DATASET_SPLIT_SEED = "lucent-router-evaluation-v1"

const stableHash = (value: string) => {
  let hash = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return hash >>> 0
}

export function splitRouterDataset(examples = ROUTER_DATASET): Record<DatasetPartition, RouterExample[]> {
  const groups = new Map<string, RouterExample[]>()
  for (const example of examples) {
    const key = `${example.ambiguous ? "ambiguous" : "strict"}:${example.expected}`
    groups.set(key, [...(groups.get(key) ?? []), example])
  }

  const development: RouterExample[] = []
  const holdout: RouterExample[] = []
  for (const group of groups.values()) {
    const ordered = [...group].sort((left, right) => {
      const difference = stableHash(`${DATASET_SPLIT_SEED}:${left.id}`) - stableHash(`${DATASET_SPLIT_SEED}:${right.id}`)
      return difference || left.id.localeCompare(right.id)
    })
    const holdoutCount = Math.max(1, Math.round(ordered.length * 0.25))
    holdout.push(...ordered.slice(0, holdoutCount))
    development.push(...ordered.slice(holdoutCount))
  }

  return {
    development: development.sort((a, b) => a.id.localeCompare(b.id)),
    holdout: holdout.sort((a, b) => a.id.localeCompare(b.id))
  }
}
