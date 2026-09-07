import { describe, expect, it } from "vitest"
import { buildComparisonLearningObject } from "../builders/comparisonBuilder"
import { buildProcessLearningObject } from "../builders/processBuilder"
import { rendererKindFor } from "./LearningObjectRenderer"

describe("LearningObjectRenderer dispatch", () => {
  it("selects the process renderer path", () => {
    expect(rendererKindFor(buildProcessLearningObject("First prepare. Then finish."))).toBe("process")
  })

  it("selects the comparison renderer path", () => {
    expect(rendererKindFor(buildComparisonLearningObject("TCP uses connections, whereas UDP uses datagrams."))).toBe("comparison")
  })
})
