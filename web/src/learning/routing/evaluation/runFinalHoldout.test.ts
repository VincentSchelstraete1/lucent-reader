import { describe, expect, it } from "vitest"
import { routeRepresentationBaseline } from "../representationRouter"
import { compareEvaluations, evaluateRouter } from "./evaluationMetrics"
import { DEVELOPMENT_CANDIDATES } from "./experimentalRouters"
import { DATASET_SPLIT_SEED, splitRouterDataset } from "./routerDataset"

describe("final untouched holdout evaluation", () => {
  it("compares the frozen baseline with the development-selected router", () => {
    const { holdout } = splitRouterDataset()
    const baseline = evaluateRouter(holdout, routeRepresentationBaseline)
    const improved = evaluateRouter(holdout, DEVELOPMENT_CANDIDATES["Candidate D — guarded A+C"])
    const changes = compareEvaluations(baseline, improved)
    const summarize = (summary: ReturnType<typeof evaluateRouter>) => ({
      total: summary.total,
      correct: summary.correct,
      accuracy: summary.accuracy,
      perClass: summary.perClass,
      confusion: summary.confusion,
      correctConfidence: summary.correctConfidence,
      incorrectConfidence: summary.incorrectConfidence,
      failures: summary.failures.map(({ id, expected, predicted, confidence, scores, text }) => ({
        id, expected, predicted, confidence, scores, text
      })),
      ambiguous: summary.ambiguous.map(({ id, expected, predicted, acceptable, confidence, scores, text }) => ({
        id, expected, predicted, acceptable, confidence, scores, text
      }))
    })
    const results = {
      partition: "holdout",
      splitSeed: DATASET_SPLIT_SEED,
      holdoutIds: holdout.map((example) => example.id),
      baseline: summarize(baseline),
      selected: summarize(improved),
      fixed: changes.fixed,
      regressions: changes.regressions
    }
    expect(results.holdoutIds).toHaveLength(35)
    expect({ correct: baseline.correct, total: baseline.total, accuracy: baseline.accuracy })
      .toEqual({ correct: 18, total: 28, accuracy: 0.643 })
    expect({ correct: improved.correct, total: improved.total, accuracy: improved.accuracy })
      .toEqual({ correct: 21, total: 28, accuracy: 0.75 })
    expect(changes).toEqual({ fixed: ["causal-09", "concept_map-09", "concept_map-12"], regressions: [] })
    expect(improved.ambiguous.every((example) => example.acceptable)).toBe(true)
  })
})
