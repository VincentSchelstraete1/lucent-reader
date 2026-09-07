import { describe, expect, it } from "vitest"

import { missedQuestions } from "./QuizPlayer"
import type { Quiz } from "../api/client"

const quiz: Quiz = {
  id: 1,
  document_id: 4,
  title: "Memory quiz",
  created_at: "2026-09-03T00:00:00Z",
  questions: [
    { question: "What does a cache avoid?", choices: ["Slow memory", "Registers"], correct_index: 0, explanation: "A hit avoids slower memory.", section_id: "section-cache" },
    { question: "Which is fastest?", choices: ["Disk", "Registers"], correct_index: 1, explanation: "Registers are closest to execution.", section_id: "section-levels" },
  ],
}

describe("quiz review", () => {
  it("retains only missed questions and their note-section associations", () => {
    const missed = missedQuestions(quiz, [1, 1])
    expect(missed).toHaveLength(1)
    expect(missed[0].item.section_id).toBe("section-cache")
  })
})
