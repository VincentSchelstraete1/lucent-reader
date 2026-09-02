import { describe, expect, it } from "vitest"
import { buildProcessLearningObject } from "../builders/processBuilder"
import { processToMermaid } from "./ProcessRenderer"

describe("processToMermaid", () => {
  it("translates semantic steps and connections internally", () => {
    const definition = processToMermaid(buildProcessLearningObject("First prepare. Then execute. Finally review."))
    expect(definition).toContain("flowchart LR")
    expect(definition).toContain("node0 --> node1")
    expect(definition).toContain("node1 --> node2")
  })

  it("escapes markup in labels", () => {
    const object = buildProcessLearningObject("First use <script>alert(1)</script>. Then finish.")
    const definition = processToMermaid(object)
    expect(definition).not.toContain("<script>")
    expect(definition).toContain("&lt;script&gt;")
  })
})
