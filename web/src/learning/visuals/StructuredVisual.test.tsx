import { createElement } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it } from "vitest"
import { StructuredVisual, type StructuredVisualSpec } from "./StructuredVisual"

const spec: StructuredVisualSpec = {
  type: "process_flow",
  title: "A process",
  purpose: "Follow the grounded transition.",
  nodes: [{ id: "a", label: "Start" }, { id: "b", label: "Finish" }],
  edges: [{ source: "a", target: "b", label: "leads to" }],
  stages: [{ title: "Start", activeNodeIds: ["a"] }],
  animations: [{ operation: "flow", targetIds: ["a", "b"] }],
}

describe("StructuredVisual semantic connectors", () => {
  it("uses the real edge for motion and never renders a detached dashed path or ball", () => {
    const html = renderToStaticMarkup(createElement(StructuredVisual, { spec }))
    expect(html).toContain("structured-visual-edge motion")
    expect(html).not.toContain("structured-visual-motion-path")
    expect(html).not.toContain("structured-visual-flow-dot")
    expect(html).not.toContain("animateMotion")
  })
})
