import { createElement } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it } from "vitest"

import { NoteView } from "./Notes"
import type { SectionNote } from "../api/client"

describe("SectionNote product rendering", () => {
  it("renders stable review anchors without leaking source block identifiers", () => {
    const note: SectionNote = {
      id: "section-memory",
      title: "Memory hierarchy",
      bigIdea: "Nearby memory is faster but smaller.",
      learningGoals: [],
      components: [{
        kind: "key_definition",
        title: "Cache",
        term: "Cache",
        definition: "Small, fast memory near the processor.",
        sourceBlockIds: ["private-block-id"],
        nodes: [], edges: [], items: [], dimensions: [], steps: [],
      }],
      keyTakeaways: ["The hierarchy trades speed for capacity."],
      sourceBlockIds: ["private-block-id"],
      omittedNoise: [],
    }

    const html = renderToStaticMarkup(createElement(NoteView, { notes: [note] }))

    expect(html).toContain('id="section-memory"')
    expect(html).toContain("The hierarchy trades speed for capacity")
    expect(html).not.toContain("private-block-id")
  })

  it("renders branching flow topology rather than chaining sibling outcomes", () => {
    const note: SectionNote = {
      id: "section-branch", title: "Cache check", bigIdea: "The tag check chooses one of two paths.", learningGoals: [], keyTakeaways: [], sourceBlockIds: ["b"], omittedNoise: [],
      components: [{
        kind: "flow", title: "Hit or miss", sourceBlockIds: ["b"], items: [], dimensions: [], steps: [],
        nodes: [{ id: "check", label: "Check tag" }, { id: "hit", label: "Return data" }, { id: "miss", label: "Fetch block" }],
        edges: [{ source: "check", target: "hit", relation: "hit" }, { source: "check", target: "miss", relation: "miss" }],
      }],
    }
    const html = renderToStaticMarkup(createElement(NoteView, { notes: [note] }))
    expect(html).toContain("flow-split")
    expect(html).toContain("Return data")
    expect(html).toContain("Fetch block")
    expect(html).not.toContain("private-block-id")
  })

  it("keeps long supporting prose behind progressive disclosure", () => {
    const note: SectionNote = {
      id: "section-explanation", title: "Energy", bigIdea: "Energy changes form.", learningGoals: [], keyTakeaways: [], sourceBlockIds: ["b"], omittedNoise: [],
      components: [{ kind: "explanation", title: "Why it matters", text: "Energy changes form in an isolated system. Friction transfers some mechanical energy to heat. This makes the visible motion gradually decrease. The same conservation principle explains why the total remains constant even as the observable movement changes over time.", sourceBlockIds: ["b"], nodes: [], edges: [], items: [], dimensions: [], steps: [] }],
    }
    const html = renderToStaticMarkup(createElement(NoteView, { notes: [note] }))
    expect(html).toContain("<details")
    expect(html).toContain("<summary>Energy changes form in an isolated system.")
  })
})
