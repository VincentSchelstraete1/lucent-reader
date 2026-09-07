import { describe, expect, it } from "vitest"
import { routeRepresentation, routeRepresentationBaseline } from "../representationRouter"
import { compareEvaluations, evaluateRouter } from "./evaluationMetrics"
import { DEVELOPMENT_CANDIDATES, createExperimentalRouter } from "./experimentalRouters"
import { splitRouterDataset } from "./routerDataset"

describe("development-only router experiments", () => {
  const { development } = splitRouterDataset()

  it("keeps the no-change experimental profile identical to the frozen baseline", () => {
    const noChange = createExperimentalRouter({})
    for (const example of development) {
      expect(noChange(example.text)).toEqual(routeRepresentationBaseline(example.text))
    }
  })

  it("keeps the production router on the frozen baseline after candidate rejection", () => {
    for (const example of development) {
      expect(routeRepresentation(example.text)).toEqual(routeRepresentationBaseline(example.text))
    }
  })

  it("reports controlled candidate results without evaluating holdout", () => {
    const baseline = evaluateRouter(development, routeRepresentationBaseline)
    const experiments = Object.entries(DEVELOPMENT_CANDIDATES).map(([version, router]) => {
      const summary = evaluateRouter(development, router)
      const changes = compareEvaluations(baseline, summary)
      return {
        version,
        correct: summary.correct,
        total: summary.total,
        accuracy: summary.accuracy,
        perClass: summary.perClass,
        correctConfidence: summary.correctConfidence,
        incorrectConfidence: summary.incorrectConfidence,
        fixedCount: changes.fixed.length,
        regressionCount: changes.regressions.length,
        regressions: changes.regressions,
        ambiguousAcceptable: summary.ambiguous.filter((example) => example.acceptable).length
      }
    })
    expect(experiments.map(({ version, correct, total, accuracy, fixedCount, regressionCount }) => ({
      version, correct, total, accuracy, fixedCount, regressionCount
    }))).toEqual([
      { version: "Candidate A — lexical coverage", correct: 68, total: 84, accuracy: 0.81, fixedCount: 25, regressionCount: 2 },
      { version: "Candidate B — class thresholds", correct: 48, total: 84, accuracy: 0.571, fixedCount: 3, regressionCount: 0 },
      { version: "Candidate C — structural patterns", correct: 53, total: 84, accuracy: 0.631, fixedCount: 8, regressionCount: 0 },
      { version: "Candidate A+C", correct: 70, total: 84, accuracy: 0.833, fixedCount: 27, regressionCount: 2 },
      { version: "Candidate A+B+C", correct: 71, total: 84, accuracy: 0.845, fixedCount: 28, regressionCount: 2 },
      { version: "Candidate D — guarded A+C", correct: 75, total: 84, accuracy: 0.893, fixedCount: 30, regressionCount: 0 }
    ])
  })
})
