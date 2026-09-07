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

  it("places connector labels in the gap between same-row nodes", () => {
    const html = renderToStaticMarkup(createElement(StructuredVisual, { spec }))
    const label = html.match(/<text x="([0-9.]+)" y="[0-9.]+"><tspan[^>]*>leads to/)
    expect(label).not.toBeNull()
    // Source node ends at x=183; target starts at x=260. The label belongs
    // in that gap, never inside either node rectangle.
    expect(Number(label?.[1])).toBeGreaterThan(183)
    expect(Number(label?.[1])).toBeLessThan(260)
  })
})
