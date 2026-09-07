import { describe, expect, it } from "vitest"
import { buildLearningObject } from "./learningObjectBuilder"

describe("buildLearningObject", () => {
  it("preserves the process path", () => {
    expect(buildLearningObject("process", "First prepare. Then execute. Finally review.")?.type).toBe("process")
  })

  it("builds the comparison path", () => {
    expect(buildLearningObject("comparison", "TCP uses connections, whereas UDP uses datagrams.")?.type).toBe("comparison")
  })

  it("builds every taxonomy type", () => {
    for (const type of ["causal", "concept_map", "hierarchy", "quantitative", "plain_text"] as const) {
      expect(buildLearningObject(type, "A causes B.")?.type).toBe(type)
    }
  })
})
