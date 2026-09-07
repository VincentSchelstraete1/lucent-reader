import { describe, expect, it } from "vitest"
import { buildProcessLearningObject } from "./processBuilder"

const source = "The client sends SYN. Then the server responds with SYN-ACK. Finally the client sends ACK."

describe("buildProcessLearningObject", () => {
  it("creates semantic steps and ordered connections", () => {
    const object = buildProcessLearningObject(source)
    expect(object.type).toBe("process")
    expect(object.steps.map((step) => step.label)).toEqual([
      "The client sends SYN",
      "the server responds with SYN-ACK",
      "the client sends ACK"
    ])
    expect(object.connections).toEqual([
      { from: "step-1", to: "step-2" },
      { from: "step-2", to: "step-3" }
    ])
    expect(JSON.stringify(object)).not.toContain("flowchart")
  })

  it("is deterministic", () => {
    expect(buildProcessLearningObject(source)).toEqual(buildProcessLearningObject(source))
  })

  it("rejects text without two identifiable steps", () => {
    expect(() => buildProcessLearningObject("One isolated sentence.")).toThrow()
  })
})
