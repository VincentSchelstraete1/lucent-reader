import { describe, expect, it } from "vitest"
import { buildComparisonLearningObject } from "./comparisonBuilder"

const source = "A direct-mapped cache allows one possible location, whereas a four-way set-associative cache allows four possible locations."

describe("buildComparisonLearningObject", () => {
  it("extracts aligned cache-location semantics", () => {
    const object = buildComparisonLearningObject(source)
    expect(object).toMatchObject({
      type: "comparison",
      items: [
        { id: "item-1", name: "Direct-mapped cache", attributes: [{ label: "Possible locations", value: "1" }] },
        { id: "item-2", name: "4-way set-associative cache", attributes: [{ label: "Possible locations", value: "4" }] }
      ]
    })
    expect(object.learningGoal).toContain("Direct-mapped cache")
    expect(object.differences?.length).toBeGreaterThan(0)
    expect(JSON.stringify(object)).not.toContain("ComparisonRenderer")
  })

  it("handles another parallel whereas comparison", () => {
    const object = buildComparisonLearningObject("TCP uses connections, whereas UDP uses datagrams.")
    expect(object.items.map((item) => item.name)).toEqual(["TCP", "UDP"])
    expect(object.items.map((item) => item.attributes[0])).toEqual([
      { label: "Approach", value: "connections" },
      { label: "Approach", value: "datagrams" }
    ])
  })

  it("is deterministic", () => {
    expect(buildComparisonLearningObject(source)).toEqual(buildComparisonLearningObject(source))
  })

  it("rejects comparisons without extractable parallel language", () => {
    expect(() => buildComparisonLearningObject("RAM versus storage.")).toThrow()
  })
})
