import { createElement } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it } from "vitest"

import type { SectionNote } from "../api/client"
import { LearnView } from "./Notes"

describe("Learn tutor browser smoke fixture", () => {
  it("renders the real accessible onboarding contract without backend or model credentials", () => {
    const note: SectionNote = {
      id: "pendulum",
      title: "Pendulum energy",
      bigIdea: "Potential energy becomes kinetic energy as the pendulum falls.",
      learningGoals: [],
      components: [],
      keyTakeaways: ["Speed is greatest at the bottom."],
      sourceBlockIds: ["b1"],
      omittedNoise: [],
    }
    const html = renderToStaticMarkup(createElement(LearnView, { note, documentId: 7, onBack: () => undefined }))

    expect(html).toContain("What do you want to get out of this?")
    expect(html).toContain("Understand the concepts")
    expect(html).toContain("Learn to solve problems")
    expect(html).toContain("How familiar are you with this already?")
    expect(html).toContain("Start learning")
    expect(html).not.toContain("source-grounded relationship")
  })
})
