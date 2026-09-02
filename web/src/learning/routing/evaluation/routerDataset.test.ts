import { describe, expect, it } from "vitest"
import { REPRESENTATION_TYPES } from "../representationTypes"
import { DATASET_SPLIT_SEED, ROUTER_DATASET, splitRouterDataset } from "./routerDataset"

describe("router evaluation dataset", () => {
  it("contains a broad labeled corpus with unique identifiers", () => {
    expect(ROUTER_DATASET.length).toBe(126)
    expect(new Set(ROUTER_DATASET.map((example) => example.id)).size).toBe(ROUTER_DATASET.length)
    for (const type of REPRESENTATION_TYPES) {
      expect(ROUTER_DATASET.filter((example) => !example.ambiguous && example.expected === type)).toHaveLength(16)
      expect(ROUTER_DATASET.filter((example) => example.ambiguous && example.expected === type)).toHaveLength(2)
    }
  })

  it("creates a deterministic stratified development/holdout split", () => {
    const first = splitRouterDataset()
    const second = splitRouterDataset()
    expect(DATASET_SPLIT_SEED).toBe("lucent-router-evaluation-v1")
    expect(first).toEqual(second)
    expect(first.development).toHaveLength(91)
    expect(first.holdout).toHaveLength(35)
    for (const type of REPRESENTATION_TYPES) {
      expect(first.development.filter((example) => !example.ambiguous && example.expected === type)).toHaveLength(12)
      expect(first.holdout.filter((example) => !example.ambiguous && example.expected === type)).toHaveLength(4)
      expect(first.development.filter((example) => example.ambiguous && example.expected === type)).toHaveLength(1)
      expect(first.holdout.filter((example) => example.ambiguous && example.expected === type)).toHaveLength(1)
    }
  })
})
