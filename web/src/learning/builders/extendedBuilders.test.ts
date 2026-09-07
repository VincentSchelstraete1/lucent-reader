import { describe, expect, it } from "vitest"
import { buildCausalLearningObject, buildConceptMapLearningObject, buildHierarchyLearningObject, buildPlainTextLearningObject, buildQuantitativeLearningObject } from "./extendedBuilders"

describe("extended learning object builders", () => {
  it("builds semantic objects for each remaining representation", () => {
    expect(buildCausalLearningObject("Rain causes flooding.").type).toBe("causal")
    expect(buildConceptMapLearningObject("Cells, DNA, and proteins are related.").nodes.length).toBeGreaterThan(1)
    expect(buildHierarchyLearningObject("Memory consists of cache, RAM, and storage.").root.children?.length).toBeGreaterThan(1)
    expect(buildQuantitativeLearningObject("Velocity = distance / time.").relationships.length).toBeGreaterThan(0)
    expect(buildPlainTextLearningObject("A paragraph.").paragraphs).toEqual(["A paragraph."])
  })
})
