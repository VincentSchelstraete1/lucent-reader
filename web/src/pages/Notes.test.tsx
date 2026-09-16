import { createElement } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it } from "vitest"

import { NoteView, SavedContentView } from "./Notes"
import type { Note, SectionNote } from "../api/client"

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

  it("changes the reading depth without changing the semantic note", () => {
    const note: SectionNote = {
      id: "section-depth", title: "Depth", bigIdea: "A concise idea.", learningGoals: [], keyTakeaways: [], sourceBlockIds: ["b"], omittedNoise: [],
      components: [{ kind: "explanation", title: "Context", text: "A first sentence stays visible. A second sentence adds context for learners who want more detail. A third sentence adds the final nuance. A fourth sentence adds another useful distinction so the detailed mode has meaningful supporting material to reveal.", sourceBlockIds: ["b"], nodes: [], edges: [], items: [], dimensions: [], steps: [] }],
    }
    const concise = renderToStaticMarkup(createElement(NoteView, { notes: [note], depth: "concise" }))
    const detailed = renderToStaticMarkup(createElement(NoteView, { notes: [note], depth: "detailed" }))
    expect(concise).not.toContain("final nuance")
    expect(detailed).toContain("open=\"\"")
    expect(detailed).toContain("final nuance")
  })
})

describe("extension-saved content rendering", () => {
  it("shows the saved result, its original passage, and its source", () => {
    const note: Note = {
      id: 17,
      title: "Why domestication matters",
      content: "Domestication changed dogs through selection alongside humans.",
      source_passage: "Dogs were the first species to be domesticated.",
      content_type: "explanation",
      source_url: "https://example.test/dog",
      document_id: 4,
      created_at: "2026-09-15T12:00:00Z",
      updated_at: "2026-09-15T12:00:00Z",
    }

    const html = renderToStaticMarkup(createElement(SavedContentView, { notes: [note] }))

    expect(html).toContain("Saved explanation")
    expect(html).toContain("Domestication changed dogs through selection alongside humans.")
    expect(html).toContain("Dogs were the first species to be domesticated.")
    expect(html).toContain('href="https://example.test/dog"')
  })
})
