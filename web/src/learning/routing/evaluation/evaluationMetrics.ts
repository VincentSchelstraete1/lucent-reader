import { REPRESENTATION_TYPES, type RepresentationRoute, type RepresentationType } from "../representationTypes"
import type { RouterExample } from "./routerDataset"

export type RouterFunction = (text: string) => RepresentationRoute

export type EvaluatedExample = RouterExample & {
  predicted: RepresentationType
  confidence: number
  scores: RepresentationRoute["scores"]
  reasons: string[]
  strictCorrect: boolean
  acceptable: boolean
}

export type EvaluationSummary = {
  total: number
  correct: number
  accuracy: number
  perClass: Record<RepresentationType, { correct: number; total: number; accuracy: number }>
  confusion: Record<RepresentationType, Record<RepresentationType, number>>
  correctConfidence: { min: number; mean: number; max: number }
  incorrectConfidence: { min: number; mean: number; max: number }
  failures: EvaluatedExample[]
  ambiguous: EvaluatedExample[]
}

const rounded = (value: number) => Math.round(value * 1000) / 1000
const confidenceStats = (values: number[]) => ({
  min: values.length ? Math.min(...values) : 0,
  mean: values.length ? rounded(values.reduce((sum, value) => sum + value, 0) / values.length) : 0,
  max: values.length ? Math.max(...values) : 0
})

export function evaluateRouter(examples: RouterExample[], router: RouterFunction): EvaluationSummary {
  const evaluated = examples.map((example): EvaluatedExample => {
    const result = router(example.text)
    return {
      ...example,
      predicted: result.type,
      confidence: result.confidence,
      scores: result.scores,
      reasons: result.reasons,
      strictCorrect: result.type === example.expected,
      acceptable: (example.acceptableTypes ?? [example.expected]).includes(result.type)
    }
  })
  const strict = evaluated.filter((example) => !example.ambiguous)
  const correct = strict.filter((example) => example.strictCorrect)
  const incorrect = strict.filter((example) => !example.strictCorrect)
  const perClass = Object.fromEntries(REPRESENTATION_TYPES.map((type) => {
    const classExamples = strict.filter((example) => example.expected === type)
    const classCorrect = classExamples.filter((example) => example.strictCorrect).length
    return [type, { correct: classCorrect, total: classExamples.length, accuracy: classExamples.length ? rounded(classCorrect / classExamples.length) : 0 }]
  })) as EvaluationSummary["perClass"]
  const confusion = Object.fromEntries(REPRESENTATION_TYPES.map((expected) => [
    expected,
    Object.fromEntries(REPRESENTATION_TYPES.map((predicted) => [
      predicted,
      strict.filter((example) => example.expected === expected && example.predicted === predicted).length
    ]))
  ])) as EvaluationSummary["confusion"]
  return {
    total: strict.length,
    correct: correct.length,
    accuracy: strict.length ? rounded(correct.length / strict.length) : 0,
    perClass,
    confusion,
    correctConfidence: confidenceStats(correct.map((example) => example.confidence)),
    incorrectConfidence: confidenceStats(incorrect.map((example) => example.confidence)),
    failures: incorrect,
    ambiguous: evaluated.filter((example) => example.ambiguous)
  }
}

export function compareEvaluations(baseline: EvaluationSummary, candidate: EvaluationSummary) {
  const baselineFailures = new Set(baseline.failures.map((example) => example.id))
  const candidateFailures = new Set(candidate.failures.map((example) => example.id))
  return {
    fixed: [...baselineFailures].filter((id) => !candidateFailures.has(id)),
    regressions: [...candidateFailures].filter((id) => !baselineFailures.has(id))
  }
}
