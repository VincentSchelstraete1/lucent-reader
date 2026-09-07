import { routeRepresentationBaseline } from "../representationRouter"
import { evaluateRouter } from "./evaluationMetrics"
import { DATASET_SPLIT_SEED, splitRouterDataset } from "./routerDataset"
import { describe, expect, it } from "vitest"

describe("development-only baseline evaluation", () => {
  it("reports baseline metrics without reading holdout predictions", () => {
    const { development } = splitRouterDataset()
    const summary = evaluateRouter(development, routeRepresentationBaseline)
    expect(DATASET_SPLIT_SEED).toBe("lucent-router-evaluation-v1")
    expect(development.map((example) => example.id)).toHaveLength(91)
    expect({ correct: summary.correct, total: summary.total, accuracy: summary.accuracy })
      .toEqual({ correct: 45, total: 84, accuracy: 0.536 })
  })
})
